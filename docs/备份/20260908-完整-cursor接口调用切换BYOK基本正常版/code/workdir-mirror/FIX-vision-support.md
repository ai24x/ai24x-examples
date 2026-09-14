# FIX: OpenAI 兼容层 Vision（多模态/图片）支持

> 主脑诊断 + 直接修复 · 2026-08-04 07:44~07:53 · 更新 12:30
> ⚠️ **科设注意：此文件已由主脑直接修改并部署04生产。Gitee 同步时请保留此改动！**

## 🚨 重要更新（2026-08-04 12:30）：DeepSeek V4 官方 API 不支持读图

**结论：DeepSeek 官方 API（deepseek-v4-flash 0731 / deepseek-v4-pro）是纯文本模型，不支持图片/多模态输入。**

三重证据：
1. **官方文档**（8/4 抓取 api-docs.deepseek.com）：模型能力表只有 JSON 输出 / 工具调用 / Responses API / Anthropic API / 补全，**无 Vision 项**；`/guides/vision` 页面 404。
2. **平台透传实测**：图片数据成功透传上游（prompt_tokens 49→189 证明图已到上游），但 DeepSeek 回复 *"I can't see images, as I'm a text-based assistant"*。
3. **历史事故实锤**：8/3 曾给 DeepSeek 配置加 image 声明 → 官方 API 拒绝请求格式（provider rejected the request schema）→ 代理全挂。

**对 vision 修复的影响：** 平台兼容层修好透传（本文件下方内容）只是第一步；**上游模型必须换成支持 vision 的模型**（如 Qwen-VL、Kimi Vision、GPT-4o 等）才能真正读图。纯 DeepSeek 上游读不了。

**当前可用方案：** 主脑侧已配置 Kimi Vision（moonshot-v1-8k-vision-preview）作为图片理解引擎（OpenClaw tools.media.image），飞书发图 → Kimi Vision 转文字 → 主会话 DeepSeek 理解。实测 Kimi 能准确读出图片内容（支付截图金额/汇率/支付方式全对）。

---

## 原修复内容（兼容层透传）

>
> - 本地源码：`E:\AI24X\ai24x-website\ai24x01\api\openai_compat.py` ✅ 已修改
> - 备份文件：`openai_compat.py.bak.20260804`（修改前原版）
> - 04 生产：`C:\ai24x01\api\openai_compat.py` ✅ 已同步部署
> - 04 备份：`C:\ai24x01\api\openai_compat.py.bak.20260804`（04侧原版，需手动确认）
> - 实测验证：curl vision 请求 → prompt_tokens 43→153，模型正确响应 ✅

## 问题

**症状：** 调用平台 `/v1/chat/completions`，用 multipart content（text + image_url）发图片，返回 200 OK，但模型回复"I can't see any image"。

**实测：** 主脑 curl 平台 Flash 发图 → `"content": "I can't see any image in this chat."`（prompt_tokens 仅 43，图片数据根本没到上游）

## 根因

`api/openai_compat.py` 的 `_content_to_text()` 函数把图片数据丢弃了：

```python
# 第 ~97 行 — 当前实现
def _content_to_text(content: Any) -> str:
    ...
    if isinstance(content, list):
        for p in content:
            ...
            elif p.get("type") == "image_url":
                parts.append("[image]")  # ❌ 图的 base64 直接丢弃！
```

然后 `normalize_messages_for_upstream()` 调用 `_content_to_text()`，最后强制把 content 转成纯字符串：

```python
# 第 ~170 行
out.append({"role": role, "content": text})  # ❌ 永远是 string，丢掉了 list 结构
```

**结果：** 兼容层把 `[{"type":"text","text":"..."}, {"type":"image_url",...}]` 拍扁成了 `"...\n[image]"` 纯文本，发给上游 OpenRouter 的 DeepSeek 时图片早已消失。

## 修复方案

### 1. `_content_to_text()` — 不改（保持现有行为，给账本/回退用）

这个函数目前被 `messages_to_prompt()` 用于转成纯文本 prompt（账本、回退等场景），保持现有逻辑不变即可。

### 2. 新增 `_normalize_content_for_upstream()` 函数

```python
def _normalize_content_for_upstream(content: Any) -> Any:
    """保留 multipart 结构（含 image_url）供上游透传。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[Dict[str, Any]] = []
        for p in content:
            if isinstance(p, str):
                parts.append({"type": "text", "text": p})
            elif isinstance(p, dict):
                tp = str(p.get("type") or "").strip().lower()
                if tp == "image_url":
                    # 原样保留图片数据
                    parts.append(p)
                elif tp == "text" or "text" in p:
                    parts.append({"type": "text", "text": str(p.get("text") or "")})
                else:
                    # 未知类型，safe fallback
                    parts.append(p)
        return parts if parts else ""
    return str(content)
```

### 3. 修改 `normalize_messages_for_upstream()`

把消息中的 content 处理从 `_content_to_text()` 改为 `_normalize_content_for_upstream()`：

```python
# 改前：
text = _content_to_text(m.get("content")).strip()
...
out.append({"role": role, "content": text})

# 改后：
content = _normalize_content_for_upstream(m.get("content"))
if isinstance(content, str) and not content.strip():
    continue
...
out.append({"role": role, "content": content})
```

### 4. tool/function 角色同理

tool/function 角色的 content 也需跟着改（当前也是 `_content_to_text`）。

## 验证

修完后用 curl 测试：

```bash
curl -X POST https://api.ai24x.com/v1/chat/completions \
  -H "Authorization: Bearer <test_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "flash",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "What is in this image?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
      ]
    }]
  }'
```

**期望：** 返回能准确描述图片内容的文本（而不是"I can't see any image"）。

## 影响面

- `_content_to_text()` 保持不变（账本/回退路径不受影响）
- 仅上游透传路径 `normalize_messages_for_upstream()` 受益于新函数
- 不影响纯文本对话（`content` 为 `str` 时行为不变）
- `messages_to_prompt()` 仍然调用 `_content_to_text()`，关系不变
