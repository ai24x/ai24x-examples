"""QA: 验证 PayPal/支付宝下单按 Origin 动态选择回跳域名（open 站同域回跳）。"""
import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

_API_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from token_pay_service import _origin_console_url


def test_origin_console_url():
    assert _origin_console_url(None) is None
    assert _origin_console_url("https://open.ai24x.com") == "https://open.ai24x.com/console.html"
    assert _origin_console_url("HTTPS://OPEN.AI24X.COM/") == "https://open.ai24x.com/console.html"
    assert _origin_console_url("https://www.ai24x.com") is None
    assert _origin_console_url("http://127.0.0.1:8000") is None
    print("test_origin_console_url PASS")


def _fake_row(otn="T10001"):
    return SimpleNamespace(
        out_trade_no=otn,
        plan="pro",
        amount_fen=2490,
        code_url=None,
        status="pending",
        transaction_id=None,
    )


async def test_paypal_return_dynamic():
    captured = {}
    fake_db = SimpleNamespace(commit=lambda: None)

    async def fake_create_checkout_order(cfg, **kw):
        captured.update(kw)
        return {"id": "PAYPAL-ORDER-1"}

    fake_cfg = SimpleNamespace(
        paypal_return_url="https://www.ai24x.com/console.html",
        paypal_cancel_url="https://www.ai24x.com/console.html",
        paypal_client_id="x",
        paypal_client_secret="y",
    )
    with patch("token_pay_service.create_pending_order", return_value=_fake_row()):
        with patch("token_pay_service.get_plan", return_value={"title_en": "Pro", "price_usd": 24.9}):
            with patch("token_pay_service.token_pay_mock_allowed", return_value=False):
                with patch("token_pay_service.token_pay_enabled", return_value=True):
                    with patch("token_pay_service.pay_settings_ns", return_value=fake_cfg):
                        with patch("pay_paypal.paypal_configured", return_value=True):
                            with patch(
                                "pay_paypal.create_checkout_order",
                                new=fake_create_checkout_order,
                            ):
                                with patch(
                                    "pay_paypal.approve_url_from_order",
                                    return_value="https://paypal.test/approve",
                                ):
                                    from token_pay_service import create_paypal_order

                                    r = await create_paypal_order(
                                        fake_db,
                                        auth_user_id=1,
                                        plan="pro",
                                        origin="https://open.ai24x.com",
                                    )
    ret = captured["return_url"]
    assert ret.startswith("https://open.ai24x.com/console.html?paypal=1&out_trade_no=T10001"), ret
    can = captured["cancel_url"]
    assert can.startswith("https://open.ai24x.com/console.html?paypal_cancel=1"), can
    assert r["channel"] == "paypal" and r["pay_url"] == "https://paypal.test/approve"
    print("test_paypal_return_dynamic PASS ->", ret)


async def test_paypal_return_default_when_no_origin():
    captured = {}
    fake_db = SimpleNamespace(commit=lambda: None)

    async def fake_create_checkout_order(cfg, **kw):
        captured.update(kw)
        return {"id": "PAYPAL-ORDER-2"}

    fake_cfg = SimpleNamespace(
        paypal_return_url="https://www.ai24x.com/console.html",
        paypal_cancel_url="https://www.ai24x.com/console.html",
    )
    with patch("token_pay_service.create_pending_order", return_value=_fake_row(otn="T10002")):
        with patch("token_pay_service.get_plan", return_value={"title_en": "Pro", "price_usd": 24.9}):
            with patch("token_pay_service.token_pay_mock_allowed", return_value=False):
                with patch("token_pay_service.token_pay_enabled", return_value=True):
                    with patch("token_pay_service.pay_settings_ns", return_value=fake_cfg):
                        with patch("pay_paypal.paypal_configured", return_value=True):
                            with patch(
                                "pay_paypal.create_checkout_order",
                                new=fake_create_checkout_order,
                            ):
                                with patch(
                                    "pay_paypal.approve_url_from_order",
                                    return_value="https://paypal.test/approve",
                                ):
                                    from token_pay_service import create_paypal_order

                                    await create_paypal_order(fake_db, auth_user_id=1, plan="pro")
    ret = captured["return_url"]
    assert ret.startswith("https://www.ai24x.com/console.html?paypal=1&out_trade_no=T10002"), ret
    print("test_paypal_return_default_when_no_origin PASS ->", ret)


async def test_alipay_return_dynamic():
    captured = {}
    fake_db = SimpleNamespace(commit=lambda: None)

    def fake_build_wap_pay_url(cfg, **kw):
        captured.update(kw)
        return "https://openapi.alipay.test/gateway.do?pay=1"

    fake_cfg = SimpleNamespace(alipay_return_url="https://www.ai24x.com/console.html")
    with patch("token_pay_service.create_pending_order", return_value=_fake_row(otn="T10003")):
        with patch("token_pay_service.get_plan", return_value={"title": "Pro"}):
            with patch("token_pay_service.token_pay_mock_allowed", return_value=False):
                with patch("token_pay_service.token_pay_enabled", return_value=True):
                    with patch("token_pay_service.pay_settings_ns", return_value=fake_cfg):
                        with patch("pay_alipay_wap.alipay_configured", return_value=True):
                            with patch(
                                "pay_alipay_wap.build_wap_pay_url",
                                new=fake_build_wap_pay_url,
                            ):
                                from token_pay_service import create_alipay_wap

                                await create_alipay_wap(
                                    fake_db,
                                    auth_user_id=1,
                                    plan="pro",
                                    origin="https://open.ai24x.com",
                                )
    assert captured["return_url"] == "https://open.ai24x.com/console.html", captured["return_url"]
    print("test_alipay_return_dynamic PASS ->", captured["return_url"])


if __name__ == "__main__":
    test_origin_console_url()
    asyncio.run(test_paypal_return_dynamic())
    asyncio.run(test_paypal_return_default_when_no_origin())
    asyncio.run(test_alipay_return_dynamic())
    print("ALL PASS")
