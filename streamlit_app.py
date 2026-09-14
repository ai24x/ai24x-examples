import streamlit as st
import requests

st.set_page_config(page_title="AI24X AI Gateway - Live Demo", page_icon="⚡", layout="wide")

st.title("AI24X AI Gateway - Live Demo")
st.markdown("**One API. Every AI. Pay Less.** — 31+ models, one OpenAI-compatible endpoint.")

st.subheader("Quick API Test")

api_key = st.text_input("API Key", placeholder="sk-...", type="password")

model_groups = {
    "Managed Tiers": ["flash", "auto", "pro", "ultra", "shared"],
    "DeepSeek": ["vip-ds-flash", "vip-ds-pro"],
    "Qwen": ["vip-qwen-max", "vip-qwen122b"],
    "GPT-6 Series": ["vip-gpt6-astra", "vip-gpt56-terra", "vip-gpt56-sol", "vip-gpt56-luna"],
    "GPT-5 & GPT-4": ["vip-gpt5", "vip-gpt5-mini", "vip-gpt54", "vip-gpt4o", "vip-gpt4o-mini"],
    "Claude": ["vip-claude-opus", "vip-claude-sonnet", "vip-claude-haiku"],
    "Gemini": ["vip-gemini-pro", "vip-gemini-flash"],
    "Others": ["vip-kimi", "vip-kimi-code", "vip-mimo", "vip-minimax", "vip-glm", "vip-hy3", "vip-grok", "vip-llama4"]
}

all_models = []
group_labels = {}
for group, models in model_groups.items():
    for m in models:
        label = f"{group} → {m}"
        all_models.append(label)
        group_labels[label] = m

model = st.selectbox("Model", all_models, format_func=lambda x: x.split(" → ")[1] + " (" + x.split(" → ")[0] + ")")
actual_model = group_labels[model]

prompt = st.text_area("Prompt", "Say hello and introduce yourself briefly in one paragraph.")

if st.button("Send Request") and api_key:
    with st.spinner(f"Calling {actual_model} on AI24X Gateway..."):
        try:
            resp = requests.post(
                "https://api.ai24x.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": actual_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 300},
                timeout=20
            )
            if resp.status_code == 200:
                result = resp.json()
                usage = result.get("usage", {})
                st.success(f"Response from {actual_model}")
                st.write(result["choices"][0]["message"]["content"])
                if usage:
                    st.caption(f"Tokens: {usage.get('prompt_tokens', '?')} in → {usage.get('completion_tokens', '?')} out")
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")

st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("[Get API Key](https://open.ai24x.com)")
with col2:
    st.markdown("[Pricing](https://www.ai24x.com/pricing.html)")
with col3:
    st.markdown("[GitHub](https://github.com/ai24x/ai24x-examples)")