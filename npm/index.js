const OpenAI = require("openai");

const AI24X_BASE_URL = "https://api.ai24x.com/v1";

function createClient(options = {}) {
  return new OpenAI({
    baseURL: AI24X_BASE_URL,
    ...options,
  });
}

const MODELS = {
  FLASH: "flash",
  AUTO: "auto",
  PRO: "pro",
  ULTRA: "ultra",
  SHARED: "shared",
  DEEPSEEK_FLASH: "vip-ds-flash",
  DEEPSEEK_PRO: "vip-ds-pro",
  QWEN_MAX: "vip-qwen-max",
  QWEN_122B: "vip-qwen122b",
  GPT6_ASTRA: "vip-gpt6-astra",
  GPT56_TERRA: "vip-gpt56-terra",
  GPT56_SOL: "vip-gpt56-sol",
  GPT56_LUNA: "vip-gpt56-luna",
  GPT5: "vip-gpt5",
  GPT5_MINI: "vip-gpt5-mini",
  CLAUDE_OPUS: "vip-claude-opus",
  CLAUDE_SONNET: "vip-claude-sonnet",
  CLAUDE_HAIKU: "vip-claude-haiku",
  GEMINI_PRO: "vip-gemini-pro",
  GEMINI_FLASH: "vip-gemini-flash",
  GROK: "vip-grok",
  LLAMA4: "vip-llama4",
  MIMO: "vip-mimo",
  KIMI: "vip-kimi",
  GLM: "vip-glm",
};

module.exports = { createClient, MODELS, AI24X_BASE_URL };
