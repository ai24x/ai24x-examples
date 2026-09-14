import streamlit as st
import requests

st.set_page_config(page_title="AI24X AI Gateway - Live Demo", page_icon=":zap:", layout="wide")

st.title("AI24X AI Gateway - Live Demo")
st.markdown("**One API. Every AI. Pay Less.** -- Test 29+ models with one endpoint.")

st.subheader("Quick API Test")
api_key = st.text_input("API Key", placeholder="sk-...", type="password")
model = st.selectbox("Model", ["flash", "pro", "qwen-max", "mimo-v2.5-pro", "gpt-5", "claude-opus"])
prompt = st.text_area("Prompt", "Say hello and introduce yourself briefly.")

if st.button("Send Request") and api_key:
    with st.spinner("Calling AI24X Gateway..."):
        try:
            resp = requests.post(
                "https://api.ai24x.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 200},
                timeout=15
            )
            if resp.status_code == 200:
                result = resp.json()
                st.success(f"Response from {model}")
                st.write(result["choices"][0]["message"]["content"])
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")

st.markdown("---")
st.markdown("### Links")
st.markdown("[Get API Key](https://open.ai24x.com) | [Pricing](https://www.ai24x.com/pricing.html) | [GitHub Examples](https://github.com/ai24x/ai24x-examples)")
