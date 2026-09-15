# ai24x — Node.js Client

> One API key for 31+ models: DeepSeek, GPT-6, Claude, Gemini, Grok, Llama4, Qwen and more.

## Install

```bash
npm install ai24x openai
```

## Usage

```js
const { createClient, MODELS } = require("ai24x");

const client = createClient({ apiKey: "sk-your-key" });

async function main() {
  const response = await client.chat.completions.create({
    model: MODELS.FLASH,
    messages: [{ role: "user", content: "Hello!" }],
  });
  console.log(response.choices[0].message.content);
}
main();
```

## Docs

- [AI24X Gateway](https://open.ai24x.com)
- [Pricing](https://www.ai24x.com/pricing.html)
- [GitHub Examples](https://github.com/ai24x/ai24x-examples)
- [Live Demo](https://ai24x-examples-bj26ncdeqstapzeta63ozr.streamlit.app/)
