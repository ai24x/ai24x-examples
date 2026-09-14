# curl Examples: AI24X Gateway API

## Chat Completion

```bash
curl -X POST "https://api.ai24x.com/v1/chat/completions" \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "flash",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is an AI gateway?"}
    ]
  }'
```

## Streaming

```bash
curl -X POST "https://api.ai24x.com/v1/chat/completions" \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "flash",
    "messages": [{"role": "user", "content": "Count to 5."}],
    "stream": true
  }'
```

## List Models

```bash
curl -s "https://api.ai24x.com/v1/models" \
  -H "Authorization: Bearer sk-..." | jq '.data[] | {id, owned_by}'
```

## DeepSeek Pro (stronger reasoning)

```bash
curl -X POST "https://api.ai24x.com/v1/chat/completions" \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "pro",
    "messages": [{"role": "user", "content": "Solve: 27 × 43 + 15 = ?"}]
  }'
```

## BYOK Endpoint

```bash
curl -X POST "https://open.ai24x.com/v1/chat/completions" \
  -H "Authorization: Bearer sk-byok-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello from BYOK!"}]
  }'
```

See full docs at [open.ai24x.com](https://open.ai24x.com)
