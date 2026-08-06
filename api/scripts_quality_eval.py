# -*- coding: utf-8 -*-
"""极致性价比通道质量评测（LLM-as-judge + 客观题自动判分）。

横向比对：DeepSeek V4 Flash/Pro · Kimi K3 · GLM-5.2 · Qwen3.7 Max · MiniMax M3 · MiMo Pro
          × 官方直连 / OpenRouter / TokenLab / Requesty / 硅基.com，并带 GPT-5 mini 参考锚点。

用法（在 api/ 目录下执行）：
  python scripts_quality_eval.py --quick       每类 1-2 题，快速冒烟
  python scripts_quality_eval.py               默认每类 2 题
  python scripts_quality_eval.py --full        每类 4 题
  python scripts_quality_eval.py --only deepseek  只测含 deepseek 的候选
  python scripts_quality_eval.py --group retest  补测 Luna / Gemini Pro / Haiku / GPT-5 / GPT-4o 系 × TL/OR
输出：ops/quality-eval-YYYYMMDD-HHMM.md / .json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

API_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(API_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(API_ROOT / ".env", override=False)
except Exception:
    pass

from llm_keys import get_key
from model_router import _call_openai_compatible, _normalize_openai_base

# ---------------- 候选矩阵（label, provider, base, model, cost_in, cost_out $/1M） ----------------
CANDIDATES: list[dict[str, Any]] = [
    # —— 极致性价比通道候选（低价主力）——
    {"label": "DeepSeek V4 Flash · 官方直连", "provider": "deepseek", "base": "https://api.deepseek.com/v1", "model": "deepseek-v4-flash", "cost_in": 0.14, "cost_out": 0.28},
    {"label": "DeepSeek V4 Flash · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-v4-flash", "cost_in": 0.14, "cost_out": 0.28},
    {"label": "DeepSeek V4 Flash · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "deepseek-v4-flash", "cost_in": 0.14, "cost_out": 0.28},
    {"label": "DeepSeek V4 Flash · 硅基.com", "provider": "siliconflow", "base": "https://api.siliconflow.com/v1", "model": "deepseek-ai/DeepSeek-V4-Flash", "cost_in": 0.14, "cost_out": 0.28},
    {"label": "DeepSeek V4 Pro · 官方直连", "provider": "deepseek", "base": "https://api.deepseek.com/v1", "model": "deepseek-v4-pro", "cost_in": 0.435, "cost_out": 0.87},
    {"label": "DeepSeek V4 Pro · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "deepseek-v4-pro", "cost_in": 0.435, "cost_out": 0.87},
    {"label": "DeepSeek V4 Pro · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-v4-pro", "cost_in": 0.435, "cost_out": 0.87},
    {"label": "Kimi K3 · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "kimi-k3", "cost_in": 3.0, "cost_out": 15.0},
    {"label": "GLM-5.2 · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "glm-5.2", "cost_in": 1.12, "cost_out": 3.52},
    {"label": "Qwen3.7 Max · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "qwen3.7-max", "cost_in": 1.475, "cost_out": 4.425},
    {"label": "MiniMax M3 · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "minimax-m3", "cost_in": 0.3, "cost_out": 1.2},
    {"label": "MiMo v2.5 Pro · Requesty", "provider": "requesty", "base": "https://router.requesty.ai/v1", "model": "xiaomi/mimo-v2.5-pro", "cost_in": 0.435, "cost_out": 0.87},
    # —— 参考锚点（国际轻量，横向比对用）——
    {"label": "GPT-5 mini · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "openai/gpt-5-mini", "cost_in": 0.25, "cost_out": 2.0},
    {"label": "GPT-5 mini · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "gpt-5-mini", "cost_in": 0.25, "cost_out": 2.0},
    # —— 旗舰补测组（国际旗舰 × TokenLab/OR + Grok/Llama 探路）——
    {"label": "GPT-5.4 · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "gpt-5.4", "cost_in": 2.0, "cost_out": 12.0, "group": "flagship", "max_tokens": 2048},
    {"label": "GPT-5.4 · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "openai/gpt-5.4", "cost_in": 2.0, "cost_out": 12.0, "group": "flagship", "max_tokens": 2048},
    {"label": "GPT-5.6 Terra · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "gpt-5.6-terra", "cost_in": 2.0, "cost_out": 12.0, "group": "flagship", "max_tokens": 2048},
    {"label": "GPT-5.6 Terra · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "openai/gpt-5.6-terra", "cost_in": 2.0, "cost_out": 12.0, "group": "flagship", "max_tokens": 2048},
    {"label": "Claude Sonnet 5 · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "claude-sonnet-5", "cost_in": 3.0, "cost_out": 15.0, "group": "flagship", "max_tokens": 2048},
    {"label": "Claude Sonnet 5 · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "anthropic/claude-sonnet-5", "cost_in": 3.0, "cost_out": 15.0, "group": "flagship", "max_tokens": 2048},
    {"label": "Claude Opus 5 · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "claude-opus-5", "cost_in": 5.0, "cost_out": 25.0, "group": "flagship", "max_tokens": 2048},
    {"label": "Claude Opus 5 · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "anthropic/claude-opus-5", "cost_in": 5.0, "cost_out": 25.0, "group": "flagship", "max_tokens": 2048},
    {"label": "Gemini 3.6 Flash · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "gemini-3.6-flash", "cost_in": 0.5, "cost_out": 2.5, "group": "flagship", "max_tokens": 2048},
    {"label": "Gemini 3.6 Flash · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "google/gemini-3.6-flash", "cost_in": 0.5, "cost_out": 2.5, "group": "flagship", "max_tokens": 2048},
    {"label": "Grok 4.20 · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "grok-4.20", "cost_in": 3.0, "cost_out": 15.0, "group": "flagship", "max_tokens": 2048},
    {"label": "Grok 4.20 · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "x-ai/grok-4.20", "cost_in": 3.0, "cost_out": 15.0, "group": "flagship", "max_tokens": 2048},
    {"label": "Grok 4.20 · Requesty", "provider": "requesty", "base": "https://router.requesty.ai/v1", "model": "x-ai/grok-4.20", "cost_in": 3.0, "cost_out": 15.0, "group": "flagship", "max_tokens": 2048},
    {"label": "Llama 4 · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "meta-llama/llama-4-maverick", "cost_in": 0.5, "cost_out": 0.9, "group": "flagship", "max_tokens": 2048},
    # —— 补测组（2026-08-06：Luna / Gemini Pro / Haiku / GPT-5 / GPT-4o 系 × TL/OR；cost 按 TL/OR 实价）——
    {"label": "GPT-5.6 Luna · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "gpt-5.6-luna", "cost_in": 0.06, "cost_out": 0.36, "group": "retest", "max_tokens": 2048},
    {"label": "GPT-5.6 Luna · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "openai/gpt-5.6-luna", "cost_in": 0.1, "cost_out": 0.6, "group": "retest", "max_tokens": 2048},
    {"label": "Gemini 3.1 Pro · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "gemini-3.1-pro-preview", "cost_in": 1.0, "cost_out": 6.0, "group": "retest", "max_tokens": 2048},
    {"label": "Gemini 3.1 Pro · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "google/gemini-3.1-pro-preview", "cost_in": 2.0, "cost_out": 12.0, "group": "retest", "max_tokens": 2048},
    {"label": "Claude Haiku 4.5 · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "claude-haiku-4-5", "cost_in": 0.65, "cost_out": 3.25, "group": "retest", "max_tokens": 2048},
    {"label": "Claude Haiku 4.5 · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "anthropic/claude-haiku-4.5", "cost_in": 1.0, "cost_out": 5.0, "group": "retest", "max_tokens": 2048},
    {"label": "GPT-5 · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "gpt-5", "cost_in": 1.25, "cost_out": 10.0, "group": "retest", "max_tokens": 2048},
    {"label": "GPT-5 · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "openai/gpt-5", "cost_in": 1.25, "cost_out": 10.0, "group": "retest", "max_tokens": 2048},
    {"label": "GPT-4o · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "gpt-4o", "cost_in": 2.5, "cost_out": 10.0, "group": "retest", "max_tokens": 2048},
    {"label": "GPT-4o · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o", "cost_in": 2.5, "cost_out": 10.0, "group": "retest", "max_tokens": 2048},
    {"label": "GPT-4o-mini · TokenLab", "provider": "tokenlab", "base": "https://api.tokenlab.sh/v1", "model": "gpt-4o-mini", "cost_in": 0.15, "cost_out": 0.6, "group": "retest", "max_tokens": 2048},
    {"label": "GPT-4o-mini · OpenRouter", "provider": "openrouter", "base": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini", "cost_in": 0.15, "cost_out": 0.6, "group": "retest", "max_tokens": 2048},
]

_KEY_ENV = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "tokenlab": "TOKENLAB_API_KEY",
    "requesty": "REQUESTY_API_KEY",
    "siliconflow": "SILICONFLOW_COM_API_KEY",
}

# ---------------- 题库 ----------------
# type: choice=自动判选项 / math=自动判数字 / judge=LLM 判分
QUESTIONS: dict[str, list[dict[str, str]]] = {
    "en_knowledge": [
        {"q": "Which planet is known as the Red Planet?\nA. Venus B. Mars C. Jupiter D. Saturn", "a": "B", "type": "choice"},
        {"q": "What is the chemical symbol for gold?\nA. Go B. Gd C. Au D. Ag", "a": "C", "type": "choice"},
        {"q": "Who wrote \"Romeo and Juliet\"?\nA. Charles Dickens B. William Shakespeare C. Jane Austen D. Mark Twain", "a": "B", "type": "choice"},
        {"q": "Which ocean is the largest?\nA. Atlantic B. Indian C. Arctic D. Pacific", "a": "D", "type": "choice"},
        {"q": "How many continents are there on Earth?\nA. 5 B. 6 C. 7 D. 8", "a": "C", "type": "choice"},
        {"q": "What is the capital of Australia?\nA. Sydney B. Melbourne C. Canberra D. Perth", "a": "C", "type": "choice"},
        {"q": "Which gas do plants absorb from the atmosphere?\nA. Oxygen B. Nitrogen C. Carbon dioxide D. Hydrogen", "a": "C", "type": "choice"},
        {"q": "What is the largest mammal?\nA. Elephant B. Blue whale C. Giraffe D. Rhino", "a": "B", "type": "choice"},
    ],
    "cn_knowledge": [
        {"q": "中国的首都是？\nA. 上海 B. 广州 C. 北京 D. 深圳", "a": "C", "type": "choice"},
        {"q": "《红楼梦》的作者是？\nA. 罗贯中 B. 曹雪芹 C. 施耐庵 D. 吴承恩", "a": "B", "type": "choice"},
        {"q": "光年是什么的单位？\nA. 时间 B. 速度 C. 距离 D. 亮度", "a": "C", "type": "choice"},
        {"q": "水的化学式是？\nA. CO2 B. H2O C. O2 D. NaCl", "a": "B", "type": "choice"},
        {"q": "一年有多少个节气？\nA. 12 B. 18 C. 24 D. 36", "a": "C", "type": "choice"},
        {"q": "中国四大发明不包括以下哪项？\nA. 造纸术 B. 印刷术 C. 火药 D. 丝绸", "a": "D", "type": "choice"},
        {"q": "珠穆朗玛峰位于？\nA. 中国和尼泊尔边境 B. 中国和印度边境 C. 印度和尼泊尔境内 D. 中国和巴基斯坦边境", "a": "A", "type": "choice"},
        {"q": "人民币的货币代码是？\nA. RMB B. CNY C. CHY D. CNR", "a": "B", "type": "choice"},
    ],
    "en_logic": [
        {"q": "If all Zorks are blue, and some blue things are round, which statement must be true?\nA. All Zorks are round B. Some Zorks are round C. Some round things are blue D. All round things are Zorks", "a": "C", "type": "choice"},
        {"q": "A is taller than B. B is taller than C. Who is the shortest?\nA. A B. B C. C D. Cannot determine", "a": "C", "type": "choice"},
        {"q": "If today is Tuesday, what day will it be in 10 days?\nA. Wednesday B. Thursday C. Friday D. Saturday", "a": "C", "type": "choice"},
        {"q": "Ann sits immediately left of Bob, and Bob sits immediately left of Cal in a row of three. Who is in the middle?\nA. Ann B. Bob C. Cal D. Cannot determine", "a": "B", "type": "choice"},
        {"q": "All apples are fruits. Some fruits are red. Which statement must be true?\nA. All red things are apples B. Some apples are red C. Some red things are fruits D. All fruits are apples", "a": "C", "type": "choice"},
        {"q": "If the day before yesterday was Friday, what day is tomorrow?\nA. Sunday B. Monday C. Tuesday D. Wednesday", "a": "B", "type": "choice"},
    ],
    "en_math": [
        {"q": "What is 17 × 23?", "a": "391", "type": "math"},
        {"q": "If x + 3 = 10, what is 2x?", "a": "14", "type": "math"},
        {"q": "A train travels 300 km in 2.5 hours. What is its average speed in km/h?", "a": "120", "type": "math"},
        {"q": "What is 15% of 240?", "a": "36", "type": "math"},
        {"q": "Simplify: (2^3 × 2^4) / 2^5", "a": "4", "type": "math"},
        {"q": "The sum of three consecutive integers is 72. What is the smallest one?", "a": "23", "type": "math"},
    ],
    "cn_math": [
        {"q": "一个数的 1/4 是 25，这个数是多少？", "a": "100", "type": "math"},
        {"q": "一件商品原价 200 元，打八折后是多少元？", "a": "160", "type": "math"},
        {"q": "一个三角形三个角分别是 2x、3x、4x，x 是多少？", "a": "20", "type": "math"},
        {"q": "100 以内能被 7 整除的最大奇数是？", "a": "91", "type": "math"},
    ],
    "en_code": [
        {"q": "Write a Python function fibonacci(n) that returns a list of the first n Fibonacci numbers.", "a": "函数应正确生成前 n 个斐波那契数；边界 n=0/1 处理合理。", "type": "judge"},
        {"q": "Write a Python function is_palindrome(s) that checks if a string is a palindrome (ignoring case and spaces).", "a": "应忽略大小写与空格后判断回文，返回 bool。", "type": "judge"},
        {"q": "Write a Python function word_frequency(text) that returns a dict of word -> count.", "a": "按空格分词并计数，返回 dict。", "type": "judge"},
        {"q": "Write a Python function largest(nums) that returns the largest number in a list without using max().", "a": "遍历比较求最大，返回数值。", "type": "judge"},
        {"q": "Write a Python function sum_even(n) that returns the sum of all even numbers from 1 to n inclusive.", "a": "累加 1..n 内偶数并返回。", "type": "judge"},
        {"q": "Write a Python function reverse_string(s) that returns the string reversed.", "a": "返回反转后的字符串。", "type": "judge"},
    ],
    "en_reading": [
        {"q": "Summarize in ONE sentence: 'Photosynthesis is the process by which green plants use sunlight to synthesize nutrients from carbon dioxide and water. It generates oxygen as a byproduct, making it essential for most life on Earth. Scientists study it to improve crop yields and develop renewable energy.'", "a": "应抓住：光合作用用阳光把CO2和水合成养分、释放氧气、对地球生命关键。", "type": "judge"},
        {"q": "Extract all dates from this text and list them: 'The project started on 2024-03-15, the first milestone was due April 2, 2024, and the final report is expected by 2024/12/31.'", "a": "应列出 2024-03-15、April 2 2024、2024/12/31 三个日期。", "type": "judge"},
        {"q": "Passage: 'The company reported a 12% increase in revenue, driven mainly by growth in cloud services. However, operating costs also rose 9%, narrowing the profit margin. Management expects similar trends next quarter.' What is the main point?", "a": "营收增12%但成本增9%致利润率收窄；下季度预计类似。", "type": "judge"},
        {"q": "Passage: 'HTTP is a request-response protocol. A client sends a request; a server returns a response with a status code. Common codes include 200 (OK), 404 (Not Found), and 500 (Internal Server Error).' What does status code 500 mean?", "a": "500 = Internal Server Error（服务器内部错误）。", "type": "judge"},
    ],
    "cn_reading": [
        {"q": "用一句话概括：'人工智能正在改变医疗行业：辅助诊断系统能快速分析影像，降低漏诊率；药物研发借助大模型缩短周期；个性化治疗方案让患者获得更精准的护理。'", "a": "AI 通过辅助诊断、加速药物研发、个性化治疗改变医疗。", "type": "judge"},
        {"q": "请解释成语「画蛇添足」的含义，并给出一个使用例子。", "a": "比喻做了多余的事反而不恰当；举例贴切即可。", "type": "judge"},
        {"q": "把下面中文翻译成英文：'这个系统支持高并发请求，平均响应时间低于 200 毫秒。'", "a": "应准确传达高并发支持与 <200ms 平均响应。", "type": "judge"},
        {"q": "这段文字的主要观点是什么？'开源软件降低了企业 IT 成本，但也带来安全维护责任。企业应在选型时评估社区活跃度与安全响应能力。'", "a": "开源降本但有安全维护责任，选型需评估社区与安全能力。", "type": "judge"},
    ],
    "en_instruct": [
        {"q": "Reply with the single word \"banana\". Do not add anything else.", "a": "只输出 banana 一个词。", "type": "judge"},
        {"q": "List exactly three reasons why reading is beneficial. Number them 1, 2, 3.", "a": "恰好三条，且用 1. 2. 3. 编号。", "type": "judge"},
        {"q": "Write a sentence that starts with the word \"Although\" and ends with a period.", "a": "以 Although 开头、句号结尾的完整句。", "type": "judge"},
        {"q": "Translate \"Good morning\" into French and reply with only the translation.", "a": "只输出法文翻译 Bonjour。", "type": "judge"},
    ],
    "cn_instruct": [
        {"q": "只回复两个字：「好的」。不要输出任何其它内容。", "a": "严格只输出「好的」两字。", "type": "judge"},
        {"q": "列出三条喝水的健康益处，用 1. 2. 3. 编号。", "a": "恰好三条且编号 1.2.3.。", "type": "judge"},
        {"q": "用不超过 10 个字回答：中国的首都是哪里？", "a": "答案≤10字且正确（北京）。", "type": "judge"},
        {"q": "用一段话介绍你自己，不超过 50 字。", "a": "一段话且≤50字，内容合理。", "type": "judge"},
    ],
    "en_translate": [
        {"q": "Translate into Chinese: \"The quick brown fox jumps over the lazy dog.\"", "a": "译为通顺中文，意思准确。", "type": "judge"},
        {"q": "Translate into Chinese: \"Please send the invoice to our finance team by Friday.\"", "a": "周五前把发票发给财务团队。", "type": "judge"},
        {"q": "Translate into Chinese: \"This update fixes a critical security vulnerability.\"", "a": "本次更新修复严重安全漏洞。", "type": "judge"},
        {"q": "Translate into Chinese: \"Our API supports streaming responses and function calling.\"", "a": "API 支持流式响应与函数调用。", "type": "judge"},
    ],
    "cn_translate": [
        {"q": "Translate into English: 「这个系统支持高并发请求。」", "a": "准确传达 high concurrency 支持。", "type": "judge"},
        {"q": "Translate into English: 「请在周五之前把发票发给我们的财务团队。」", "a": "Friday 前发发票给财务团队。", "type": "judge"},
        {"q": "Translate into English: 「本次更新修复了一个严重的安全漏洞。」", "a": "修复 critical security vulnerability。", "type": "judge"},
        {"q": "Translate into English: 「我们的 API 支持流式响应和函数调用。」", "a": "streaming responses and function calling。", "type": "judge"},
    ],
}

CATE_TITLES = {
    "en_knowledge": "英文常识", "cn_knowledge": "中文常识", "en_logic": "逻辑推理", "en_math": "数学(EN)",
    "cn_math": "数学(CN)", "en_code": "编程(Python)", "en_reading": "英文阅读", "cn_reading": "中文阅读",
    "en_instruct": "指令遵循(EN)", "cn_instruct": "指令遵循(CN)", "en_translate": "翻译(EN→CN)", "cn_translate": "翻译(CN→EN)",
}

# ---------------- judge ----------------
def _judge(q: dict[str, str], out_text: str, judge_base: str, judge_key: str, judge_model: str) -> dict[str, Any]:
    prompt = (
        "你是严格的模型输出评测员。请从「正确性、完整性、是否严格遵循指令」三个维度打分（1-5 分，3 分=及格，5 分=优秀）。\n"
        f"【题目】{q['q']}\n"
        f"【参考答案/要点】{q['a']}\n"
        f"【模型输出】\n{out_text[:2000]}\n"
        "只输出一行 JSON：{\"score\": 整数1-5, \"pass\": true/false, \"reason\": \"一句话理由\"}"
    )
    try:
        r = _call_openai_compatible(
            base=_normalize_openai_base(judge_base), key=judge_key, model=judge_model,
            prompt=prompt, temperature=0, max_tokens=256, timeout_s=60, provider="judge",
        )
        raw = str(r.get("text") or "")
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return {"score": 0, "pass": False, "reason": "judge unparse: " + raw[:80]}
        d = json.loads(m.group(0))
        score = max(1, min(5, int(d.get("score", 0))))
        return {"score": score, "pass": bool(d.get("pass", score >= 4)), "reason": str(d.get("reason", ""))[:120]}
    except Exception as e:
        return {"score": 0, "pass": False, "reason": "judge err: " + str(e)[:80]}


# ---------------- 自动判分 ----------------
def _auto_check(q: dict[str, str], out_text: str) -> bool:
    t = (out_text or "").strip()
    if q["type"] == "choice":
        m = re.search(r"\b([A-D])\b", t)
        if not m:
            m = re.search(r"答案是\s*([A-D])", t) or re.search(r"Answer:\s*([A-D])", t, re.I)
        return bool(m) and m.group(1).upper() == q["a"].strip().upper()
    if q["type"] == "math":
        nums = re.findall(r"[-+]?\d+\.?\d*", t)
        if not nums:
            return False
        try:
            got = float(nums[-1])
            want = float(q["a"])
            return abs(got - want) <= max(1e-3, abs(want) * 1e-3)
        except (TypeError, ValueError):
            return False
    return False


# ---------------- 主流程 ----------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="每类 1 题快速冒烟")
    ap.add_argument("--full", action="store_true", help="每类 4 题")
    ap.add_argument("--per", type=int, default=2, help="每类题数（默认 2）")
    ap.add_argument("--only", type=str, default="", help="只测 label 含该关键字的候选")
    ap.add_argument("--skip-judge", action="store_true", help="跳过 judge 类（只跑客观题）")
    ap.add_argument("--group", type=str, default="value", choices=["value", "flagship", "retest", "all"], help="候选组：value=价值档（默认）/ flagship=旗舰补测 / retest=补测 Luna-GeminiPro-Haiku-GPT5-4o 系 / all=全部")
    args = ap.parse_args()

    per = 4 if args.full else (1 if args.quick else args.per)
    judge_base = "https://api.deepseek.com/v1"
    judge_key = get_key("DEEPSEEK_API_KEY")
    judge_model = "deepseek-v4-pro"
    if not judge_key:
        print("缺少 DEEPSEEK_API_KEY，无法用 DeepSeek V4 Pro 做裁判；请配 Key 或改用 --skip-judge")
        return 2

    cands = [c for c in CANDIDATES if (args.group == "all" or c.get("group", "value") == args.group)]
    cands = [c for c in cands if (not args.only or args.only.lower() in c["label"].lower())]
    cands = [c for c in cands if get_key(_KEY_ENV[c["provider"]])]
    if not cands:
        print("无可用候选（Key 未配）")
        return 2

    rng = random.Random(20260806)
    selected: dict[str, list[dict[str, str]]] = {}
    for cat, qs in QUESTIONS.items():
        picked = qs if per >= len(qs) else rng.sample(qs, per)
        selected[cat] = picked

    rows: list[dict[str, Any]] = []
    for ci, cand in enumerate(cands, 1):
        label = cand["label"]
        key = get_key(_KEY_ENV[cand["provider"]])
        print(f"[{ci}/{len(cands)}] {label}")
        n_ok = n_auto = n_judge_pass = n_judge = 0
        lat: list[float] = []
        cost = 0.0
        detail: list[dict[str, Any]] = []
        for cat, qs in selected.items():
            for q in qs:
                t0 = time.time()
                last_err: Optional[Exception] = None
                for _attempt in range(2):
                    try:
                        out = _call_openai_compatible(
                            base=_normalize_openai_base(cand["base"]), key=key, model=cand["model"],
                            prompt=q["q"], temperature=0.2, max_tokens=cand.get("max_tokens", 768), timeout_s=60,
                            provider=cand["provider"],
                        )
                        last_err = None
                        break
                    except Exception as _e:
                        last_err = _e
                        if _attempt == 0:
                            time.sleep(2)  # 5xx/网络抖动重试一次，避免瞬时故障误判
                if last_err is not None:
                    rows.append({"candidate": label, "cat": cat, "ok": False, "error": str(last_err)[:150], "ms": int((time.time() - t0) * 1000)})
                    detail.append({"cat": cat, "q": q["q"][:40], "ok": False, "error": str(last_err)[:120]})
                    continue
                text = str(out.get("text") or "").strip()
                p_in = max(0, int(out.get("prompt_tokens") or 0))
                p_out = max(0, int(out.get("completion_tokens") or 0))
                ms = int((time.time() - t0) * 1000)
                lat.append(ms)
                cost += (p_in / 1_000_000) * cand["cost_in"] + (p_out / 1_000_000) * cand["cost_out"]
                if q["type"] in ("choice", "math"):
                    ok = _auto_check(q, text)
                    n_auto += 1
                    n_ok += int(ok)
                    detail.append({"cat": cat, "q": q["q"][:40], "ok": ok, "ms": ms, "in": p_in, "out": p_out})
                else:
                    if args.skip_judge:
                        detail.append({"cat": cat, "q": q["q"][:40], "ok": None, "ms": ms, "in": p_in, "out": p_out})
                        continue
                    j = _judge(q, text, judge_base, judge_key, judge_model)
                    n_judge += 1
                    n_judge_pass += int(j["pass"])
                    detail.append({"cat": cat, "q": q["q"][:40], "ok": j["pass"], "score": j["score"], "reason": j["reason"], "ms": ms, "in": p_in, "out": p_out})
        med_ms = sorted(lat)[len(lat) // 2] if lat else 0
        rows.append({
            "candidate": label, "ok": True, "auto_acc": (n_ok / n_auto) if n_auto else None,
            "judge_acc": (n_judge_pass / n_judge) if n_judge else None, "med_ms": med_ms,
            "cost_usd": round(cost, 4), "n_auto": n_auto, "n_judge": n_judge, "detail": detail,
        })
        acc = f"auto={n_ok}/{n_auto}" if n_auto else ""
        jacc = f"judge={n_judge_pass}/{n_judge}" if n_judge else ""
        print(f"    {acc} {jacc} med={med_ms}ms cost=${cost:.4f}")

    _write_report(rows, cands, per, judge_model, args)
    print(f"\n报告已生成 ops/quality-eval-*.md")
    return 0


def _write_report(rows: list[dict[str, Any]], cands: list[dict[str, Any]], per: int, judge_model: str, args: argparse.Namespace) -> None:
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    out_dir = API_ROOT.parent / "ops"
    out_dir.mkdir(exist_ok=True)
    md = out_dir / f"quality-eval-{ts}.md"
    js = out_dir / f"quality-eval-{ts}.json"

    md_lines = [
        "# AI24X 极致性价比通道质量评测",
        "",
        f"- 评测时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 模式：每类 {per} 题 | 裁判模型：{judge_model}（DeepSeek 官方直连）",
        f"- 说明：客观题（常识/逻辑/数学）自动判分；开放题（编程/阅读/指令/翻译）LLM 裁判 1-5 分，≥4 记通过；延迟为单次调用总耗时中位数；成本按候选公开价 × 实际 tokens 估算。",
        "",
        "## 总分排名",
        "",
        "| 排名 | 候选通道 | 客观正确率 | 开放题通过率 | 中位延迟(ms) | 评测成本($) |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    valid = [r for r in rows if r.get("ok")]
    def _rank(r):
        a = r.get("auto_acc") if r.get("auto_acc") is not None else 0.5
        j = r.get("judge_acc") if r.get("judge_acc") is not None else 0.5
        return a * 0.6 + j * 0.4
    valid.sort(key=_rank, reverse=True)
    for i, r in enumerate(valid, 1):
        md_lines.append(
            f"| {i} | {r['candidate']} | {r.get('auto_acc') if r.get('auto_acc') is not None else '-'} "
            f"| {r.get('judge_acc') if r.get('judge_acc') is not None else '-'} | {r.get('med_ms')} | {r.get('cost_usd')} |"
        )
    failed = [r for r in rows if not r.get("ok")]
    if failed:
        md_lines += ["", "## 调用失败", ""]
        for r in failed:
            md_lines.append(f"- {r['candidate']} [{r['cat']}] {r.get('error','')}")

    md_lines += ["", "## 分项明细", ""]
    for r in valid:
        md_lines += [f"### {r['candidate']}", ""]
        for d in r.get("detail", []):
            if d.get("ok") is None:
                md_lines.append(f"- {d['cat']} {d['q']} … skip (judge 关)")
            elif "score" in d:
                md_lines.append(f"- {d['cat']} {d['q']} … {'PASS' if d['ok'] else 'FAIL'} score={d['score']} reason={d.get('reason','')}")
            elif d.get("error"):
                md_lines.append(f"- {d['cat']} {d['q']} … ERROR {d['error']}")
            else:
                md_lines.append(f"- {d['cat']} {d['q']} … {'OK' if d['ok'] else 'X'}")
        md_lines.append("")

    md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps({"time": ts, "per": per, "judge_model": judge_model, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告：{md}")
    print(f"数据：{js}")


if __name__ == "__main__":
    raise SystemExit(main())
