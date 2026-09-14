// Basic chat completion using AI24X Gateway (Node.js)
const OpenAI = require("openai");

const client = new OpenAI({
  baseURL: "https://api.ai24x.com/v1",
  apiKey: "sk-your-key-here",
});

async function main() {
  const models = ["flash", "pro", "vip-gpt5", "vip-claude-sonnet"];

  for (const model of models) {
    const response = await client.chat.completions.create({
      model,
      messages: [{ role: "user", content: "What is an AI gateway? Answer in one sentence." }],
      max_tokens: 100,
    });
    console.log([] );
  }
}

main().catch(console.error);