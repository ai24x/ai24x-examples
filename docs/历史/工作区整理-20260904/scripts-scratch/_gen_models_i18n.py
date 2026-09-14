# -*- coding: utf-8 -*-
"""Regenerate models/*.html with data-i18n for zh/en."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1] / "web" / "models"

MODELS = [
    ("kimi", "Kimi / Moonshot"),
    ("xiaomi-mimo", "Xiaomi MiMo"),
    ("minimax", "MiniMax"),
    ("zhipu-glm", "Zhipu GLM"),
    ("deepseek", "DeepSeek"),
    ("qwen", "Qwen"),
]

INDEX = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>China Models · AI24X</title>
  <meta name="description" content="Browse China LLM pages: Kimi, Xiaomi MiMo, MiniMax, Zhipu GLM, DeepSeek, Qwen." />
  <link rel="canonical" href="https://www.ai24x.com/models/index.html" />
  <link rel="stylesheet" href="../css/base.css?v=20260731b" />
  <link id="theme-css" rel="stylesheet" href="../css/themes/theme-blue.css?v=20260725a" data-base="../css/themes/" />
</head>
<body data-page="models" class="theme-blue">
  <header class="site-header" id="site-header"></header>
  <main class="page-main">
    <section class="hero hero-surface section-tight">
      <div class="container">
        <h1 data-i18n="page.models.title"></h1>
        <p class="lead" data-i18n="page.models.lead"></p>
        <div class="hero-cta">
          <a class="btn btn-primary" href="../register.html" data-i18n="page.index.hero.cta.register"></a>
          <a class="btn" href="../pricing.html" data-i18n="nav.pricing"></a>
          <a class="btn" href="../guides/index.html" data-i18n="btn.guides"></a>
          <a class="btn" href="../refer.html" data-i18n="page.models.cta.invite"></a>
        </div>
      </div>
    </section>
    <section class="section">
      <div class="container">
        <div class="grid-3">
__CARDS__
        </div>
        <p class="sub mt-2" data-i18n="page.models.foot"></p>
      </div>
    </section>
  </main>
  <footer class="site-footer" id="site-footer"></footer>
  <script src="../config/locales.js?v=20260731b"></script>
  <script src="../js/api.js?v=20260731a"></script>
  <script src="../js/i18n.js?v=20260731a"></script>
  <script src="../js/shell.js?v=20260731a"></script>
  <script src="../js/app.js?v=20260421a"></script>
</body>
</html>
"""

DETAIL = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__TITLE_EN__ · AI24X</title>
  <meta name="description" content="__DESC_EN__" />
  <link rel="canonical" href="https://www.ai24x.com/models/__SLUG__.html" />
  <link rel="stylesheet" href="../css/base.css?v=20260731b" />
  <link id="theme-css" rel="stylesheet" href="../css/themes/theme-blue.css?v=20260725a" data-base="../css/themes/" />
</head>
<body data-page="models" class="theme-blue">
  <header class="site-header" id="site-header"></header>
  <main class="page-main">
    <section class="hero hero-surface section-tight">
      <div class="container">
        <p class="sub"><a href="index.html" data-i18n="page.models.title"></a></p>
        <h1 data-i18n="page.models.__KEY__.h1"></h1>
        <p class="lead" data-i18n="page.models.__KEY__.lead"></p>
        <div class="hero-cta">
          <a class="btn btn-primary" href="../register.html" data-i18n="page.index.hero.cta.register"></a>
          <a class="btn" href="../pricing.html" data-i18n="nav.pricing"></a>
          <a class="btn" href="../docs.html" data-i18n="nav.docs"></a>
          <a class="btn" href="../guides/index.html" data-i18n="btn.guides"></a>
        </div>
      </div>
    </section>
    <section class="section">
      <div class="container" style="max-width:820px">
        <h2 data-i18n="page.models.how"></h2>
        <ul class="lead" style="padding-left:1.25rem">
          <li data-i18n="page.models.__KEY__.b1"></li>
          <li data-i18n="page.models.__KEY__.b2"></li>
          <li data-i18n="page.models.__KEY__.b3"></li>
        </ul>
        <h2 class="mt-2" data-i18n="page.models.quick"></h2>
        <div class="code-block">curl -X POST "https://api.ai24x.com/v1/chat/run" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"prompt":"Hello","model":"flash","max_tokens":200}'</div>
        <p class="sub mt-2" data-i18n="page.models.note"></p>
        <p class="mt-2">
          <span data-i18n="page.models.inviteLead"></span>
          <a href="../refer.html" data-i18n="page.models.cta.invite"></a>
          · <a href="index.html" data-i18n="page.models.all"></a>
          · <a href="../help.html" data-i18n="nav.help"></a>
        </p>
      </div>
    </section>
  </main>
  <footer class="site-footer" id="site-footer"></footer>
  <script src="../config/locales.js?v=20260731b"></script>
  <script src="../js/api.js?v=20260731a"></script>
  <script src="../js/i18n.js?v=20260731a"></script>
  <script src="../js/shell.js?v=20260731a"></script>
  <script src="../js/app.js?v=20260421a"></script>
</body>
</html>
"""

META = {
    "kimi": ("Kimi API", "Call Kimi with one AI24X key and PayPal USD."),
    "xiaomi-mimo": ("Xiaomi MiMo API", "Call Xiaomi MiMo with AI24X credits."),
    "minimax": ("MiniMax API", "Call MiniMax with AI24X credits."),
    "zhipu-glm": ("Zhipu GLM API", "Call Zhipu GLM with AI24X credits."),
    "deepseek": ("DeepSeek API", "Call DeepSeek tiers via AI24X."),
    "qwen": ("Qwen API", "Call Qwen with AI24X credits."),
}

cards = []
for slug, _ in MODELS:
    key = slug.replace("-", "_")
    cards.append(
        f'          <div class="card"><h3><a href="{slug}.html" data-i18n="page.models.card.{key}.t"></a></h3>'
        f'<p data-i18n="page.models.card.{key}.p"></p></div>'
    )

ROOT.mkdir(parents=True, exist_ok=True)
(ROOT / "index.html").write_text(
    INDEX.replace("__CARDS__", "\n".join(cards)), encoding="utf-8"
)

for slug, _ in MODELS:
    key = slug.replace("-", "_")
    title, desc = META[slug]
    html = (
        DETAIL.replace("__SLUG__", slug)
        .replace("__KEY__", key)
        .replace("__TITLE_EN__", title)
        .replace("__DESC_EN__", desc)
    )
    (ROOT / f"{slug}.html").write_text(html, encoding="utf-8")
    print("wrote", slug)

print("index ok")
