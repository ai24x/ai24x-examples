"""QA: AI Brief 返回结构带技术健康评分（真实 AAPL 行情 + mock 模型/配额/缓存）。"""
import asyncio
import os
import sys
from unittest.mock import patch

_API = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api", "server")
)
if _API not in sys.path:
    sys.path.insert(0, _API)

from app import ai_brief  # noqa: E402
from app import providers_us  # noqa: E402


async def _fake_call_model(symbol, stats, macd_note):
    return (
        "The price has been moving within a range and remains below its longer-term "
        "average. This content is for educational purposes only."
    )


async def main():
    rows = (await providers_us.get_kline_rows("AAPL", "day", 300))["rows"]
    assert len(rows) >= 60, f"need >=60 rows, got {len(rows)}"

    with patch("app.billing.consume_ai_brief", return_value=2):
        with patch.object(ai_brief, "_call_model", new=_fake_call_model):
            with patch.object(ai_brief, "_read_cache", return_value=None):
                with patch.object(ai_brief, "_write_cache", lambda *a, **k: None):
                    data = await ai_brief.generate_brief("qa-user", "AAPL", "day")

    score = data.get("score") or {}
    print("brief has score:", "score" in data)
    print("score ok:", score.get("ok"), "score:", score.get("score"), "summary:", score.get("summary"))
    print("brief head:", (data.get("brief") or "")[:80].replace("\n", " "))
    assert data.get("score") and score.get("ok") and score.get("score") > 0
    assert data.get("brief")
    print("PASS")


if __name__ == "__main__":
    asyncio.run(main())
