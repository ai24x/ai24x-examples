import uuid
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models import User, ChatRequest, UserType
from schemas import ChatRequest as ChatRequestSchema, ChatResponse
from config import settings
from security_util import attribution_block

logger = logging.getLogger(__name__)


def _usd_cents_for_tokens(token_count: int) -> int:
    """钱包 token → USD 美分（与 flash 锚一致）。"""
    try:
        from model_warehouse import flash_ref_usd_per_m

        ref = float(flash_ref_usd_per_m())
    except Exception:
        ref = 0.35
    if ref <= 0:
        ref = 0.35
    return max(0, int(round(max(0, int(token_count)) / 1_000_000.0 * ref * 100)))


def _stamp_chat_route(
    chat_request: ChatRequest,
    *,
    auth_user_id: Optional[int] = None,
    public_model: Optional[str] = None,
    provider: Optional[str] = None,
    upstream_model: Optional[str] = None,
) -> None:
    """写入运维用通道×用户字段（不 commit）。"""
    if auth_user_id is not None:
        try:
            chat_request.auth_user_id = int(auth_user_id)
        except Exception:
            pass
    if public_model is not None:
        chat_request.public_model = str(public_model or "")[:64] or None
    if provider is not None:
        chat_request.provider = str(provider or "")[:64] or None
    if upstream_model is not None:
        chat_request.model = str(upstream_model or "")[:100] or None


def estimate_need_tokens(*, model: Optional[str], max_tokens: int, prompt: str = "") -> int:
    """预检用量：粗估 (prompt/4 + min(max_tokens,1024)) × 档位/名模倍率。

    不按完整 max_tokens 卡死（OpenClaw 常设 8k）；成功后仍按实扣，余额不足则夹断。
    """
    in_mult = 1
    out_mult = 1
    try:
        from model_warehouse import resolve_vip_pick, layer_cost_mult_for

        pick = resolve_vip_pick(model)
        if pick:
            in_mult = max(1, int(pick.get("in_mult") or pick.get("billing_mult") or 1))
            out_mult = max(1, int(pick.get("out_mult") or pick.get("billing_mult") or 1))
        else:
            m = str(model or "flash").strip().lower()
            layer = "L1"
            if m in ("pro", "or-pro"):
                layer = "L2"
            elif m in ("ultra", "or-ultra"):
                layer = "L3"
            elif m in ("shared", "free", "or-fallback"):
                layer = "L0"
            mult = max(1, int(layer_cost_mult_for(layer)))
            in_mult = out_mult = int(mult)
    except Exception:
        in_mult = out_mult = 1
    prompt_est = max(0, len(prompt or "") // 4)
    capped = min(max(1, int(max_tokens or 1000)), 1024)
    return max(1, prompt_est * in_mult + capped * out_mult)


class UserService:
    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
        return db.query(User).filter(User.user_id == user_id).first()
    
    @staticmethod
    def get_user_by_api_key(db: Session, api_key: str) -> Optional[User]:
        return db.query(User).filter(User.api_key == api_key).first()
    
    @staticmethod
    def create_user(db: Session, user_id: str, user_type: UserType = UserType.FREE) -> User:
        user = User(
            user_id=user_id,
            user_type=user_type,
            api_key=f"sk_{uuid.uuid4().hex[:32]}",
            daily_request_limit=100 if user_type == UserType.FREE else 1000,
            monthly_request_limit=3000 if user_type == UserType.FREE else 30000
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def check_rate_limit(db: Session, user: User) -> tuple[bool, Optional[str | dict]]:
        """检查用户是否超出日/月请求上限。

        按 UTC 自然日 / 自然月重置（不再用 updated_at 滚动 24h，避免 Agent 重试永远不清零）。
        """
        now = datetime.utcnow()
        today = now.date()
        last = user.updated_at
        last_naive = None
        if last is not None:
            last_naive = last.replace(tzinfo=None) if getattr(last, "tzinfo", None) else last
        last_day = last_naive.date() if last_naive is not None else None

        dirty = False
        if last_day is not None and last_day < today and int(user.current_daily_requests or 0) != 0:
            user.current_daily_requests = 0
            dirty = True
        if last_day is not None and (
            (last_day.year, last_day.month) != (today.year, today.month)
        ) and int(user.current_monthly_requests or 0) != 0:
            user.current_monthly_requests = 0
            dirty = True
        if dirty:
            # 仅推进重置水位；不把「无请求」算进当日用量
            user.updated_at = now
            db.commit()

        daily_lim = max(0, int(user.daily_request_limit or 0))
        monthly_lim = max(0, int(user.monthly_request_limit or 0))
        if daily_lim > 0 and int(user.current_daily_requests or 0) >= daily_lim:
            return False, {
                "message_zh": "今日请求次数已用完，请明天再试，或开通会员 / 提高额度。",
                "message_en": "Daily request limit reached. Try again tomorrow, or upgrade for a higher limit.",
                "message": "今日请求次数已用完，请明天再试，或开通会员 / 提高额度。",
                "code": "daily_request_limit",
            }
        if monthly_lim > 0 and int(user.current_monthly_requests or 0) >= monthly_lim:
            return False, {
                "message_zh": "本月请求次数已用完，请下月再试或开通会员。",
                "message_en": "Monthly request limit reached. Try again next month, or upgrade.",
                "message": "本月请求次数已用完，请下月再试或开通会员。",
                "code": "monthly_request_limit",
            }
        return True, None

    @staticmethod
    def increment_request_count(db: Session, user: User):
        """增加用户请求计数"""
        # 跨日先归零再累加，避免「昨日打满、今日首包仍被挡」
        UserService.check_rate_limit(db, user)
        user.current_daily_requests = int(user.current_daily_requests or 0) + 1
        user.current_monthly_requests = int(user.current_monthly_requests or 0) + 1
        user.updated_at = datetime.utcnow()
        db.commit()


class ChatService:
    @staticmethod
    def process_chat_request(
        db: Session,
        user: User,
        request: ChatRequestSchema,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        auth_user_id: Optional[int] = None,
        region_hint: Optional[str] = None,
        auth_api_key_id: Optional[int] = None,  # 2026-08-15: 按 API Key 统计
        byok_project: Optional[str] = None,
    ) -> ChatResponse:
        """处理聊天请求；若提供 auth_user_id 则走 Token 钱包扣减。"""
        request_id = f"req_{uuid.uuid4().hex[:16]}"
        start_time = time.time()

        # Token 钱包：有可花额度→付费；否则自动降级 shared（日帽内保活）
        billing_mode = "paid"
        billing: dict = {}
        if auth_user_id is not None:
            from free_shared import resolve_chat_billing_mode

            billing = resolve_chat_billing_mode(
                db,
                auth_user_id=int(auth_user_id),
                requested_model=request.model,
                force_shared=False,
            )
            billing_mode = str(billing.get("mode") or "paid")

        chat_request = ChatRequest(
            request_id=request_id,
            user_id=user.user_id,
            user_type=user.user_type,
            prompt=request.prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            ip_address=ip_address,
            user_agent=user_agent,
            status="processing",
        )
        _stamp_chat_route(
            chat_request,
            auth_user_id=auth_user_id,
            public_model=request.model,
            provider=None,
        )
        db.add(chat_request)
        db.commit()

        # BYOK（One API）：Hub key @ api.ai24x.com → open 内部路由
        byok_result = None
        if auth_user_id is not None:
            try:
                from byok_bridge import ByokEntitlementError, route_byok_chat

                byok_result = route_byok_chat(
                    db,
                    auth_user_id=int(auth_user_id),
                    request=request,
                    region_hint=region_hint,
                    project=byok_project,
                )
            except ByokEntitlementError as e:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=str(e.message or e),
                ) from e
            except Exception:
                byok_result = None
                logger.exception("byok bridge failed, fallback platform")

        try:
            from token_mvp_service import get_balance_snapshot
            from model_router import run_routed_chat

            hold_active = False
            is_vip = False
            route_model = request.model
            allow_names = None
            if auth_user_id is not None:
                snap0 = get_balance_snapshot(db, int(auth_user_id))
                is_vip = bool(snap0.get("is_vip_active"))
                if not is_vip:
                    from token_mvp_service import value_pack_allowed_models

                    allow_names = value_pack_allowed_models(db, int(auth_user_id))
            routed_tool_calls = None
            routed_finish = None
            used_shared_catalog = None
            if byok_result is not None:
                routed = byok_result
            elif billing_mode == "shared":
                from free_shared import run_shared_pool_chat

                # 共享池：工具调用仍走付费路由语义；无余额降级时暂不支持 tools
                if getattr(request, "tools", None):
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail="工具调用需有可用余额，请先充值后再试。",
                    )
                routed = run_shared_pool_chat(
                    prompt=request.prompt,
                    temperature=float(request.temperature or 0.7),
                    max_tokens=int(request.max_tokens or 1000),
                )
                # T13：取本次实际命中的上游目录用于聚合熔断
                for _a in getattr(routed, "attempts", None) or []:
                    if _a.get("ok") and _a.get("catalog_id"):
                        used_shared_catalog = _a["catalog_id"]
                        break
            else:
                if auth_user_id is not None:
                    from token_mvp_service import release_hold, reserve_tokens

                    # S5：上游前预扣，堵住并发透支；失败/不计费须 release
                    reserve_tokens(
                        db,
                        int(auth_user_id),
                        need_tokens=estimate_need_tokens(
                            model=route_model,
                            max_tokens=int(request.max_tokens or 1000),
                            prompt=str(request.prompt or ""),
                        ),
                        model=route_model,
                        request_id=request_id,
                    )
                    hold_active = True

                    # P2：点名模每日上限（单模型次数 / 单用户 credits），超限 429
                    from vip_named_guard import check_named_daily_limit
                    from model_warehouse import resolve_vip_pick

                    if resolve_vip_pick(route_model):
                        try:
                            check_named_daily_limit(db, int(auth_user_id), str(route_model))
                        except HTTPException:
                            if hold_active:
                                try:
                                    release_hold(
                                        db,
                                        auth_user_id=int(auth_user_id),
                                        request_id=request_id,
                                    )
                                    hold_active = False
                                except Exception:
                                    pass
                            raise
                        except Exception:
                            # 保护不可用时不阻断主链路（fail-open），告警交给运维日志
                            pass
                msgs = getattr(request, "messages", None)
                try:
                    routed = run_routed_chat(
                        prompt=request.prompt,
                        requested_model=route_model,
                        is_vip=is_vip,
                        allow_names=allow_names,
                        temperature=float(request.temperature or 0.7),
                        max_tokens=int(request.max_tokens or 1000),
                        region_hint=region_hint,
                        messages=msgs if isinstance(msgs, list) else None,
                        tools=getattr(request, "tools", None),
                        tool_choice=getattr(request, "tool_choice", None),
                        include_reasoning=bool(getattr(request, "include_reasoning", False)),
                    )
                except Exception as _ue:
                    from upstream_gate import UpstreamBusyError

                    if isinstance(_ue, UpstreamBusyError):
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="模型服务暂时繁忙，请稍后再试。",
                        ) from _ue
                    raise
            if not routed.ok:
                if (routed.error or "") == "vip_required":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "message_zh": "点名模型需有效会员权益。请确认当前 API Key 属于已开通会员的账号（控制台可用同一 Key 访问余额接口核对）。",
                            "message_en": "Named models need an active membership on the account that owns this API key. Check /v1/billing/balance with the same key.",
                            "message": "点名模型需有效会员权益。请确认当前 API Key 属于已开通会员的账号。",
                            "code": "vip_required",
                        },
                    )
                if (routed.error or "") == "vip_pick_disabled":
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "message_zh": "点名模型暂时不可用，请改用 flash / pro，或稍后再试。",
                            "message_en": "Named models are temporarily unavailable. Please use flash/pro, or try again later.",
                            "message": "点名模型暂时不可用，请改用 flash / pro，或稍后再试。",
                            "code": "vip_pick_disabled",
                        },
                    )
                if (routed.error or "") == "tools_unsupported":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="当前模型暂不支持工具调用，请改用 flash 或 pro，或稍后再试。",
                    )
                if (routed.error or "").startswith("byok_all_failed"):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={
                            "message_zh": "你的所有上游 Key 均调用失败，且平台回退已关闭。请到 Gateway 工作区检查 Key 状态或更换 Key。",
                            "message_en": "All your upstream keys failed and platform fallback is disabled. Check your keys in the Gateway workspace.",
                            "message": "All BYOK upstream keys failed.",
                            "code": "byok_all_failed",
                        },
                    )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="模型服务暂时繁忙，请稍后再试。",
                )

            response_text = routed.text
            used_model = routed.model
            routed_tool_calls = getattr(routed, "tool_calls", None)
            routed_finish = getattr(routed, "finish_reason", None)
            if not bool(getattr(request, "include_reasoning", False)):
                from reasoning_filter import scrub_think_tags

                response_text = scrub_think_tags(str(response_text or ""))
            from model_router import public_tier_name

            public_model = getattr(routed, "public_model", None) or public_tier_name(
                "shared" if billing_mode == "shared" else request.model,
                layer=routed.layer or "",
                upstream_model=used_model or "",
            )
            # 全上游失败落 stub：不计费（总纲 v3.3）；纯联调 stub（未配 Key）仍计最小 token 便于测钱包
            billable = not (
                routed.provider == "stub"
                and (routed.error or "") == "all_live_failed_used_stub"
            )
            token_count = max(1, int(routed.token_count)) if billable else 0
            # billing_mult 已计入 routed.token_count（VIP 点名）；此处不再叠乘

            processing_time = time.time() - start_time

            # 更新请求记录（库内仍记上游型号便于运维）
            chat_request.response = response_text
            chat_request.response_time = datetime.utcnow()
            chat_request.processing_duration = processing_time
            chat_request.status = "completed"
            chat_request.is_success = True
            chat_request.token_count = int(token_count)
            chat_request.cost = token_count * (0.000002 if user.user_type == UserType.FREE else 0.000001)
            _stamp_chat_route(
                chat_request,
                auth_user_id=auth_user_id,
                public_model=public_model,
                provider=getattr(routed, "provider", None) or ("byok" if byok_result else None),
                upstream_model=used_model,
            )
            db.commit()

            # 增加用户请求计数
            UserService.increment_request_count(db, user)

            remaining_quota = user.daily_request_limit - user.current_daily_requests
            snap = None
            if auth_user_id is not None:
                from token_mvp_service import consume_tokens, get_balance_snapshot, release_hold
                from free_shared import record_shared_usage

                if billing_mode == "shared":
                    if billable and token_count > 0:
                        record_shared_usage(
                            db,
                            auth_user_id=int(auth_user_id),
                            tokens=int(token_count),
                            model=public_model,
                            request_id=request_id,
                            catalog_id=used_shared_catalog,
                        )
                    snap = get_balance_snapshot(db, int(auth_user_id))
                    remaining_quota = int(snap.get("shared_remain_tokens") or 0)
                else:
                    byok_used = getattr(routed, "byok_key_id", None) is not None
                    if byok_used:
                        pass
                    elif billable and token_count > 0:
                        consume_tokens(
                            db,
                            auth_user_id=int(auth_user_id),
                            tokens=int(token_count),
                            amount_usd=_usd_cents_for_tokens(int(token_count)),
                            model=public_model,
                            request_id=request_id,
                            prompt_tokens=getattr(routed, "prompt_tokens", None),
                            completion_tokens=getattr(routed, "completion_tokens", None),
                            api_key_id=auth_api_key_id,
                        )
                        hold_active = False

                        # P2：累计点名模每日用量（仅成功且计费）
                        from vip_named_guard import record_named_usage
                        from model_warehouse import resolve_vip_pick

                        if resolve_vip_pick(str(request.model or "")):
                            try:
                                record_named_usage(db, int(auth_user_id), str(request.model), int(token_count))
                            except Exception:
                                pass
                    if hold_active:
                        try:
                            release_hold(
                                db,
                                auth_user_id=int(auth_user_id),
                                request_id=request_id,
                            )
                        except Exception:
                            pass
                        hold_active = False
                    snap = get_balance_snapshot(db, int(auth_user_id))
                    remaining_quota = int(snap.get("balance_tokens") or 0)

            byok_key_id = getattr(routed, "byok_key_id", None)
            if billing_mode == "shared" and byok_key_id is None:
                public_model = "shared"

            attr = attribution_block(
                request_id=request_id, auth_user_id=auth_user_id
            )
            if billing_mode == "shared" and byok_key_id is None:
                attr["billing_mode"] = "shared"
                attr["auto_degraded"] = bool(billing.get("auto_degraded"))
                if billing.get("auto_degraded"):
                    attr["upgrade_hint_zh"] = (
                        "当前为每日免费体验；充值后自动恢复付费档（flash/pro）。"
                    )
                    attr["upgrade_hint_en"] = (
                        "You're on the free daily pool. Top up to return to paid flash/pro."
                    )
                # attribution 里的 remain 与 remaining_quota 对齐为扣费后
                if snap is not None:
                    attr["shared_remain_tokens"] = int(
                        snap.get("shared_remain_tokens") or remaining_quota or 0
                    )
                    if snap.get("shared_remain_req") is not None:
                        attr["shared_remain_req"] = snap.get("shared_remain_req")
                else:
                    shared_info = billing.get("shared") or {}
                    if shared_info.get("remain_tokens") is not None:
                        attr["shared_remain_tokens"] = shared_info.get("remain_tokens")
                    if shared_info.get("remain_req") is not None:
                        attr["shared_remain_req"] = shared_info.get("remain_req")
            else:
                attr["billing_mode"] = "paid"
                if byok_key_id is not None:
                    attr["billing_mode"] = "byok"
                    attr["fee_note_zh"] = "本次走你自有的上游 Key，平台不扣托管余额，仅计网关服务。"
                    attr["fee_note_en"] = "This request used your own upstream key. We charge a gateway service fee only, no token markup."

            return ChatResponse(
                request_id=request_id,
                response=response_text,
                model=public_model,
                token_count=int(token_count),
                processing_time=processing_time,
                user_type=user.user_type,
                remaining_quota=remaining_quota,
                created_at=datetime.utcnow(),
                layer="BYOK" if byok_key_id is not None else None,
                provider="byok" if byok_key_id is not None else "ai24x",
                route_attempts=getattr(routed, "attempts", None) if byok_key_id is not None else None,
                attribution=attr,
                tool_calls=routed_tool_calls,
                finish_reason=routed_finish
                or ("tool_calls" if routed_tool_calls else "stop"),
            )

        except Exception as e:
            # S5：上游失败时退回预扣
            try:
                if auth_user_id is not None and locals().get("hold_active"):
                    from token_mvp_service import release_hold

                    release_hold(
                        db,
                        auth_user_id=int(auth_user_id),
                        request_id=request_id,
                    )
            except Exception:
                pass
            # 记录错误
            chat_request.error_message = str(e)
            chat_request.status = "failed"
            chat_request.response_time = datetime.utcnow()
            chat_request.processing_duration = time.time() - start_time
            db.commit()
            raise

    @staticmethod
    def stream_chat_request(
        db: Session,
        user: User,
        request: ChatRequestSchema,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        auth_user_id: Optional[int] = None,
        region_hint: Optional[str] = None,
        auth_api_key_id: Optional[int] = None,  # 2026-08-15: 按 API Key 统计
        byok_project: Optional[str] = None,
    ):
        """真流式：yield meta/delta/done；记账与生成器解耦（finally 兜底）。

        2026-08-12 根治（P0）：记账移到 finally 收尾——消费方 done 后提前
        return / 客户端中途断开（GeneratorExit）/ 异常，任何退出路径都不漏记、
        不重复记（_finalize 幂等）。替换原「yield done 之后记账」的漏记设计。
        """
        request_id = f"req_{uuid.uuid4().hex[:16]}"
        start_time = time.time()
        billing_mode = "paid"
        billing: dict = {}
        if auth_user_id is not None:
            from free_shared import resolve_chat_billing_mode

            billing = resolve_chat_billing_mode(
                db,
                auth_user_id=int(auth_user_id),
                requested_model=request.model,
                force_shared=False,
            )
            billing_mode = str(billing.get("mode") or "paid")

        chat_request = ChatRequest(
            request_id=request_id,
            user_id=user.user_id,
            user_type=user.user_type,
            prompt=(request.prompt or "").replace("\x00", ""),
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            ip_address=ip_address,
            user_agent=user_agent,
            status="processing",
        )
        _stamp_chat_route(
            chat_request,
            auth_user_id=auth_user_id,
            public_model=request.model,
            provider=None,
        )
        db.add(chat_request)
        db.commit()

        byok_stream = None
        if auth_user_id is not None:
            try:
                from byok_bridge import ByokEntitlementError, stream_byok_chat

                byok_stream = stream_byok_chat(
                    db,
                    auth_user_id=int(auth_user_id),
                    request=request,
                    region_hint=region_hint,
                    project=byok_project,
                )
            except ByokEntitlementError as e:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=str(e.message or e),
                ) from e
            except Exception:
                byok_stream = None
                logger.exception("byok bridge stream setup failed, fallback platform")

        msgs = getattr(request, "messages", None)
        public_model = request.model or "flash"
        provider = "ai24x"
        used_model = public_model
        full_text = ""
        token_count = 0
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        billable = True
        byok_used = byok_stream is not None
        saw_done = False
        saw_error = False
        error_detail = ""
        finalized = False
        hold_active = False

        def _finalize(status: str, err: str = "") -> None:
            """记账收尾（不 yield；可被 finally / GeneratorExit 路径调用；幂等）。"""
            nonlocal finalized, hold_active
            if finalized:
                return
            finalized = True
            try:
                now = datetime.utcnow()
                chat_request.response_time = now
                chat_request.processing_duration = time.time() - start_time
                if status == "completed":
                    chat_request.response = (full_text or "")[:200000]
                    chat_request.status = "completed"
                    chat_request.is_success = True
                    chat_request.token_count = int(token_count) if billable else 0
                    _stamp_chat_route(
                        chat_request,
                        auth_user_id=auth_user_id,
                        public_model=public_model,
                        provider=provider,
                        upstream_model=used_model,
                    )
                    db.commit()
                    UserService.increment_request_count(db, user)
                    if auth_user_id is not None and billable and token_count > 0 and not byok_used:
                        from token_mvp_service import consume_tokens
                        from free_shared import record_shared_usage

                        if billing_mode == "shared":
                            record_shared_usage(
                                db,
                                auth_user_id=int(auth_user_id),
                                tokens=int(token_count),
                                model="shared",
                                request_id=request_id,
                                catalog_id=used_shared_catalog,
                            )
                        else:
                            consume_tokens(
                                db,
                                auth_user_id=int(auth_user_id),
                                tokens=int(token_count),
                                amount_usd=_usd_cents_for_tokens(int(token_count)),
                                model=public_model,
                                request_id=request_id,
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                api_key_id=auth_api_key_id,
                            )
                            hold_active = False
                    if hold_active and auth_user_id is not None:
                        try:
                            from token_mvp_service import release_hold

                            release_hold(
                                db,
                                auth_user_id=int(auth_user_id),
                                request_id=request_id,
                            )
                        except Exception:
                            pass
                        hold_active = False
                else:
                    chat_request.status = status
                    if err:
                        chat_request.error_message = str(err)[:300]
                    db.commit()
                    if hold_active and auth_user_id is not None:
                        try:
                            from token_mvp_service import release_hold

                            release_hold(
                                db,
                                auth_user_id=int(auth_user_id),
                                request_id=request_id,
                            )
                        except Exception:
                            pass
                        hold_active = False
            except HTTPException:
                try:
                    chat_request.status = "failed"
                    db.commit()
                except Exception:
                    pass
                if hold_active and auth_user_id is not None:
                    try:
                        from token_mvp_service import release_hold

                        release_hold(
                            db,
                            auth_user_id=int(auth_user_id),
                            request_id=request_id,
                        )
                    except Exception:
                        pass
                    hold_active = False
            except Exception as e:
                try:
                    chat_request.error_message = str(e)[:300]
                    chat_request.status = "failed"
                    db.commit()
                except Exception:
                    pass
                if hold_active and auth_user_id is not None:
                    try:
                        from token_mvp_service import release_hold

                        release_hold(
                            db,
                            auth_user_id=int(auth_user_id),
                            request_id=request_id,
                        )
                    except Exception:
                        pass
                    hold_active = False

        try:
            from token_mvp_service import get_balance_snapshot
            from model_router import run_routed_chat_stream, public_tier_name

            is_vip = False
            allow_names = None
            if auth_user_id is not None:
                snap0 = get_balance_snapshot(db, int(auth_user_id))
                is_vip = bool(snap0.get("is_vip_active"))
                if not is_vip:
                    from token_mvp_service import value_pack_allowed_models

                    allow_names = value_pack_allowed_models(db, int(auth_user_id))

            used_shared_catalog = None
            if billing_mode == "shared" and byok_stream is None:
                if getattr(request, "tools", None):
                    saw_error = True
                    error_detail = "tools_need_balance"
                    _finalize("failed", error_detail)
                    yield {"type": "error", "error": "tools_need_balance"}
                    return
                # 共享池：暂用非流整段后单 delta（避免阻塞主路径过久时仍可用）
                from free_shared import run_shared_pool_chat

                routed = run_shared_pool_chat(
                    prompt=request.prompt,
                    temperature=float(request.temperature or 0.7),
                    max_tokens=int(request.max_tokens or 1000),
                )
                # T13：取本次实际命中的上游目录用于聚合熔断
                for _a in getattr(routed, "attempts", None) or []:
                    if _a.get("ok") and _a.get("catalog_id"):
                        used_shared_catalog = _a["catalog_id"]
                        break
                if not routed.ok:
                    saw_error = True
                    error_detail = str(routed.error or "")[:200]
                    _finalize("failed", error_detail)
                    yield {"type": "error", "error": routed.error or "shared_failed"}
                    return
                full_text = str(routed.text or "")
                token_count = max(1, int(routed.token_count or 1))
                public_model = "shared"
                yield {"type": "meta", "public_model": "shared", "provider": routed.provider}
                if full_text:
                    yield {"type": "delta", "text": full_text}
                yield {
                    "type": "done",
                    "text": full_text,
                    "tokens": token_count,
                    "public_model": "shared",
                    "raw_model": routed.model,
                    "provider": routed.provider,
                }
                saw_done = True
            else:
                if auth_user_id is not None and byok_stream is None:
                    from token_mvp_service import reserve_tokens

                    reserve_tokens(
                        db,
                        int(auth_user_id),
                        need_tokens=estimate_need_tokens(
                            model=request.model,
                            max_tokens=int(request.max_tokens or 1000),
                            prompt=str(request.prompt or ""),
                        ),
                        model=request.model,
                        request_id=request_id,
                    )
                    hold_active = True
                stream_iter = byok_stream
                if stream_iter is None:
                    stream_iter = run_routed_chat_stream(
                        prompt=request.prompt,
                        requested_model=request.model,
                        is_vip=is_vip,
                        allow_names=allow_names,
                        temperature=float(request.temperature or 0.7),
                        max_tokens=int(request.max_tokens or 1000),
                        region_hint=region_hint,
                        messages=msgs if isinstance(msgs, list) else None,
                        tools=getattr(request, "tools", None),
                        tool_choice=getattr(request, "tool_choice", None),
                        include_reasoning=bool(
                            getattr(request, "include_reasoning", False)
                        ),
                    )
                from reasoning_filter import ThinkTagStreamScrubber, scrub_think_tags

                _reason_scrub = ThinkTagStreamScrubber(
                    include_reasoning=bool(
                        getattr(request, "include_reasoning", False)
                    )
                )
                for ev in stream_iter:
                    et = ev.get("type")
                    if et == "meta":
                        public_model = str(
                            ev.get("public_model")
                            or public_tier_name(
                                request.model or "flash",
                                layer=str(ev.get("layer") or ""),
                                upstream_model=str(ev.get("raw_model") or ""),
                            )
                        )
                        provider = str(ev.get("provider") or provider)
                        used_model = str(ev.get("raw_model") or used_model)
                        yield {
                            "type": "meta",
                            "public_model": public_model,
                            "raw_model": used_model,
                            "provider": provider,
                            "layer": ev.get("layer"),
                        }
                    elif et == "delta":
                        raw_piece = str(ev.get("text") or "")
                        if not bool(getattr(request, "include_reasoning", False)):
                            raw_piece = _reason_scrub.feed(raw_piece)
                        if not raw_piece:
                            continue
                        full_text += raw_piece
                        ev = {**ev, "text": raw_piece}
                        yield ev
                    elif et == "tool_calls_delta":
                        yield ev
                    elif et == "done":
                        if not bool(getattr(request, "include_reasoning", False)):
                            _tail = _reason_scrub.flush()
                            if _tail:
                                full_text += _tail
                                yield {"type": "delta", "text": _tail}
                        saw_done = True
                        full_text = str(ev.get("text") or full_text)
                        if not bool(getattr(request, "include_reasoning", False)):
                            full_text = scrub_think_tags(full_text)
                        token_count = max(1, int(ev.get("tokens") or 1))
                        try:
                            if ev.get("prompt_tokens") is not None:
                                prompt_tokens = max(0, int(ev.get("prompt_tokens") or 0))
                            if ev.get("completion_tokens") is not None:
                                completion_tokens = max(0, int(ev.get("completion_tokens") or 0))
                        except (TypeError, ValueError):
                            pass
                        public_model = str(ev.get("public_model") or public_model)
                        used_model = str(ev.get("raw_model") or used_model)
                        provider = str(ev.get("provider") or provider)
                        if provider == "stub" and not full_text:
                            billable = False
                        yield {
                            "type": "done",
                            "text": full_text,
                            "tokens": token_count,
                            "public_model": public_model,
                            "raw_model": used_model,
                            "provider": provider,
                            "tool_calls": ev.get("tool_calls"),
                            "finish_reason": ev.get("finish_reason") or "stop",
                            "tool_calls_streamed": bool(
                                ev.get("tool_calls_streamed")
                            ),
                        }
                    elif et == "error":
                        saw_error = True
                        error_detail = str(ev.get("error") or "")[:200]
                        if error_detail == "upstream_busy" or ev.get("error_kind") == "busy":
                            _finalize("failed", "upstream_busy")
                            raise HTTPException(
                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="模型服务暂时繁忙，请稍后再试。",
                            )
                        _finalize("failed", error_detail)
                        yield ev
                        return
                if not saw_done:
                    saw_error = True
                    error_detail = "stream_incomplete"
                    _finalize("failed", error_detail)
                    yield {"type": "error", "error": "stream_incomplete"}
                    return
        except GeneratorExit:
            # 消费方提前退出（SSE 层 done 后 return / 客户端断开）：已完成补记账，未完成标 interrupted
            _finalize("completed" if (saw_done and not saw_error) else "interrupted")
            raise
        except HTTPException:
            _finalize("failed", error_detail)
            raise
        except BaseException as e:
            _finalize("failed", str(e)[:300])
            raise
        finally:
            # 兜底：任何路径（正常/return/异常/GeneratorExit）都保证状态收尾与记账
            if not finalized:
                _finalize("completed" if (saw_done and not saw_error) else "interrupted")
    @staticmethod
    def preflight_stream(
        db: Session, request: ChatRequestSchema, auth_user_id: Optional[int]
    ) -> None:
        """流式路由启动前预检（2026-08-12）：余额/共享工具限制在首字节前返回 402。

        流一旦开始无法改状态码，预检保证「VIP 拦截/余额不足 → 正确 402/403，
        不记账」，与 /v1/chat/run 非流式语义一致。
        """
        if auth_user_id is None:
            return
        try:
            from byok_bridge import has_byok_coverage

            if has_byok_coverage(db, int(auth_user_id), request.model):
                return
        except Exception:
            pass
        from free_shared import resolve_chat_billing_mode

        billing = resolve_chat_billing_mode(
            db,
            auth_user_id=int(auth_user_id),
            requested_model=request.model,
            force_shared=False,
        )
        mode = str(billing.get("mode") or "paid")
        if mode == "shared":
            if getattr(request, "tools", None):
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="工具调用需有可用余额，请先充值后再试。",
                )
            return
        from token_mvp_service import assert_can_spend

        assert_can_spend(
            db,
            int(auth_user_id),
            need_tokens=estimate_need_tokens(
                model=request.model,
                max_tokens=int(request.max_tokens or 1000),
                prompt=str(request.prompt or ""),
            ),
            model=request.model,
        )

    @staticmethod
    def _generate_response(prompt: str) -> str:
        """生成回复（模拟AI响应）"""
        # 实际项目中这里会调用真实的AI API
        # 这里返回一个模拟回复
        responses = {
            "你好": "你好！我是AI24X副脑01，很高兴为您服务。",
            "python": "Python是一种高级编程语言，以其简洁易读的语法而闻名。它广泛应用于Web开发、数据分析、人工智能等领域。",
            "fastapi": "FastAPI是一个现代、快速（高性能）的Web框架，用于构建API。它基于Python 3.6+，使用类型提示，并自动生成API文档。",
            "postgresql": "PostgreSQL是一个强大的开源关系型数据库系统，以其可靠性、功能丰富性和性能而闻名。"
        }
        
        prompt_lower = prompt.lower()
        for key, response in responses.items():
            if key in prompt_lower:
                return response
        
        # 默认回复
        return f"我已经收到您的请求：'{prompt[:50]}...'。作为AI24X副脑01，我专注于编程相关任务，包括代码编写、功能实现、接口逻辑、数据库设计等。请告诉我具体的开发需求。"


class AuthService:
    @staticmethod
    def authenticate_user(db: Session, api_key: Optional[str] = None, user_id: Optional[str] = None) -> Optional[User]:
        """用户认证"""
        if api_key:
            user = UserService.get_user_by_api_key(db, api_key)
        elif user_id:
            user = UserService.get_user_by_id(db, user_id)
        else:
            return None
        
        if user and user.is_active:
            return user
        return None
    
    @staticmethod
    def determine_user_type(api_key: Optional[str] = None) -> UserType:
        """确定用户类型（免费/VIP）"""
        # 实际项目中这里会有更复杂的逻辑
        # 例如：检查API key前缀、查询数据库等
        if api_key and api_key.startswith("sk_vip_"):
            return UserType.VIP
        return UserType.FREE
