# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web" / "models"

MODELS = [
    {
        "slug": "kimi",
        "title": "Kimi API · Moonshot via AI24X",
        "h1": "Kimi (Moonshot) API with PayPal",
        "desc": "Call Kimi / Moonshot models with one AI24X key and USD credits. Extreme-value China LLM for developers abroad.",
        "lead": "Kimi is a top China LLM many developers search for. AI24X lets you try value tiers (flash/pro) first, then use named picks when VIP opens—PayPal USD, one key.",
        "bullets": [
            "Search intents: Kimi API, Kimi K2, Kimi 3, Moonshot API, cheap Kimi API",
            "Start with model tier flash or pro on /v1/chat/run",
            "VIP named Kimi routing is rolling out (billing multiplier by plan)",
        ],
    },
    {
        "slug": "xiaomi-mimo",
        "title": "Xiaomi MiMo API · AI24X",
        "h1": "Xiaomi MiMo API — extreme value China LLM",
        "desc": "Use Xiaomi MiMo with AI24X credits and PayPal. One key for developers outside China.",
        "lead": "MiMo is widely used for high-value China-model workloads. Validate cost on AI24X tiers, then scale when it pays off.",
        "bullets": [
            "Search intents: Xiaomi MiMo API, MiMo-V2, MiMo Flash, cheap MiMo API",
            "Public tier names: flash / pro (do not hard-code unstable upstream ids in apps)",
            "Named MiMo pick planned for VIP",
        ],
    },
    {
        "slug": "minimax",
        "title": "MiniMax API · M2 via AI24X",
        "h1": "MiniMax (M2) API with USD credits",
        "desc": "Call MiniMax models through AI24X—one key, PayPal USD, value-first for agent/coding workloads.",
        "lead": "MiniMax M-series is a frequent pick for agentic and coding stacks. AI24X focuses on clear credits and cross-border payment—not the biggest catalog.",
        "bullets": [
            "Search intents: MiniMax API, MiniMax M2, M2.5, M2.7, cheap MiniMax API",
            "Try flash/pro first; named MiniMax on VIP roadmap",
            "See Integrations for OpenClaw / SDK snippets",
        ],
    },
    {
        "slug": "zhipu-glm",
        "title": "Zhipu GLM API · AI24X",
        "h1": "Zhipu GLM API for developers abroad",
        "desc": "Access Zhipu / GLM-class models via AI24X token credits and PayPal USD.",
        "lead": "GLM (Zhipu / Z.ai) is a core China-model brand in global search. Use AI24X for one-key billing and clearer onboarding than juggling multiple vendor accounts.",
        "bullets": [
            "Search intents: Zhipu API, GLM API, GLM-4, GLM-5, ChatGLM API",
            "Start with flash/pro tiers on the unified endpoint",
            "VIP named GLM pick planned",
        ],
    },
    {
        "slug": "deepseek",
        "title": "DeepSeek API · Value tiers on AI24X",
        "h1": "DeepSeek API with PayPal — value path",
        "desc": "Run DeepSeek-class workloads via AI24X flash/pro tiers. One key, USD credits, extreme value focus.",
        "lead": "DeepSeek is our default value anchor for flash/pro. Abroad developers get PayPal top-up and a single integration instead of fighting payment rails.",
        "bullets": [
            "Search intents: DeepSeek API, DeepSeek V4, cheap DeepSeek API, DeepSeek PayPal",
            "Recommended public model field: flash or pro",
            "Named DeepSeek pick available in VIP catalog planning",
        ],
    },
    {
        "slug": "qwen",
        "title": "Qwen API · Alibaba models via AI24X",
        "h1": "Qwen API — China LLM credits",
        "desc": "Call Qwen-class models with AI24X. PayPal USD for developers outside China; clear token billing.",
        "lead": "Qwen (Tongyi) covers strong general and international routing use cases. AI24X keeps the story on value China LLMs and simple credits.",
        "bullets": [
            "Search intents: Qwen API, Qwen 2.5, Qwen 3, Alibaba Qwen API pricing",
            "Validate on flash/pro; named Qwen on VIP roadmap",
            "Pair with Docs Quickstart and OpenAI-compatible guide",
        ],
    },
]

TPL = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{title}</title>
  <meta name=\"description\" content=\"{desc}\" />
  <link rel=\"canonical\" href=\"https://www.ai24x.com/models/{slug}.html\" />
  <meta property=\"og:title\" content=\"{title}\" />
  <meta property=\"og:description\" content=\"{desc}\" />
  <meta property=\"og:url\" content=\"https://www.ai24x.com/models/{slug}.html\" />
  <meta property=\"og:type\" content=\"website\" />
  <link rel=\"stylesheet\" href=\"../css/base.css?v=20260731a\" />
  <link id=\"theme-css\" rel=\"stylesheet\" href=\"../css/themes/theme-blue.css?v=20260725a\" data-base=\"../css/themes/\" />
  <script type=\"application/ld+json\">
  {{
    \"@context\": \"https://schema.org\",
    \"@type\": \"WebPage\",
    \"name\": {title_json},
    \"description\": {desc_json},
    \"url\": \"https://www.ai24x.com/models/{slug}.html\"
  }}
  </script>
</head>
<body data-page=\"models\" class=\"theme-blue\">
  <header class=\"site-header\" id=\"site-header\"></header>
  <main class=\"page-main\">
    <section class=\"hero hero-surface section-tight\">
      <div class=\"container\">
        <p class=\"sub\"><a href=\"index.html\">China models</a></p>
        <h1>{h1}</h1>
        <p class=\"lead\">{lead}</p>
        <div class=\"hero-cta\">
          <a class=\"btn btn-primary\" href=\"../register.html\">Create account</a>
          <a class=\"btn\" href=\"../pricing.html\">Pricing</a>
          <a class=\"btn\" href=\"../docs.html\">Docs</a>
          <a class=\"btn\" href=\"../guides/index.html\">Integrations</a>
        </div>
      </div>
    </section>
    <section class=\"section\">
      <div class=\"container\" style=\"max-width:820px\">
        <h2>How to start</h2>
        <ul class=\"lead\" style=\"padding-left:1.25rem\">
{bullets}
        </ul>
        <h2 class=\"mt-2\">Quick call</h2>
        <div class=\"code-block\">curl -X POST \"https://api.ai24x.com/v1/chat/run\" \\
  -H \"Content-Type: application/json\" \\
  -H \"X-API-Key: YOUR_API_KEY\" \\
  -d '{{\"prompt\":\"Hello\",\"model\":\"flash\",\"max_tokens\":200}}'</div>
        <p class=\"sub mt-2\">We specialize in extreme-value China LLMs—not the biggest global catalog. Latency depends on upstream region; we state expectations honestly.</p>
        <p class=\"mt-2\"><a href=\"index.html\">All China models</a> · <a href=\"../refer.html\">Invite &amp; earn</a> · <a href=\"../help.html\">Help</a></p>
      </div>
    </section>
  </main>
  <footer class=\"site-footer\" id=\"site-footer\"></footer>
  <script src=\"../config/locales.js?v=20260731a\"></script>
  <script src=\"../js/api.js?v=20260727b\"></script>
  <script src=\"../js/i18n.js?v=20260731a\"></script>
  <script src=\"../js/shell.js?v=20260731a\"></script>
  <script src=\"../js/app.js?v=20260421a\"></script>
  <script>try{{AI24X_SHELL.mount(\"models\");AI24X_I18N.apply(document);}}catch(e){{}}</script>
</body>
</html>
"""

import json

ROOT.mkdir(parents=True, exist_ok=True)
for m in MODELS:
    bullets = "\n".join(f"          <li>{b}</li>" for b in m["bullets"])
    html = TPL.format(
        slug=m["slug"],
        title=m["title"],
        h1=m["h1"],
        desc=m["desc"],
        lead=m["lead"],
        bullets=bullets,
        title_json=json.dumps(m["title"], ensure_ascii=False),
        desc_json=json.dumps(m["desc"], ensure_ascii=False),
    )
    (ROOT / f"{m['slug']}.html").write_text(html, encoding="utf-8")
print("wrote", len(MODELS), "model pages")
