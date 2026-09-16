#!/bin/bash
# Compare model responses via curl
# Requires jq: https://jqlang.github.io/jq/

API_KEY="sk-your-key-here"
PROMPT="Explain what an AI gateway is in two sentences."
ENDPOINT="https://api.ai24x.com/v1/chat/completions"

models=("flash" "auto" "pro" "vip-gpt5" "vip-claude-sonnet" "vip-ds-flash" "vip-qwen-max")

for model in "${models[@]}"; do
  start=$(date +%s%N)
  
  response=$(curl -s "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_KEY" \
    -d "{
      \"model\": \"$model\",
      \"messages\": [{\"role\": \"user\", \"content\": \"$PROMPT\"}],
      \"max_tokens\": 100
    }")
  
  end=$(date +%s%N)
  elapsed=$(( (end - start) / 1000000 ))
  
  content=$(echo "$response" | jq -r '.choices[0].message.content // "error"')
  echo "$model ($elapsed ms): $content"
  echo ""
done