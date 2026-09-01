"""Core → Open BYOK bridge (One API unified entry, Phase 1).

Core authenticates Hub API keys (core uid). BYOK decrypt/route/usage stays on open.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)


class ByokEntitlementError(Exception):
    """Free-tier BYOK cap or subscription gate — do not fall back to platform routing."""

    def __init__(self, code: str, message: str):
        self.code = str(code or "byok_entitlement")
        self.message = str(message or "BYOK entitlement required")
        super().__init__(self.message)


@dataclass
class ByokRouteResult:
    """Compatible with open byok.ByokRouteResult / model_router.RouteResult."""

    ok: bool
    text: str = ""
    model: str = ""
    layer: str = "BYOK"
    provider: str = "byok"
    token_count: int = 0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    public_model: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    byok_key_id: Optional[int] = None
    cached: bool = False
    upstream_model: str = ""
    project: Optional[str] = None


def bridge_enabled() -> bool:
    try:
        from config import settings

        return bool(getattr(settings, "byok_bridge_enabled", False))
    except Exception:
        return False


def _open_base() -> str:
    from config import settings

    return str(getattr(settings, "open_api_base", "") or "http://127.0.0.1:18080").rstrip("/")


def _internal_headers() -> dict[str, str]:
    from config import settings

    key = str(getattr(settings, "admin_api_key", "") or "").strip()
    if not key:
        key = str(getattr(settings, "sms_internal_key", "") or "").strip()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-Admin-Key"] = key
    return headers


def _payload_from_request(
    request: Any,
    *,
    platform_user_id: int,
    region_hint: Optional[str],
    project: Optional[str],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "platform_user_id": int(platform_user_id),
        "model": str(getattr(request, "model", None) or "auto"),
        "prompt": getattr(request, "prompt", None),
        "temperature": float(getattr(request, "temperature", None) or 0.7),
        "max_tokens": int(getattr(request, "max_tokens", None) or 1000),
        "region_hint": region_hint,
        "project": project,
    }
    msgs = getattr(request, "messages", None)
    if isinstance(msgs, list):
        body["messages"] = msgs
    tools = getattr(request, "tools", None)
    if tools:
        body["tools"] = tools
    tc = getattr(request, "tool_choice", None)
    if tc is not None:
        body["tool_choice"] = tc
    return body


def _result_from_dict(d: dict[str, Any]) -> ByokRouteResult:
    return ByokRouteResult(
        ok=bool(d.get("ok")),
        text=str(d.get("text") or ""),
        model=str(d.get("model") or ""),
        layer=str(d.get("layer") or "BYOK"),
        provider=str(d.get("provider") or "byok"),
        token_count=int(d.get("token_count") or 0),
        prompt_tokens=d.get("prompt_tokens"),
        completion_tokens=d.get("completion_tokens"),
        attempts=list(d.get("attempts") or []),
        error=d.get("error"),
        public_model=d.get("public_model"),
        tool_calls=d.get("tool_calls"),
        finish_reason=d.get("finish_reason"),
        byok_key_id=d.get("byok_key_id"),
        cached=bool(d.get("cached")),
        upstream_model=str(d.get("upstream_model") or ""),
        project=d.get("project"),
    )


def _parse_entitlement_response(r) -> None:
    try:
        data = r.json()
    except Exception:
        data = {}
    detail = data.get("detail")
    if isinstance(detail, dict):
        code = str(detail.get("code") or "byok_entitlement")
        msg = str(detail.get("message") or detail.get("message_en") or "BYOK entitlement required")
    else:
        code = "byok_entitlement"
        msg = str(detail or "BYOK entitlement required")
    raise ByokEntitlementError(code, msg)


def route_byok_chat(
    db,
    *,
    auth_user_id: int,
    request: Any,
    region_hint: Optional[str] = None,
    project: Optional[str] = None,
) -> Optional[ByokRouteResult]:
    """Return routed BYOK result, None = fall back to platform tiers."""
    del db  # open side owns BYOK DB session
    if not bridge_enabled() or not auth_user_id:
        return None
    import httpx

    payload = _payload_from_request(
        request,
        platform_user_id=int(auth_user_id),
        region_hint=region_hint,
        project=project,
    )
    url = f"{_open_base()}/v1/internal/byok/route"
    try:
        r = httpx.post(url, json=payload, headers=_internal_headers(), timeout=120.0)
    except Exception as e:
        logger.warning("byok bridge route http error: %r", e)
        return None
    if r.status_code == 402:
        _parse_entitlement_response(r)
    if r.status_code != 200:
        logger.warning("byok bridge route status=%s body=%s", r.status_code, r.text[:200])
        return None
    try:
        data = r.json()
    except Exception:
        return None
    st = str(data.get("status") or "")
    if st == "fallback":
        return None
    if st == "error":
        res = _result_from_dict(dict(data.get("result") or {}))
        return res if not res.ok else None
    if st == "routed":
        res = _result_from_dict(dict(data.get("result") or {}))
        return res if res.ok else None
    return None


def has_byok_coverage(db, auth_user_id: int, requested_model: Optional[str]) -> bool:
    del db
    if not bridge_enabled() or not auth_user_id:
        return False
    import httpx

    url = f"{_open_base()}/v1/internal/byok/has-coverage"
    payload = {
        "platform_user_id": int(auth_user_id),
        "model": str(requested_model or "auto"),
    }
    try:
        r = httpx.post(url, json=payload, headers=_internal_headers(), timeout=8.0)
        if r.status_code != 200:
            return False
        return bool((r.json() or {}).get("coverage"))
    except Exception:
        return False


def stream_byok_chat(
    db,
    *,
    auth_user_id: int,
    request: Any,
    region_hint: Optional[str] = None,
    project: Optional[str] = None,
) -> Optional[Iterator[dict[str, Any]]]:
    """NDJSON event stream from open BYOK router; None = use platform stream."""
    del db
    if not bridge_enabled() or not auth_user_id:
        return None
    import httpx

    model = str(getattr(request, "model", None) or "auto")
    preflight_url = f"{_open_base()}/v1/internal/byok/preflight"
    try:
        pr = httpx.post(
            preflight_url,
            json={"platform_user_id": int(auth_user_id), "model": model},
            headers=_internal_headers(),
            timeout=8.0,
        )
        if pr.status_code == 402:
            _parse_entitlement_response(pr)
        if pr.status_code != 200 or not (pr.json() or {}).get("ok"):
            return None
    except ByokEntitlementError:
        raise
    except Exception:
        return None

    payload = _payload_from_request(
        request,
        platform_user_id=int(auth_user_id),
        region_hint=region_hint,
        project=project,
    )

    def _gen() -> Iterator[dict[str, Any]]:
        url = f"{_open_base()}/v1/internal/byok/stream"
        try:
            with httpx.stream(
                "POST",
                url,
                json=payload,
                headers=_internal_headers(),
                timeout=300.0,
            ) as r:
                if r.status_code == 402:
                    _parse_entitlement_response(r)
                if r.status_code == 204:
                    return
                if r.status_code != 200:
                    logger.warning(
                        "byok bridge stream status=%s", r.status_code
                    )
                    return
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except Exception:
                        continue
        except ByokEntitlementError:
            raise
        except Exception:
            logger.exception("byok bridge stream failed")

    return _gen()
