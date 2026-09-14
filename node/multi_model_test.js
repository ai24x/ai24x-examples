// Test multiple models on the same prompt (Node.js)
const OpenAI = require("openai");

const client = new OpenAI({
  baseURL: "https://api.ai24x.com/v1",
  apiKey: "sk-your-key-here",
});

async function main() {
  const prompt = "Explain what an AI gateway is in two sentences.";
  const models = [
    { id: "flash", label: "Fast tier" },
    { id: "pro", label: "Value tier" },
    { id: "vip-gpt56-luna", label: "GPT Luna" },
    { id: "vip-gemini-flash", label: "Gemini Flash" },
  ];

  console.log(Prompt: \n);
  for (const { id, label } of models) {
    const start = Date.now();
    try {
      const response = await client.chat.completions.create({
        model: id,
        messages: [{ role: "user", content: prompt }],
        max_tokens: 150,
      });
      const elapsed = ((Date.now() - start) / 1000).toFixed(2);
      const text = response.choices[0].message.content.slice(0, 60);
      console.log(${id.padEnd(20)}  s  ...);
    } catch (e) {
      console.log(${id.padEnd(20)}  ERROR  );
    }
  }
}

main().catch(console.error);