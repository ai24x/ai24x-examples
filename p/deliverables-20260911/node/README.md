# Node.js Examples: AI24X Gateway API

## Prerequisites

```bash
npm install openai
```

## Chat Completion

```javascript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.ai24x.com/v1",
  apiKey: "sk-...", // Replace with your AI24X API key
});

async function main() {
  const response = await client.chat.completions.create({
    model: "flash",
    messages: [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "Explain AI gateways simply." },
    ],
  });
  console.log(response.choices[0].message.content);
}
main();
```

## Streaming

```javascript
const stream = await client.chat.completions.create({
  model: "flash",
  messages: [{ role: "user", content: "Write a haiku." }],
  stream: true,
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || "");
}
```

## List Models

```javascript
const models = await client.models.list();
for (const m of models.data) {
  console.log(`${m.id} (${m.owned_by})`);
}
```

## BYOK Example

```javascript
const byokClient = new OpenAI({
  baseURL: "https://open.ai24x.com/v1",
  apiKey: "sk-byok-...",
});
```

See full docs at [open.ai24x.com](https://open.ai24x.com)
