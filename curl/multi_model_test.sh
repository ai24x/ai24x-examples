#!/bin/bash
# Compare model responses via curl
# Requires jq: https://jqlang.github.io/jq/

API_KEY="sk-your-key-here"
PROMPT="Explain what an AI gateway is in two sentences."
ENDPOINT="https://api.ai24x.com/v1/chat/completions"

models=("flash" "pro" "vip-gpt5" "vip-claude-sonnet" "vip-ds-flash" "vip-qwen-max")

for model in ""; do
  start=
  response=
  end=
  elapsed=
  
  content=
  echo " (s): "
done