"""
模型仓库（运营统筹）：档位 ↔ 上游、成本、容灾链、套餐毛利、VIP 自选规划。

覆盖文件：api/data/model_warehouse_override.json
优先级：覆盖 > env OPENROUTER_MODEL_* / 直连默认 > 代码目录
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

_OVERRIDE_PATH = Path(__file__).resolve().parent / "data" / "model_warehouse_override.json"
_AUDIT_PATH = Path(__file__).resolve().parent / "data" / "pricing_audit.jsonl"

# 品牌层默认扣费倍率（相对 flash）；L2/L3 可被 override.layer_mult 覆盖
_DEFAULT_LAYER_MULT = {"L0": 1, "L1": 1, "L2": 3, "L3": 7, "QI": 1}  # ⚠️ 主脑 2026-08-08 修改：L3 6→7，消除 price_warn_or_gpt5_mini 低毛利告警

# 极致性价比·超值包（Value Pack）白名单点名模型（catalog id）：
# 只装「质量过关 + 毛利安全」的低成本名模；2026-08-11 起 gpt-5/gpt-5-mini 走 QuickRouter ×1 实锤成本（0.625/5.0、0.125/1.0）加入白名单；2026-08-12 加 gpt-5.4（TL 主通道毛利 70%，QR 兜底亦不倒挂）；gpt-4o 毛利贴地 26% 暂不点亮，待 QR 补测实拉价；其余国际旗舰（Claude/Gemini/Grok/Kimi K3）仍不装，防倒挂。
# 由 token_mvp_service.value_pack_allowed_models 判定资格；白名单随质量与成本基线滚动调整。
VALUE_PACK_ALLOWED_IDS: frozenset[str] = frozenset(
    {
        "vip-hy3",
        "vip-ds-flash",
        "vip-ds-pro",
        "vip-kimi-code",
        "vip-mimo",
        "vip-minimax",
        "vip-qwen-max",
        "vip-qwen122b",
        "vip-glm",
        "vip-gpt5",
        "vip-gpt5-mini",
        "vip-gpt54",
        "vip-gpt4o-mini",
        "vip-gpt56-terra",
        "vip-gpt56-luna",
        "vip-llama4",
    }
)


def _env_flag(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")

# 粗算上游价（USD / 1M tokens；以公开挂牌量级，非实时账单）
# in=input out=output；展示用 blended≈ (in+out)/2
CATALOG: list[dict[str, Any]] = [
    {
        "id": "ds-v4-flash",
        "title": "DeepSeek V4 Flash",
        "brand_tiers": ["auto", "flash"],
        "layer": "L1",
        "role": "default_flash",
        "priority": 1,
        "openrouter_id": "deepseek/deepseek-v4-flash",
        "direct_id": "deepseek-v4-flash",
        "cost_in": 0.14,
        "cost_out": 0.28,
        "quality": "高性价比默认",
        "access": "live",  # live | ready | planned
        "failover_to": ["silicon-qwen", "or-auto"],
    },
    {
        "id": "ds-v4-pro",
        "title": "DeepSeek V4 Pro",
        "brand_tiers": ["pro"],
        "layer": "L2",
        "role": "default_pro",
        "priority": 1,
        "openrouter_id": "deepseek/deepseek-v4-pro",
        "direct_id": "deepseek-v4-pro",
        "cost_in": 0.435,
        "cost_out": 0.87,
        "quality": "推理加强",
        "access": "live",
        "failover_to": ["ds-v4-flash"],
    },
    {
        "id": "or-gpt5-mini",
        "title": "GPT-5 mini",
        "brand_tiers": ["ultra"],
        "layer": "L3",
        "role": "default_ultra",
        "priority": 1,
        "openrouter_id": "openai/gpt-5-mini",
        "direct_id": None,
        "cost_in": 0.25,
        "cost_out": 2.0,
        "quality": "国际轻量·现行",
        "access": "live",
        "failover_to": ["ds-v4-pro"],
    },
    {
        "id": "silicon-qwen",
        "title": "硅基 Qwen2.5-7B",
        "brand_tiers": ["shared", "auto"],
        "layer": "L0",
        "role": "fallback_l0",
        "priority": 1,
        "openrouter_id": None,
        "direct_id": "Qwen/Qwen2.5-7B-Instruct",
        "provider_hint": "siliconflow",
        "cost_in": 0.0,
        "cost_out": 0.0,
        "quality": "免费/极低价兜底",
        "access": "ready",
        "failover_to": ["or-auto"],
    },
    {
        "id": "or-auto",
        "title": "OpenRouter Auto / Free",
        "brand_tiers": ["shared"],
        "layer": "L0",
        "role": "or_fallback",
        "priority": 9,
        "openrouter_id": "openrouter/auto",
        "direct_id": None,
        "cost_in": 0.0,
        "cost_out": 0.0,
        "quality": "OR 自动/免费池",
        "access": "ready",
        "failover_to": [],
    },
    {
        "id": "mimo-v25",
        "title": "Xiaomi MiMo v2.5",
        "brand_tiers": ["flash"],
        "layer": "L1",
        "role": "capability_alt",
        "priority": 2,
        "openrouter_id": "xiaomi/mimo-v2.5",
        "direct_id": None,
        "cost_in": 0.14,
        "cost_out": 0.28,
        "quality": "能力向备选（非默认）",
        "access": "ready",
        "failover_to": ["ds-v4-flash"],
    },
    {
        "id": "qwen-eu",
        "title": "Qwen3.7 Plus（国际路由）",
        "brand_tiers": ["auto"],
        "layer": "QI",
        "role": "eu_route",
        "priority": 1,
        "openrouter_id": "qwen/qwen3.7-plus",
        "direct_id": None,
        "cost_in": 0.32,
        "cost_out": 1.28,
        "quality": "区域路由·通义现行",
        "access": "ready",
        "failover_to": ["ds-v4-flash"],
    },
    {
        "id": "vip-hy3",
        "title": "Hy3",
        "title_en": "Tencent Hy3",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 10,
        "openrouter_id": "tencent/hy3",
        "direct_id": None,
        "siliconflow_id": "tencent/Hy3",
        "cost_in": 0.129,
        "cost_out": 0.534,
        "billing_mult": 2,
        "in_mult": 1,   # ceil(0.129/0.35*1.8)=1
        "out_mult": 2,  # ceil(0.534/0.35*1.2)=2
        "quality": "低价预算",
        "quality_en": "Ultra-budget",
        "access": "ready",
        "modalities": ["text"],
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },

    # —— VIP 自选：中国名模（按国际知名度排序：Kimi → DeepSeek → Qwen → GLM → MiniMax → MiMo）——
    {
        "id": "vip-ds-flash",
        "title": "DeepSeek V4 Flash",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 2,
        "openrouter_id": "deepseek/deepseek-v4-flash",
        "direct_id": "deepseek-v4-flash",
        # 官方直连优先；硅基仅作官方/OR 失败后的同族兜底
        "siliconflow_id": "deepseek-ai/DeepSeek-V4-Flash",
        "cost_in": 0.14,
        "cost_out": 0.28,
        # 2026-08-14: DS 官方 8/17 涨价（输出 ¥2→¥4.5 闲时/¥9 高峰）
        # → 点名价上调 in2/out4（$0.70/$1.40），闲时 1:4 毛利约 56%
        "billing_mult": 4,
        "in_mult": 2,
        "out_mult": 4,
        "quality": "点名专属 · 全程同模型不降级",
        "quality_en": "Named pick · same-model failover",
        "access": "ready",
        "modalities": ["text"],
        "failover_to": ["ds-v4-flash"],
    },
    {
        "id": "vip-ds-pro",
        "title": "DeepSeek V4 Pro",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 3,
        "openrouter_id": "deepseek/deepseek-v4-pro",
        "direct_id": "deepseek-v4-pro",
        "siliconflow_id": "deepseek-ai/DeepSeek-V4-Pro",
        "cost_in": 0.435,
        "cost_out": 0.87,
        # 2026-08-14: DS 官方 8/17 涨价（输出 ¥6→¥13.5 闲时/¥27 高峰）
        # → 点名价上调 in6/out12（$2.10/$4.20），闲时 1:4 毛利约 56%
        "billing_mult": 12,
        "in_mult": 6,
        "out_mult": 12,
        "quality": "更强推理",
        "quality_en": "Stronger reasoning",
        "access": "ready",
        "modalities": ["text"],
        "failover_to": ["ds-v4-pro"],
    },
    {
        "id": "vip-kimi",
        "title": "Kimi K3",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 1,
        "openrouter_id": "moonshotai/kimi-k3",
        "direct_id": None,
        # 2026-08-06: TokenLab 的 kimi-k3 全挂（400/503，评测 0/24）→ 聚合链屏蔽 TL，走 硅基→OR
        "channels": ["openrouter"],
        # 中国模：硅基优先（相对 OR 降本）；mult 仍按 OR 地板防亏
        "siliconflow_id": "moonshotai/Kimi-K3",
        "cost_in": 3.0,
        "cost_out": 15.0,
        "billing_mult": 39,  # 2026-08-05: ceil(9.0/0.35*1.5)=39 (flash anchor 0.35)
        "in_mult": 18,   # 2026-08-06: 点名溢价（$6.30，2.1x 官方）
        "out_mult": 58,  # 2026-08-06: 点名溢价（$20.30，1.35x 官方）
        "quality": "旗舰 · 多项国际评测冠军",
        "quality_en": "Flagship · top benchmarks",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-ds-pro", "ds-v4-pro"],
    },
    {
        "id": "vip-kimi-code",
        "title": "Kimi K2.7 Code",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 2,
        "openrouter_id": "moonshotai/kimi-k2.7-code",
        "direct_id": None,
        # 2026-08-06: kimi-code 屏蔽 TokenLab（K3 在 TL 全挂 400/503，K2.7 未评测防空转）
        "channels": ["openrouter"],
        "siliconflow_id": "moonshotai/Kimi-K2.7-Code",
        "cost_in": 0.71,
        "cost_out": 3.50,
        "billing_mult": 10,
        "in_mult": 4,   # ceil(0.71/0.35*1.8)=4
        "out_mult": 12,  # ceil(3.5/0.35*1.2)=12
        "quality": "编程",
        "quality_en": "Coding",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-ds-pro", "ds-v4-pro"],
    },
    {
        "id": "vip-mimo",
        "title": "小米 MiMo Pro",
        "title_en": "Xiaomi MiMo Pro",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 4,
        "openrouter_id": "xiaomi/mimo-v2.5-pro",
        "direct_id": None,
        "siliconflow_id": None,  # 硅基目录暂无稳定同款，走 OR
        "cost_in": 0.435,
        "cost_out": 0.87,
        "billing_mult": 4,  # 2026-08-06: 点名溢价（品牌层无 mimo 替代，$1.40，毛利~55%）
        "in_mult": 4,
        "out_mult": 4,
        "quality": "均衡",
        "quality_en": "Balanced",
        "access": "ready",
        "modalities": ["text"],
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },
    {
        "id": "vip-minimax",
        "title": "MiniMax M3",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 5,
        "openrouter_id": "minimax/minimax-m3",
        "direct_id": None,
        "siliconflow_id": "MiniMaxAI/MiniMax-M2.5",
        "cost_in": 0.3,
        "cost_out": 1.2,
        "billing_mult": 4,  # 2026-08-05: ceil(0.75/0.35*1.5)=4
        "in_mult": 2,   # ceil(0.3/0.35*1.8)=2
        "out_mult": 5,  # ceil(1.2/0.35*1.2)=5
        "quality": "智能体 / 编程",
        "quality_en": "Agents / coding",
        "access": "ready",
        "modalities": ["text"],
        "failover_to": ["vip-ds-pro", "ds-v4-pro"],
    },
    {
        "id": "vip-qwen-max",
        "title": "通义 Qwen Max",
        "title_en": "Qwen Max",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 6,
        "openrouter_id": "qwen/qwen3.7-max",
        "direct_id": None,
        "siliconflow_id": None,  # .com/.cn 目录无 Qwen3-235B（仅 Qwen3.5-397B/122B，与 qwen3.7-max 不等价）→ 走 TL 主通道
        # 2026-08-14: 主通道切 TokenLab（TL 实价 $0.3529/$1.4118 为 OR 24%，04 价目监控「降本机会」落地）
        "channels": ["tokenlab", "openrouter", "requesty"],
        "cost_in": 0.3529,
        "cost_out": 1.4118,
        "billing_mult": 13,  # 2026-08-05: ceil(2.95/0.35*1.5)=14
        "in_mult": 8,   # ceil(1.475/0.35*1.8)=8
        "out_mult": 16,  # ceil(4.425/0.35*1.2)=16
        "quality": "通用旗舰",
        "quality_en": "General flagship",
        "access": "ready",
        "modalities": ["text"],
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },

    {
        "id": "vip-qwen122b",
        "title": "Qwen3.5 122B",
        "title_en": "Qwen3.5 122B MoE",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 8,
        "openrouter_id": "qwen/qwen3.5-122b-a10b",
        "direct_id": None,
        "siliconflow_id": "Qwen/Qwen3.5-122B-A10B",
        "cost_in": 0.26,
        "cost_out": 2.08,
        "billing_mult": 6,
        "in_mult": 2,   # ceil(0.26/0.35*1.8)=2
        "out_mult": 8,  # ceil(2.08/0.35*1.2)=8
        "quality": "MoE",
        "quality_en": "MoE flagship",
        "access": "ready",
        "modalities": ["text"],
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },    {
        "id": "vip-glm",
        "title": "智谱 GLM-5.2",
        "title_en": "Zhipu GLM-5.2",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 7,
        "openrouter_id": "z-ai/glm-5.2",
        "direct_id": None,
        "siliconflow_id": "zai-org/GLM-5.1",
        # 2026-08-06: 主通道切 OR（OR 实拉 $0.76/$2.42，比 TL 便宜 32%，毛利混合 39.7%→58.7%）
        "channels": ["openrouter", "tokenlab", "requesty"],
        "cost_in": 0.76,
        "cost_out": 2.42,
        "billing_mult": 10,  # 2026-08-05: ceil(2.32/0.35*1.5)=11
        "in_mult": 8,   # 2026-08-06: 点名溢价（$2.80，2.5x 官方）
        "out_mult": 14,  # 2026-08-06: 点名溢价（$4.90，1.4x 官方）
        "quality": "通用旗舰",
        "quality_en": "General flagship",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },
    # —— VIP 自选：国际旗舰（次优先）——
    {
        "id": "vip-gpt5",
        "title": "GPT-5",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 9,
        "openrouter_id": "openai/gpt-5",
        "direct_id": None,
        # 2026-08-06: 保持 OR 主通道（补测 TL 同价无成本优势，OR 稳定性更优）
        # 2026-08-11: 加 QuickRouter failover（分组倍率×1 已账单实测 0.625/5.0，成本降 50%）
        "channels": ["quickrouter", "tokenlab", "openrouter"],
        "cost_in": 0.625,
        "cost_out": 5.0,
        "billing_mult": 25,  # 2026-08-05: ceil(5.625/0.35*1.5)=25
        "in_mult": 6,   # 2026-08-06: 6x0.35=$2.10，vs 官方 1.25=1.68x，GM in 40%
        "out_mult": 37,  # 2026-08-06: 37x0.35=$12.95，vs 官方 10=1.30x，GM out 23%
        "quality": "旗舰 · 多项国际评测冠军",
        "quality_en": "Flagship · top benchmarks",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-gpt5-mini", "vip-gpt4o", "vip-ds-pro"],
    },
    {
        "id": "vip-gpt5-mini",
        "title": "GPT-5 mini",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 16,
        "openrouter_id": "openai/gpt-5-mini",
        "direct_id": None,
        # ⚠️ 主脑 2026-08-12：QuickRouter 降本 50% 优先化（×1 倍率实测 0.125/1.0）
        "channels": ["quickrouter", "tokenlab", "openrouter"],
        # 2026-08-11: QuickRouter ×1 实锤 0.125/1.0（原 OR 0.25/2.0）
        "cost_in": 0.125,
        "cost_out": 1.0,
        "billing_mult": 5,
        "in_mult": 2,   # 2026-08-06: 维持 $0.70（mult=1 会跌破毛利线）
        "out_mult": 8,  # 2026-08-06: 8x0.35=$2.80，vs 官方 2=1.40x，GM out 29%
        "quality": "轻量",
        "quality_en": "Lightweight",
        "access": "ready",
        "modalities": ["text"],
        "failover_to": ["vip-gpt4o-mini", "vip-ds-flash"],
    },
    {
        "id": "vip-gpt54",
        "title": "GPT-5.4",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 8,
        "openrouter_id": "openai/gpt-5.4",
        "direct_id": None,
        # 2026-08-06: 主通道切 TokenLab（评测 24/24 vs OR 23/24；TL 实价 in $0.75/out $4.5，约 OR 70% off）
        "channels": ["tokenlab", "openrouter", "requesty"],
        "cost_in": 0.75,    # 2026-08-06: TL 实价（原 2.00 官方/OR）
        "cost_out": 4.50,   # 2026-08-06: TL 实价（原 12.00 官方/OR）
        "billing_mult": 30,  # 2026-08-05: ceil(7.0/0.35*1.5)=32
        "in_mult": 11,   # ceil(2.0/0.35*1.8)=11
        "out_mult": 42,  # ceil(12.0/0.35*1.2)=42
        "quality": "最强",
        "quality_en": "Top tier",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-gpt5", "vip-ds-pro"],
    },
    {
        "id": "vip-gpt4o",
        "title": "GPT-4o",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 17,
        "openrouter_id": "openai/gpt-4o",
        "direct_id": None,
        # 2026-08-06: 主通道切 TokenLab（补测 24/24 持平；TL 与 OR 同价，OR 留作备用）
        "channels": ["tokenlab", "openrouter", "requesty"],
        "cost_in": 2.5,
        "cost_out": 10.0,
        "billing_mult": 27,  # 2026-08-05: ceil(6.25/0.35*1.5)=28
        "in_mult": 11,   # 2026-08-06: 11x0.35=$3.85，vs 官方 2.5=1.54x，GM in 35%
        "out_mult": 40,  # 2026-08-06: 40x0.35=$14.00，GM out 29%
        "quality": "经典",
        "quality_en": "Classic",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-gpt4o-mini", "vip-ds-pro"],
    },
    {
        "id": "vip-gpt4o-mini",
        "title": "GPT-4o mini",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 18,
        "openrouter_id": "openai/gpt-4o-mini",
        "direct_id": None,
        # 2026-08-06: 主通道切 TokenLab（补测 24/24 持平；TL 与 OR 同价）
        "channels": ["tokenlab", "openrouter", "requesty"],
        "cost_in": 0.15,
        "cost_out": 0.6,
        "billing_mult": 2,
        "in_mult": 1,   # ceil(0.15/0.35*1.8)=1
        "out_mult": 3,  # ceil(0.6/0.35*1.2)=3
        "quality": "经典轻量",
        "quality_en": "Classic lightweight",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },
    {
        "id": "vip-claude-sonnet",
        "title": "Claude Sonnet 5",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 11,
        "openrouter_id": "anthropic/claude-sonnet-5",
        "direct_id": None,
        "cost_in": 2.0,
        "cost_out": 10.0,
        "billing_mult": 26,  # 2026-08-05: ceil(6.0/0.35*1.5)=27
        "in_mult": 11,   # ceil(2.0/0.35*1.8)=11
        "out_mult": 35,  # ceil(10.0/0.35*1.2)=35
        "quality": "写作 / 推理",
        "quality_en": "Writing / reasoning",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-claude-haiku", "vip-ds-pro"],
    },
    {
        "id": "vip-claude-haiku",
        "title": "Claude Haiku 4.5",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 14,
        "openrouter_id": "anthropic/claude-haiku-4.5",
        "direct_id": None,
        # 2026-08-14: 主通道切 TokenLab（TL 实价 $0.65/$3.25 为 OR 65%，04 价目监控「降本机会」落地）
        "channels": ["tokenlab", "openrouter", "requesty"],
        "cost_in": 0.65,
        "cost_out": 3.25,
        "billing_mult": 13,  # 2026-08-05: ceil(3.0/0.35*1.5)=14
        "in_mult": 6,   # ceil(1.0/0.35*1.8)=6
        "out_mult": 18,  # ceil(5.0/0.35*1.2)=18
        "quality": "轻量快速",
        "quality_en": "Fast and light",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },
    {
        "id": "vip-claude-opus",
        "title": "Claude Opus 5",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 10,
        "openrouter_id": "anthropic/claude-opus-5",
        "direct_id": None,
        # 2026-08-14: 主通道切 TokenLab（TL 实价 $3.25/$16.25 为 OR 65%，04 价目监控「降本机会」落地）
        "channels": ["tokenlab", "openrouter", "requesty"],
        "cost_in": 3.25,
        "cost_out": 16.25,
        "billing_mult": 65,  # 2026-08-05: ceil(15.0/0.35*1.5)=67
        "in_mult": 26,   # ceil(5.0/0.35*1.8)=26
        "out_mult": 86,  # ceil(25.0/0.35*1.2)=86
        "quality": "顶配",
        "quality_en": "Premium",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-claude-sonnet", "vip-ds-pro"],
    },
    {
        "id": "vip-gemini-pro",
        "title": "Gemini 3.1 Pro",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 12,
        "openrouter_id": "google/gemini-3.1-pro-preview",
        "direct_id": None,
        # 2026-08-06: 主通道切 TokenLab（补测 96% 持平；TL 实价 $1.0/$6.0 为 OR 50%）
        "channels": ["tokenlab", "openrouter", "requesty"],
        "cost_in": 1.0,    # 2026-08-06: TL 实价（原 2.0 = OR）
        "cost_out": 6.0,   # 2026-08-06: TL 实价（原 12.0 = OR）
        "billing_mult": 30,  # 2026-08-05: ceil(7.0/0.35*1.5)=32
        "in_mult": 11,   # ceil(2.0/0.35*1.8)=11
        "out_mult": 42,  # ceil(12.0/0.35*1.2)=42
        "quality": "长上下文",
        "quality_en": "Long context",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-gemini-flash", "vip-ds-pro"],
    },
    {
        "id": "vip-gemini-flash",
        "title": "Gemini 3.6 Flash",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 15,
        "openrouter_id": "google/gemini-3.6-flash",
        "direct_id": None,
        # 2026-08-06: 主通道切 TokenLab（评测 22/24 vs OR 23/24 仅差1题；TL 实价 in $0.75/out $3.75 为 OR 50%，延迟 2.6s < OR 3.5s）
        "channels": ["tokenlab", "openrouter", "requesty"],
        "cost_in": 0.75,    # 2026-08-06: TL 实价（原 1.5 = OR）
        "cost_out": 3.75,   # 2026-08-06: TL 实价（原 7.5 = OR）
        "billing_mult": 20,  # 2026-08-05: ceil(4.5/0.35*1.5)=20
        "in_mult": 8,   # ceil(1.5/0.35*1.8)=8
        "out_mult": 26,  # ceil(7.5/0.35*1.2)=26
        "quality": "轻量长上下文",
        "quality_en": "Light long-context",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-ds-flash", "ds-v4-flash"],
    },
    # —— GPT-5.6 系列（2026-08-03 新增，OR 50% off 渠道成本）——
    {
        "id": "vip-gpt56-terra",
        "title": "GPT-5.6 Terra",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 13,
        "openrouter_id": "openai/gpt-5.6-terra",
        "direct_id": None,
        # 2026-08-06: 主通道切 TokenLab（评测 24/24 vs OR 22/24；TL 实价 in $0.6/out $3.6，比 OR 50% off 更低）
        "channels": ["tokenlab", "openrouter", "requesty"],
        "cost_in": 0.60,    # 2026-08-06: TL 实价（原 1.00 = OR 50% off）
        "cost_out": 3.60,   # 2026-08-06: TL 实价（原 6.00 = OR 50% off）
        "billing_mult": 15,
        "in_mult": 6,   # ceil(1.0/0.35*1.8)=6
        "out_mult": 21,  # ceil(6.0/0.35*1.2)=21
        "quality": "日常旗舰·平衡",
        "quality_en": "Balanced flagship",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-gpt56-luna", "vip-ds-pro"],
    },
    {
        "id": "vip-gpt56-luna",
        "title": "GPT-5.6 Luna",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 20,
        "openrouter_id": "openai/gpt-5.6-luna",
        "direct_id": None,
        # 2026-08-06: 主通道切 TokenLab（补测 24/24 持平且延迟 2.3s < OR 2.8s；TL 实价 $0.06/$0.36 为 OR 60%）
        # ⚠️ 主脑 2026-08-12：QuickRouter 优先（QR 支持 Luna+tools 实测 200，降本+绕 TokenLab 400）
        "channels": ["quickrouter", "openrouter", "tokenlab"],
        "cost_in": 0.06,    # 2026-08-06: TL 实价（原 0.10 = OR）
        "cost_out": 0.36,   # 2026-08-06: TL 实价（原 0.60 = OR）
        "billing_mult": 2,
        "in_mult": 1,   # ceil(0.1/0.35*1.8)=1
        "out_mult": 3,  # ceil(0.6/0.35*1.2)=3
        "quality": "高性价比·智能体",
        "quality_en": "Value agentic",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-gpt5-mini", "vip-ds-flash"],
    },
    {
        # 2026-08-06: Grok 4.20 新增（评测：TL 22/24 · 6.3s ｜ OR 21/24 · 1.8s；TL 实价 in $0.625/out $1.25 为 OR 50%）
        "id": "vip-grok",
        "title": "Grok 4.20",
        "title_en": "Grok 4.20",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 19,
        "openrouter_id": "x-ai/grok-4.20",
        "direct_id": None,
        "channels": ["tokenlab", "openrouter"],
        "cost_in": 0.625,
        "cost_out": 1.25,
        "billing_mult": 20,   # 2026-08-06 定价定案（前沿旗舰档：Terra 15 < Grok 20 < GPT-5.4 30；毛利约 87%）
        "in_mult": 8,
        "out_mult": 30,
        "quality": "前沿旗舰 · 实时信息",
        "quality_en": "Frontier · real-time info",
        "access": "ready",
        "modalities": ["text", "image"],
        "failover_to": ["vip-gpt54", "vip-ds-pro"],
    },
    {
        # 2026-08-06: Llama 4 Maverick 上架（开源旗舰·高性价比；评测 21/24 · 2.7s；OR 实价 in $0.2/out $0.8；仅 OR 有货）
        "id": "vip-llama4",
        "title": "Llama 4",
        "title_en": "Llama 4",
        "brand_tiers": ["vip_pick"],
        "layer": "VIP",
        "role": "vip_pick",
        "priority": 21,
        "openrouter_id": "meta-llama/llama-4-maverick",
        "direct_id": None,
        "channels": ["openrouter"],
        "cost_in": 0.2,
        "cost_out": 0.8,
        "billing_mult": 3,   # 2026-08-06 定价：开源旗舰引流款（毛利约 52%，走量）
        "in_mult": 2,
        "out_mult": 3,
        "quality": "开源旗舰 · 高性价比",
        "quality_en": "Open flagship · value",
        "access": "ready",
        "modalities": ["text"],
        "failover_to": ["vip-gpt5-mini", "vip-ds-flash"],
    },
]


def _load_ov() -> dict[str, Any]:
    try:
        if not _OVERRIDE_PATH.is_file():
            return {}
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_ov(data: dict[str, Any]) -> None:
    _OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def flash_ref_usd_per_m() -> float:
    try:
        v = float((os.getenv("TOKEN_FLASH_REF_USD_PER_M") or "0.35").strip() or "0.35")
        return v if v > 0 else 0.35
    except ValueError:
        return 0.35


def min_markup() -> float:
    """售价相对混合成本的最低加成（默认 1.5 = 约 33% 毛利率量级）。"""
    try:
        v = float((os.getenv("TOKEN_MIN_MARKUP") or "1.5").strip() or "1.5")
        return v if v >= 1.0 else 1.5
    except ValueError:
        return 2.0


def _usd_cny_fx() -> float:
    try:
        fx = float((os.getenv("TOKEN_USD_CNY") or "7.2").strip() or "7.2")
        return fx if fx > 0 else 7.2
    except ValueError:
        return 7.2


def _vip_rates_map() -> dict[str, dict[str, Any]]:
    ov = _load_ov()
    raw = ov.get("vip_rates")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for k, v in raw.items():
        if isinstance(v, dict) and str(k).strip():
            out[str(k).strip()] = v
    return out


def layer_cost_mult_map() -> dict[str, int]:
    base = dict(_DEFAULT_LAYER_MULT)
    ov = _load_ov()
    raw = ov.get("layer_mult")
    if isinstance(raw, dict):
        for ly in ("L2", "L3"):
            if ly not in raw:
                continue
            try:
                n = int(raw[ly])
            except (TypeError, ValueError):
                continue
            if 1 <= n <= 100:
                base[ly] = n
    return base


def layer_cost_mult_for(layer: str) -> int:
    return int(layer_cost_mult_map().get(str(layer or "").upper(), 1) or 1)


def suggest_billing_mult(*, cost_in: float, cost_out: float) -> int:
    """ceil(blended / flash_ref × min_markup)，至少 1。"""
    blended = (float(cost_in or 0) + float(cost_out or 0)) / 2.0
    ref = flash_ref_usd_per_m()
    mk = min_markup()
    if blended <= 0 or ref <= 0:
        return 1
    import math

    return max(1, int(math.ceil(blended / ref * mk)))


def _append_pricing_audit(entry: dict[str, Any]) -> None:
    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with _AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def merge_catalog_row(c: dict[str, Any]) -> dict[str, Any]:
    """CATALOG 行 + override（vip_rates / 成本与倍率）。"""
    row = deepcopy(c)
    if row.get("role") == "vip_pick":
        ov = _vip_rates_map().get(str(row.get("id") or "")) or {}
        if "billing_mult" in ov:
            try:
                row["billing_mult"] = max(1, min(200, int(ov["billing_mult"])))
            except (TypeError, ValueError):
                pass
        if "cost_in" in ov:
            try:
                row["cost_in"] = float(ov["cost_in"])
            except (TypeError, ValueError):
                pass
        if "cost_out" in ov:
            try:
                row["cost_out"] = float(ov["cost_out"])
            except (TypeError, ValueError):
                pass
        if "enabled" in ov:
            row["pick_enabled"] = bool(ov["enabled"])
        else:
            row["pick_enabled"] = True
        if "in_mult" in ov:
            try:
                row["in_mult"] = max(1, min(200, int(ov["in_mult"])))
            except (TypeError, ValueError):
                pass
        if "out_mult" in ov:
            try:
                row["out_mult"] = max(1, min(200, int(ov["out_mult"])))
            except (TypeError, ValueError):
                pass
        # 双价兜底：缺 in/out 倍率时回落 billing_mult（单费率兼容）
        if isinstance(ov.get("channels"), list) and ov["channels"]:
            row["channels"] = [str(x).strip() for x in ov["channels"] if str(x).strip()]
        row.setdefault("in_mult", row.get("billing_mult", 1))
        row.setdefault("out_mult", row.get("billing_mult", 1))
        row["rate_source"] = "admin" if ov else "catalog"
    else:
        row["pick_enabled"] = True
        row["rate_source"] = "catalog"
    return row


def catalog_merged() -> list[dict[str, Any]]:
    return [merge_catalog_row(c) for c in CATALOG]


def _assert_vip_margin_ok(
    *,
    cid: str,
    billing_mult: int,
    cost_in: float,
    cost_out: float,
) -> None:
    blended = (float(cost_in or 0) + float(cost_out or 0)) / 2.0
    if blended <= 0:
        return
    sell = flash_ref_usd_per_m() * max(1, int(billing_mult))
    floor = blended * min_markup()
    if sell + 1e-9 < floor:
        raise ValueError(
            f"{cid}: 估售价 ${sell:.4g}/M 低于成本地板 ${floor:.4g}/M"
            f"（混合成本 ${blended:.4g} × 最低加成 {min_markup():.2g}），请提高倍率或核对成本。"
        )


def layer_model_override(layer: str) -> Optional[str]:
    ov = _load_ov()
    layers = ov.get("layers") if isinstance(ov.get("layers"), dict) else {}
    row = layers.get(str(layer).upper()) if isinstance(layers, dict) else None
    if not isinstance(row, dict):
        return None
    m = (row.get("model") or "").strip()
    return m or None


def vip_pick_enabled() -> bool:
    ov = _load_ov()
    if "vip_pick_enabled" in ov:
        return bool(ov.get("vip_pick_enabled"))
    return True  # 默认开：高阶 VIP 可点名中国模


def vip_channel_order(public_id: str) -> Optional[list[str]]:
    """VIP 点名聚合通道顺序（openrouter/tokenlab/requesty 子集）；未配置返回 None（默认 OR → TokenLab → Requesty）。"""
    cid = str(public_id or "").strip()
    for c in catalog_merged():
        if str(c.get("id") or "") != cid or c.get("role") != "vip_pick":
            continue
        ch = c.get("channels")
        if isinstance(ch, list) and ch:
            return [str(x).strip() for x in ch if str(x).strip()]
        return None
    return None


def resolve_vip_pick(requested_model: Optional[str]) -> Optional[dict[str, Any]]:
    """若请求是 VIP 点名模，返回合并后的目录行（含 openrouter_id / billing_mult）；否则 None。"""
    raw = (requested_model or "").strip()
    if not raw:
        return None
    key = raw.lower()
    # 去掉常见前缀
    for prefix in ("vip:", "vip-", "named:", "pick:"):
        if key.startswith(prefix):
            key = key[len(prefix) :].lstrip("-:")
            break
    aliases = {
        "kimi": "vip-kimi",
        "moonshot": "vip-kimi",
        "kimi-k2": "vip-kimi",
        "kimi-k3": "vip-kimi",
        "kimi3": "vip-kimi",
        "kimi-3": "vip-kimi",
        "kimi-code": "vip-kimi-code",
        "kimi-k2.7": "vip-kimi-code",
        "kimi-k2.7-code": "vip-kimi-code",
        "kimi27": "vip-kimi-code",
        "mimo": "vip-mimo",
        "xiaomi-mimo": "vip-mimo",
        "xiaomi": "vip-mimo",
        "minimax": "vip-minimax",
        "minimax-m2": "vip-minimax",
        "minimax-m3": "vip-minimax",
        "glm": "vip-glm",
        "glm-5": "vip-glm",
        "glm-5.2": "vip-glm",
        "zhipu": "vip-glm",
        "zhipu-glm": "vip-glm",
        "qwen": "vip-qwen-max",
        "qwen-max": "vip-qwen-max",
        "qwen3": "vip-qwen-max",
        "qwen122b": "vip-qwen122b",
        "qwen-122b": "vip-qwen122b",
        "qwen3.5": "vip-qwen122b",
        "deepseek": "vip-ds-flash",
        "deepseek-flash": "vip-ds-flash",
        "deepseek-v4-flash": "vip-ds-flash",
        "deepseek-pro": "vip-ds-pro",
        "deepseek-v4-pro": "vip-ds-pro",
        "ds-flash": "vip-ds-flash",
        "ds-pro": "vip-ds-pro",
        "gpt5": "vip-gpt5",
        "gpt-5": "vip-gpt5",
        "openai": "vip-gpt5",
        "gpt": "vip-gpt5",
        "gpt5-mini": "vip-gpt5-mini",
        "gpt-5-mini": "vip-gpt5-mini",
        "gpt54": "vip-gpt54",
        "gpt-5.4": "vip-gpt54",
        "gpt5.4": "vip-gpt54",
        "gpt4o": "vip-gpt4o",
        "gpt-4o": "vip-gpt4o",
        "gpt4o-mini": "vip-gpt4o-mini",
        "gpt-4o-mini": "vip-gpt4o-mini",
        "claude": "vip-claude-sonnet",
        "claude-sonnet": "vip-claude-sonnet",
        "claude-sonnet-5": "vip-claude-sonnet",
        "sonnet": "vip-claude-sonnet",
        "sonnet-5": "vip-claude-sonnet",
        "claude-haiku": "vip-claude-haiku",
        "claude-haiku-4.5": "vip-claude-haiku",
        "haiku": "vip-claude-haiku",
        "haiku-4.5": "vip-claude-haiku",
        "claude-opus": "vip-claude-opus",
        "claude-opus-5": "vip-claude-opus",
        "opus": "vip-claude-opus",
        "opus-5": "vip-claude-opus",
        "gemini": "vip-gemini-pro",
        "gemini-pro": "vip-gemini-pro",
        "gemini-3": "vip-gemini-pro",
        "gemini-flash": "vip-gemini-flash",
        # 2026-08-06: 补版本号自然名（副脑04 验收发现 gemini-3.6-flash 点名 miss 落 L1）
        "gemini-3.6-flash": "vip-gemini-flash",
        "gemini-3.6": "vip-gemini-flash",
        "gemini-3.1-pro": "vip-gemini-pro",
        "gemini-3.1-pro-preview": "vip-gemini-pro",
        "gemini-3.1": "vip-gemini-pro",
        # GPT-5.6 系列（2026-08-03）
        "gpt56": "vip-gpt56-terra",
        "gpt-5.6": "vip-gpt56-terra",
        "gpt5.6": "vip-gpt56-terra",
        "gpt56-terra": "vip-gpt56-terra",
        "gpt-5.6-terra": "vip-gpt56-terra",
        "terra": "vip-gpt56-terra",
        "gpt56-luna": "vip-gpt56-luna",
        "gpt-5.6-luna": "vip-gpt56-luna",
        "luna": "vip-gpt56-luna",
        "grok": "vip-grok",
        "grok-4": "vip-grok",
        "grok-4.20": "vip-grok",
        "grok4": "vip-grok",
        "x-ai": "vip-grok",
        "llama": "vip-llama4",
        "llama-4": "vip-llama4",
        "llama-4-maverick": "vip-llama4",
        "llama4": "vip-llama4",
        "hy3": "vip-hy3",
        "hy-3": "vip-hy3",
        "tencent": "vip-hy3",
        "tencent-hy3": "vip-hy3",
    }
    cid = aliases.get(key, key if key.startswith("vip-") else "")
    if not cid:
        # 直接匹配 catalog id
        cid = key if any(c["id"] == key for c in CATALOG) else ""
    if not cid:
        return None
    for c in catalog_merged():
        if c.get("role") != "vip_pick":
            continue
        if str(c.get("id")) != cid:
            continue
        if c.get("pick_enabled") is False:
            return None
        if not c.get("openrouter_id") and not c.get("direct_id"):
            return None
        return dict(c)
    return None


def list_vip_picks_for_user(
    *, is_vip: bool, allow_names: Optional[set[str]] = None
) -> list[dict[str, Any]]:
    """控制台可选点名列表（中国模优先）。非 VIP 也返回目录但 locked。"""
    enabled = vip_pick_enabled()
    allow_names = set(allow_names or ())
    fx = _usd_cny_fx()
    ref_usd_per_m = flash_ref_usd_per_m()
    out = []
    for c in sorted(
        [x for x in catalog_merged() if x.get("role") == "vip_pick" and x.get("pick_enabled") is not False],
        key=lambda x: int(x.get("priority") or 99),
    ):
        # 国际旗舰次优先：仍列出，标注 intl
        is_intl = str(c.get("id") or "").startswith("vip-gpt") or "claude" in str(
            c.get("id")
        ) or "gemini" in str(c.get("id") or "") or "grok" in str(c.get("id") or "") or "llama" in str(c.get("id") or "")
        mult = int(c.get("billing_mult") or 1)
        in_mult = int(c.get("in_mult") or c.get("billing_mult") or 1)
        out_mult = int(c.get("out_mult") or c.get("billing_mult") or 1)
        est_usd = round(ref_usd_per_m * mult, 2)
        est_in_usd = round(ref_usd_per_m * in_mult, 2)
        est_out_usd = round(ref_usd_per_m * out_mult, 2)
        est_cny = int(round(est_usd * fx))
        est_in_cny = int(round(est_in_usd * fx))
        est_out_cny = int(round(est_out_usd * fx))
        out.append(
            {
                "id": c["id"],
                "title": c.get("title") or c["id"],
                "title_en": c.get("title_en") or c.get("title") or c["id"],
                "model": c["id"],
                "billing_mult": mult,
                "in_mult": in_mult,
                "out_mult": out_mult,
                "est_in_usd_per_m": est_in_usd,
                "est_out_usd_per_m": est_out_usd,
                "est_in_cny_per_m": est_in_cny,
                "est_out_cny_per_m": est_out_cny,
                # 短标签给用户看；勿塞运维备注
                "blurb": c.get("quality") or "",
                "blurb_en": c.get("quality_en") or c.get("quality") or "",
                "group": "intl" if is_intl else "china",
                "locked": (not (is_vip or (str(c["id"]) in allow_names))) or (not enabled),
                "value_pack_ok": str(c["id"]) in allow_names,
                "enabled_platform": enabled,
                "est_usd_per_m": est_usd,
                "est_cny_per_m": est_cny,
                "est_basis": "flash_anchor",
                "flash_ref_usd_per_m": ref_usd_per_m,
                "modalities": c.get("modalities") or ["text"],
            }
        )
    return out


def vip_pick_models() -> list[str]:
    ov = _load_ov()
    raw = ov.get("vip_pick_models")
    if isinstance(raw, list) and raw:
        return [str(x).strip() for x in raw if str(x).strip()]
    return [
        str(c["openrouter_id"])
        for c in catalog_merged()
        if c.get("role") == "vip_pick"
        and c.get("pick_enabled") is not False
        and c.get("openrouter_id")
    ]


def _blended(c: dict[str, Any]) -> float:
    return round((float(c.get("cost_in") or 0) + float(c.get("cost_out") or 0)) / 2.0, 4)


def warehouse_snapshot() -> dict[str, Any]:
    from model_router import (
        CHAIN_FREE,
        CHAIN_VIP,
        _OR_DEFAULT_MODELS,
        _layer_upstream,
        _upstream_mode,
        list_models_public,
    )
    from token_plans import list_public_plans

    mode = _upstream_mode()
    ov = _load_ov()
    layer_ov = ov.get("layers") if isinstance(ov.get("layers"), dict) else {}

    layers_live: dict[str, Any] = {}
    for ly in ("L0", "L1", "L2", "L3", "QI"):
        info = _layer_upstream(ly)
        ov_model = None
        if isinstance(layer_ov.get(ly), dict):
            ov_model = (layer_ov[ly].get("model") or "").strip() or None
        enabled = True
        if isinstance(layer_ov.get(ly), dict) and "enabled" in layer_ov[ly]:
            enabled = bool(layer_ov[ly]["enabled"])
        layers_live[ly] = {
            "layer": ly,
            "provider": info.get("provider"),
            "model": ov_model or info.get("model"),
            "default_model": _OR_DEFAULT_MODELS.get(ly) if mode == "openrouter" else info.get("model"),
            "key_set": bool(info.get("key")),
            "enabled": enabled,
            "source": "admin" if ov_model else "env/default",
        }

    pub = list_models_public(is_vip=True)
    brand_rows = []
    brand_layer = {"auto": "L1", "flash": "L1", "pro": "L2", "ultra": "L3"}
    for bid, title in (pub.get("brand") or {}).items():
        layer = brand_layer.get(bid, "L1")
        live = layers_live.get(layer) or {}
        brand_rows.append(
            {
                "brand": bid,
                "title": title,
                "maps_to_layer": layer,
                "upstream_model": live.get("model") or "—",
                "chain_free": " → ".join(CHAIN_FREE),
                "chain_vip": " → ".join(CHAIN_VIP),
            }
        )

    catalog_out = []
    ref = flash_ref_usd_per_m()
    mk = min_markup()
    for c in catalog_merged():
        row = deepcopy(c)
        blended = _blended(row)
        row["cost_blended_usd_per_m"] = blended
        ly = str(c.get("layer") or "")
        live = layers_live.get(ly) or {}
        key_ok = bool(live.get("key_set")) if ly in layers_live else False
        # 接入状态：规划 / 缺 Key / 在线路由中
        access = str(c.get("access") or "planned")
        if access == "planned":
            runtime = "planned"
        elif ly == "VIP":
            if not vip_pick_enabled() or row.get("pick_enabled") is False:
                runtime = "vip_pick_off"
            else:
                runtime = "ready" if key_ok else "need_key"
        elif key_ok and live.get("enabled", True):
            # 当前层实际模型是否匹配
            cur_m = str(live.get("model") or "")
            want = str(c.get("openrouter_id") or c.get("direct_id") or "")
            runtime = "active" if want and want in cur_m else "standby"
        elif key_ok:
            runtime = "disabled"
        else:
            runtime = "need_key"
        row["runtime"] = runtime
        mult = int(row.get("billing_mult") or (1 if ly != "VIP" else 10))
        row["billing_mult"] = mult
        if row.get("role") == "vip_pick":
            est_sell = round(ref * mult, 4)
            row["est_sell_usd_per_m"] = est_sell
            row["suggest_billing_mult"] = suggest_billing_mult(
                cost_in=float(row.get("cost_in") or 0),
                cost_out=float(row.get("cost_out") or 0),
            )
            if blended > 0:
                row["est_margin_pct"] = round((1.0 - blended / est_sell) * 100.0, 1) if est_sell > 0 else None
                row["cost_floor_usd_per_m"] = round(blended * mk, 4)
            else:
                row["est_margin_pct"] = None
                row["cost_floor_usd_per_m"] = 0.0
        catalog_out.append(row)

    plans = list_public_plans()
    plan_margin = []
    flash_row = next((x for x in catalog_merged() if x["id"] == "ds-v4-flash"), None)
    flash_cost = _blended(flash_row) if flash_row else 0.21
    for p in plans:
        tokens = int(p.get("credit_tokens") or 0)
        usd = float(p.get("price_usd") or 0) if p.get("price_usd") else None
        if usd is None and p.get("price_fen"):
            usd = round(int(p["price_fen"]) / 100.0 / 7.2, 4)
        est_cost = round((tokens / 1_000_000.0) * flash_cost, 4) if tokens else None
        margin = round((usd or 0) - (est_cost or 0), 4) if usd is not None and est_cost is not None else None
        plan_margin.append(
            {
                "plan": p.get("plan"),
                "title": p.get("title_zh") or p.get("title"),
                "price_usd": usd,
                "price_fen": p.get("price_fen"),
                "credit_tokens": tokens,
                "est_upstream_if_all_flash_usd": est_cost,
                "est_gross_usd": margin,
                "note": "毛利按 Flash 混合成本粗算；实际随档位/用量变",
            }
        )

    failover = {
        "free_chain": CHAIN_FREE,
        "vip_chain": CHAIN_VIP,
        "note": "层内失败自动下一档；OR↔直连不自动切换，须改上游模式。",
        "mode": mode,
        "risks": [
            {
                "if_down": "L1 Flash",
                "then": "FREE→L0（硅基/OR auto）；VIP→L2 Pro",
                "mitigation": "配齐 SILICONFLOW 或 OR L0",
            },
            {
                "if_down": "OpenRouter 整站",
                "then": "改上游模式=direct + DeepSeek Key",
                "mitigation": "管理台一键切 direct（须已配 DeepSeek）",
            },
            {
                "if_down": "DeepSeek 直连",
                "then": "切回 openrouter",
                "mitigation": "保持 OR Key 有余额",
            },
        ],
    }

    lm = layer_cost_mult_map()
    return {
        "ok": True,
        "upstream_mode": mode,
        "brand_map": brand_rows,
        "layers": layers_live,
        "catalog": catalog_out,
        "failover": failover,
        "plans_margin": plan_margin,
        "pricing": {
            "flash_ref_usd_per_m": ref,
            "min_markup": mk,
            "layer_mult": lm,
            "note": (
                "估售价 ≈ flash_ref × billing_mult；"
                "保存 VIP 费率时若估售价 < 混合成本 × min_markup 则拒绝。"
                "建议倍率 = ceil(混合成本 / flash_ref × min_markup)。"
            ),
        },
        "vip_pick": {
            "enabled": vip_pick_enabled(),
            "models": vip_pick_models(),
            "note": (
                "VIP 点名已上线：中国模有 siliconflow_id 时默认硅基优先（TOKEN_LLM_VIP_SILICON_FIRST）；"
                "国际旗舰走 OR/厂直连。扣费 = 上游用量 × billing_mult（相对 flash 锚）。"
            ),
        },
        "routing_flags": {
            "vip_silicon_first": _env_flag("TOKEN_LLM_VIP_SILICON_FIRST", True),
            "ds_prefer_paid": _env_flag("TOKEN_LLM_DS_PREFER_PAID", True),
            "layer_cost_mult": {"L2": lm.get("L2", 3), "L3": lm.get("L3", 6)},
            "vip_daily_models": "flash,auto,shared",
            "note": "L2/L3 倍率可在本页保存；VIP硅基/DS优先等开关改 .env + 重启。",
        },
        "ops_note": (
            "付费仓：改层 model、VIP 成本/倍率后保存即生效（人审，无自动跟价）。"
            "容灾 FREE：L1→L0；VIP 点名：硅基/OR/厂直连。"
            f"pro/ultra 层倍率 L2×{lm.get('L2', 3)} / L3×{lm.get('L3', 6)}。与免费共享池独立。"
        ),
    }


def update_warehouse(patch: dict[str, Any], *, actor: str = "admin") -> dict[str, Any]:
    from datetime import datetime, timezone

    cur = _load_ov()
    layers = dict(cur.get("layers") or {}) if isinstance(cur.get("layers"), dict) else {}
    audit_changes: list[dict[str, Any]] = []

    for item in patch.get("layers") or []:
        if not isinstance(item, dict):
            continue
        ly = str(item.get("layer") or "").strip().upper()
        if ly not in ("L0", "L1", "L2", "L3", "QI"):
            continue
        row = dict(layers.get(ly) or {})
        if item.get("model") is not None:
            m = str(item.get("model") or "").strip()
            if m:
                row["model"] = m
            elif "model" in row:
                del row["model"]
        if item.get("enabled") is not None:
            row["enabled"] = bool(item["enabled"])
        layers[ly] = row

    cur["layers"] = layers
    if patch.get("vip_pick_enabled") is not None:
        cur["vip_pick_enabled"] = bool(patch["vip_pick_enabled"])
    if patch.get("vip_pick_models") is not None:
        cur["vip_pick_models"] = [
            str(x).strip() for x in (patch.get("vip_pick_models") or []) if str(x).strip()
        ][:32]
    if patch.get("note") is not None:
        cur["note"] = str(patch.get("note") or "")[:200]

    # 品牌层倍率（仅 L2/L3）
    if isinstance(patch.get("layer_mult"), dict):
        lm = dict(cur.get("layer_mult") or {}) if isinstance(cur.get("layer_mult"), dict) else {}
        old_lm = dict(lm)
        for ly in ("L2", "L3"):
            if ly not in patch["layer_mult"]:
                continue
            try:
                n = int(patch["layer_mult"][ly])
            except (TypeError, ValueError):
                raise ValueError(f"layer_mult.{ly} 无效")
            if not (1 <= n <= 100):
                raise ValueError(f"layer_mult.{ly} 须在 1～100")
            lm[ly] = n
        cur["layer_mult"] = lm
        if lm != old_lm:
            audit_changes.append({"field": "layer_mult", "old": old_lm, "new": lm})

    # VIP 费率覆盖
    if patch.get("vip_rates") is not None:
        if not isinstance(patch.get("vip_rates"), list):
            raise ValueError("vip_rates 须为数组")
        rates = dict(cur.get("vip_rates") or {}) if isinstance(cur.get("vip_rates"), dict) else {}
        base_by_id = {str(c["id"]): c for c in CATALOG if c.get("role") == "vip_pick"}
        for item in patch["vip_rates"]:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id") or "").strip()
            if not cid or cid not in base_by_id:
                raise ValueError(f"未知 VIP 模型 id：{cid or '（空）'}")
            base = base_by_id[cid]
            old = dict(rates.get(cid) or {})
            new_row = dict(old)
            if "billing_mult" in item and item["billing_mult"] is not None:
                try:
                    new_row["billing_mult"] = max(1, min(200, int(item["billing_mult"])))
                except (TypeError, ValueError):
                    raise ValueError(f"{cid}: billing_mult 无效")
            if "cost_in" in item and item["cost_in"] is not None:
                try:
                    new_row["cost_in"] = float(item["cost_in"])
                except (TypeError, ValueError):
                    raise ValueError(f"{cid}: cost_in 无效")
            if "cost_out" in item and item["cost_out"] is not None:
                try:
                    new_row["cost_out"] = float(item["cost_out"])
                except (TypeError, ValueError):
                    raise ValueError(f"{cid}: cost_out 无效")
            if "enabled" in item and item["enabled"] is not None:
                new_row["enabled"] = bool(item["enabled"])

            mult = int(
                new_row.get("billing_mult")
                if "billing_mult" in new_row
                else (base.get("billing_mult") or 1)
            )
            cin = float(
                new_row["cost_in"] if "cost_in" in new_row else (base.get("cost_in") or 0)
            )
            cout = float(
                new_row["cost_out"] if "cost_out" in new_row else (base.get("cost_out") or 0)
            )
            # 仅启用时做毛利护栏
            if new_row.get("enabled", True) is not False:
                _assert_vip_margin_ok(
                    cid=cid, billing_mult=mult, cost_in=cin, cost_out=cout
                )
            rates[cid] = new_row
            if new_row != old:
                audit_changes.append(
                    {"id": cid, "old": old or None, "new": new_row}
                )
        cur["vip_rates"] = rates

    _save_ov(cur)
    if audit_changes:
        _append_pricing_audit(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "actor": str(actor or "admin")[:64],
                "changes": audit_changes[:64],
            }
        )
    return warehouse_snapshot()
