#!/bin/bash
# Basic curl examples for AI24X Gateway

# 1. Simple chat completion
curl -s https://api.ai24x.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-key-here" \
  -d '{
    "model": "flash",
    "messages": [{"role": "user", "content": "Hello! What can you do?"}],
    "max_tokens": 200
  }' | jq .

# 2. Try different models
for model in flash auto pro vip-gpt5 vip-claude-sonnet vip-ds-flash; do
  echo "=== $model ==="
  curl -s https://api.ai24x.com/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer sk-your-key-here" \
    -d "{
      \"model\": \"$model\",
      \"messages\": [{\"role\": \"user\", \"content\": \"What is the capital of Japan?\"}],
      \"max_tokens\": 50
    }" | jq '.choices[0].message.content'
done

# 3. Streaming example
curl -s -N https://api.ai24x.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-key-here" \
  -d '{
    "model": "flash",
    "messages": [{"role": "user", "content": "Count from 1 to 5."}],
    "stream": true
  }'