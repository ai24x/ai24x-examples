from setuptools import setup, find_packages

setup(
    name="ai24x",
    version="1.0.0",
    description="AI24X Gateway — one API key for 31+ models",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="AI24X",
    url="https://github.com/ai24x/ai24x-examples",
    project_urls={
        "Gateway": "https://open.ai24x.com",
        "Pricing": "https://www.ai24x.com/pricing.html",
        "Source": "https://github.com/ai24x/ai24x-examples",
    },
    packages=find_packages(),
    install_requires=["openai>=1.0.0"],
    keywords=["ai-gateway", "llm", "deepseek", "gpt", "claude", "gemini", "openai-compatible"],
    python_requires=">=3.8",
)
