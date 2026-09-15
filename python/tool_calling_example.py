#!/usr/bin/env python3
"""Function calling / tool use example."""
from openai import OpenAI

client = OpenAI(base_url="https://api.ai24x.com/v1", api_key="sk-your-key")

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current temperature for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["city"]
        }
    }
}]

response = client.chat.completions.create(
    model="pro",
    messages=[{"role": "user", "content": "What is the weather in Tokyo?"}],
    tools=tools, tool_choice="auto", max_tokens=200
)
print(response.choices[0].message.content)
if response.choices[0].message.tool_calls:
    for tc in response.choices[0].message.tool_calls:
        print(f"Tool call: {tc.function.name}({tc.function.arguments})")
