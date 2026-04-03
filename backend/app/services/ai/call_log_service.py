"""
AI 调用日志服务 / AI Call Log Service

使用 Celery 异步记录 AI 调用日志，不阻塞主请求
Uses Celery to asynchronously record AI call logs without blocking main requests.
"""

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any

from app.core.base_model import utc_now
from app.core.base_service import BaseService
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum, CallTypeEnum
from app.models.ai import AICallLog
from app.repositories.ai import AICallLogRepository

logger = LogManager.get_logger("ai.call_log")


def _normalize_trace_for_call_log(
    explicit_trace_id: str | None,
    *,
    use_context_var: bool,
) -> str | None:
    """Resolve trace_id for AICallLog (explicit arg or request context var)."""
    tid: str | None = None
    if explicit_trace_id is not None and str(explicit_trace_id).strip():
        tid = str(explicit_trace_id).strip()
    elif use_context_var:
        from app.middleware.trace import trace_id_var

        raw = trace_id_var.get()
        tid = str(raw).strip() if raw else None
    if not tid:
        return None
    return tid[:64] if len(tid) > 64 else tid


def _normalize_tool_call_id_for_call_log(tool_call_id: str | None) -> str | None:
    if not tool_call_id or not str(tool_call_id).strip():
        return None
    s = str(tool_call_id).strip()
    return s[:128] if len(s) > 128 else s


def _normalize_call_type_for_call_log(call_type: str | None) -> str:
    """Normalize call type before persistence / 落库前归一化调用类型。"""
    text = str(call_type or "").strip()
    if text in CallTypeEnum.values():
        return text
    return CallTypeEnum.MAIN_CHAT.value


class CallLogService(BaseService[AICallLog, AICallLogRepository]):
    """
    AI 调用日志服务 / AI Call Log Service.

    异步记录 AI 调用日志，支持请求/响应脱敏和截断
    """

    model = AICallLog
    repository_class = AICallLogRepository

    # 响应体截断阈值 (10KB)
    RESPONSE_TRUNCATE_THRESHOLD = 10 * 1024
    TRUNCATED_MARKER = "...truncated"
    MAX_LATENCY_MS = 2_147_483_647

    @staticmethod
    def _sanitize_request(request_data: dict) -> dict:
        """
        请求体脱敏处理 / Request body sanitization.

        Args:
            request_data: 请求数据 / Request data

        Returns:
            脱敏后的请求数据 / Sanitized request data
        """
        if not request_data:
            return request_data

        sanitized = request_data.copy()

        # 脱敏 API Key
        if "api_key" in sanitized:
            api_key = str(sanitized["api_key"])
            if len(api_key) > 8:
                sanitized["api_key"] = f"{api_key[:4]}...{api_key[-4:]}"

        # 脱敏其他敏感字段 / Redact other sensitive fields
        sensitive_fields = ["password", "token", "secret", "authorization"]
        for field in sensitive_fields:
            if field in sanitized:
                value = str(sanitized[field])
                if len(value) > 8:
                    sanitized[field] = f"{value[:4]}...{value[-4:]}"

        return sanitized

    @staticmethod
    def _truncate_response(response_data: Any) -> Any:
        """
        响应体截断处理 / Response body truncation.

        超过阈值时截断，避免大字段影响性能

        Args:
            response_data: 响应数据

        Returns:
            截断后的响应数据
        """
        if not response_data:
            return response_data

        # 转换为字符串检查大小（default=str 处理 Decimal 等特殊类型）
        response_str = json.dumps(response_data, ensure_ascii=False, default=str)

        if (
            len(response_str.encode("utf-8"))
            > CallLogService.RESPONSE_TRUNCATE_THRESHOLD
        ):
            # 截断并添加标记 / Truncate and add marker
            return {
                "truncated": True,
                "size": len(response_str),
                "preview": response_str[:1024] + CallLogService.TRUNCATED_MARKER,
            }

        return response_data

    @staticmethod
    def _generate_request_hash(
        model_id: int,
        messages: list,
        temperature: float,
        tools: list | None,
        tool_choice: str | None = None,
    ) -> str:
        """
        生成请求哈希（用于缓存命中检测）/ Generate request hash for cache hit detection.

        Args:
            model_id: 模型 ID
            messages: 消息列表
            temperature: 温度
            tools: 工具列表

        Returns:
            SHA256 哈希
        """
        params = {
            "model_id": model_id,
            "messages": messages,
            "temperature": temperature,
            "tools": tools,
            "tool_choice": tool_choice,
        }

        params_str = json.dumps(params, sort_keys=True)
        return hashlib.sha256(params_str.encode()).hexdigest()

    @classmethod
    def _normalize_latency_ms(cls, latency_ms: Any) -> int | None:
        """Normalize latency for DB persistence / 标准化延迟字段以便安全落库。"""
        if latency_ms is None:
            return None

        try:
            value = int(latency_ms)
        except (TypeError, ValueError):
            logger.warning("Invalid AI call latency discarded: raw={}", latency_ms)
            return None

        if value < 0:
            logger.warning("Negative AI call latency discarded: raw={}", value)
            return None

        if value > cls.MAX_LATENCY_MS:
            logger.warning(
                "Overflow AI call latency discarded: raw={} max={}",
                value,
                cls.MAX_LATENCY_MS,
            )
            return None

        return value

    @staticmethod
    def _to_non_empty_str(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @staticmethod
    def _normalize_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
        return None

    @classmethod
    def _normalize_turn_record_payload(cls, turn_record: Any) -> dict[str, Any] | None:
        if turn_record is None:
            return None
        if isinstance(turn_record, dict):
            return dict(turn_record)
        if is_dataclass(turn_record) and not isinstance(turn_record, type):
            try:
                payload = asdict(turn_record)
            except Exception:
                payload = None
            if isinstance(payload, dict):
                return payload
            return None
        if hasattr(turn_record, "__dict__"):
            return {
                str(key): value
                for key, value in vars(turn_record).items()
                if not str(key).startswith("_")
            }
        return None

    @classmethod
    def _normalize_context_sources(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        normalized_sources: list[dict[str, Any]] = []
        for raw in value:
            if isinstance(raw, dict):
                source = dict(raw)
            elif hasattr(raw, "__dict__"):
                source = {
                    str(key): item
                    for key, item in vars(raw).items()
                    if not str(key).startswith("_")
                }
            else:
                continue

            metadata = source.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            normalized_sources.append(
                {
                    "kind": str(source.get("kind") or "").strip(),
                    "name": str(source.get("name") or "").strip(),
                    "active": bool(source.get("active", True)),
                    "metadata": dict(metadata),
                }
            )
        return normalized_sources

    @classmethod
    def _normalize_fallback_history(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        normalized_history: list[dict[str, Any]] = []
        for raw in value:
            if isinstance(raw, dict):
                item = dict(raw)
            elif is_dataclass(raw) and not isinstance(raw, type):
                try:
                    payload = asdict(raw)
                except Exception:
                    payload = None
                if not isinstance(payload, dict):
                    continue
                item = payload
            elif hasattr(raw, "__dict__"):
                item = {
                    str(key): item_value
                    for key, item_value in vars(raw).items()
                    if not str(key).startswith("_")
                }
            else:
                continue

            from_protocol = cls._to_non_empty_str(item.get("from_protocol"))
            to_protocol = cls._to_non_empty_str(item.get("to_protocol"))
            reason = cls._to_non_empty_str(item.get("reason"))
            metadata = item.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}

            if not (from_protocol or to_protocol or reason):
                continue

            normalized_history.append(
                {
                    "from_protocol": from_protocol,
                    "to_protocol": to_protocol,
                    "reason": reason,
                    "recovered": bool(item.get("recovered", False)),
                    "metadata": dict(metadata),
                }
            )
        return normalized_history

    @classmethod
    def _pick_first_bool(cls, values: list[Any]) -> bool | None:
        for raw in values:
            parsed = cls._normalize_bool(raw)
            if parsed is not None:
                return parsed
        return None

    @classmethod
    def _inject_turn_hints(
        cls,
        request_data: dict[str, Any] | None,
        *,
        turn_record: Any = None,
        selected_tool_names: list[str] | None = None,
        selected_skill_names: list[str] | None = None,
        protocol_path: str | None = None,
        context_sources: list[dict[str, Any]] | None = None,
        fallback_history: list[dict[str, Any]] | None = None,
        sync_rescue: bool | None = None,
        should_record_call_log: bool | None = None,
    ) -> dict[str, Any]:
        payload = dict(request_data or {})
        normalized_turn_record = (
            cls._normalize_turn_record_payload(payload.get("turn_record")) or {}
        )

        incoming_turn_record = cls._normalize_turn_record_payload(turn_record)
        if incoming_turn_record:
            normalized_turn_record.update(incoming_turn_record)

        normalized_tools = cls._normalize_string_list(
            selected_tool_names
            if selected_tool_names is not None
            else normalized_turn_record.get("selected_tool_names")
        )
        normalized_skills = cls._normalize_string_list(
            selected_skill_names
            if selected_skill_names is not None
            else normalized_turn_record.get("selected_skill_names")
        )
        normalized_protocol = cls._to_non_empty_str(
            protocol_path
            if protocol_path is not None
            else normalized_turn_record.get("protocol_path")
        )
        normalized_sources = cls._normalize_context_sources(
            context_sources
            if context_sources is not None
            else normalized_turn_record.get("context_sources")
        )
        normalized_fallback = cls._normalize_fallback_history(
            fallback_history
            if fallback_history is not None
            else normalized_turn_record.get("fallback_history")
        )

        sync_rescue_value = cls._pick_first_bool(
            [
                sync_rescue,
                (
                    normalized_turn_record.get("metadata", {}).get("sync_rescue")
                    if isinstance(normalized_turn_record.get("metadata"), dict)
                    else None
                ),
                normalized_turn_record.get("sync_rescue"),
            ]
        )
        should_record_value = cls._pick_first_bool(
            [
                should_record_call_log,
                (
                    normalized_turn_record.get("metadata", {}).get(
                        "should_record_call_log"
                    )
                    if isinstance(normalized_turn_record.get("metadata"), dict)
                    else None
                ),
                normalized_turn_record.get("should_record_call_log"),
            ]
        )

        if normalized_tools:
            payload["selected_tool_names"] = normalized_tools
            normalized_turn_record["selected_tool_names"] = normalized_tools
        if normalized_skills:
            payload["selected_skill_names"] = normalized_skills
            normalized_turn_record["selected_skill_names"] = normalized_skills
        if normalized_protocol:
            payload["protocol_path"] = normalized_protocol
            normalized_turn_record["protocol_path"] = normalized_protocol
        if normalized_sources:
            payload["context_sources"] = normalized_sources
            normalized_turn_record["context_sources"] = normalized_sources
        if normalized_fallback:
            payload["fallback_history"] = normalized_fallback
            normalized_turn_record["fallback_history"] = normalized_fallback
        if sync_rescue_value is not None:
            payload["sync_rescue"] = sync_rescue_value
            metadata = (
                dict(normalized_turn_record.get("metadata") or {})
                if isinstance(normalized_turn_record.get("metadata"), dict)
                else {}
            )
            metadata["sync_rescue"] = sync_rescue_value
            normalized_turn_record["metadata"] = metadata
        if should_record_value is not None:
            payload["should_record_call_log"] = should_record_value
            metadata = (
                dict(normalized_turn_record.get("metadata") or {})
                if isinstance(normalized_turn_record.get("metadata"), dict)
                else {}
            )
            metadata["should_record_call_log"] = should_record_value
            normalized_turn_record["metadata"] = metadata

        if normalized_turn_record:
            payload["turn_record"] = normalized_turn_record
        return payload

    @classmethod
    def _build_turn_diagnostics(
        cls,
        *,
        request_data: dict[str, Any] | None,
        response_data: dict[str, Any] | None,
        status: str,
        error_message: str | None,
    ) -> dict[str, Any]:
        req = request_data if isinstance(request_data, dict) else {}
        rsp = response_data if isinstance(response_data, dict) else {}

        turn_record = cls._normalize_turn_record_payload(
            req.get("turn_record")
        ) or cls._normalize_turn_record_payload(rsp.get("turn_record"))
        turn_record_metadata = (
            dict((turn_record or {}).get("metadata") or {})
            if isinstance((turn_record or {}).get("metadata"), dict)
            else {}
        )
        incoming = (
            req.get("turn_diagnostics")
            if isinstance(req.get("turn_diagnostics"), dict)
            else {}
        )

        turn_outcome = cls._to_non_empty_str(
            (turn_record or {}).get("turn_outcome")
            or incoming.get("turn_outcome")
            or req.get("turn_outcome")
        )
        termination_reason = cls._to_non_empty_str(
            (turn_record or {}).get("termination_reason")
            or incoming.get("termination_reason")
            or req.get("termination_reason")
        )
        protocol_path = cls._to_non_empty_str(
            (turn_record or {}).get("protocol_path")
            or incoming.get("protocol_path")
            or req.get("protocol_path")
        )
        selected_tool_names = cls._normalize_string_list(
            (turn_record or {}).get("selected_tool_names")
            or incoming.get("selected_tool_names")
            or req.get("selected_tool_names")
        )
        selected_skill_names = cls._normalize_string_list(
            (turn_record or {}).get("selected_skill_names")
            or incoming.get("selected_skill_names")
            or req.get("selected_skill_names")
        )
        context_sources = (
            cls._normalize_context_sources((turn_record or {}).get("context_sources"))
            or cls._normalize_context_sources(incoming.get("context_sources"))
            or cls._normalize_context_sources(req.get("context_sources"))
        )
        fallback_history = (
            cls._normalize_fallback_history((turn_record or {}).get("fallback_history"))
            or cls._normalize_fallback_history(incoming.get("fallback_history"))
            or cls._normalize_fallback_history(req.get("fallback_history"))
        )
        sync_rescue = cls._pick_first_bool(
            [
                turn_record_metadata.get("sync_rescue"),
                (turn_record or {}).get("sync_rescue"),
                incoming.get("sync_rescue"),
                req.get("sync_rescue"),
            ]
        )
        should_record_call_log = cls._pick_first_bool(
            [
                turn_record_metadata.get("should_record_call_log"),
                (turn_record or {}).get("should_record_call_log"),
                incoming.get("should_record_call_log"),
                req.get("should_record_call_log"),
            ]
        )

        if not turn_outcome:
            turn_outcome = (
                "success" if status == CallStatusEnum.SUCCESS.value else "failed"
            )
        if not termination_reason:
            termination_reason = (
                "completed" if status == CallStatusEnum.SUCCESS.value else "error"
            )

        diagnostics: dict[str, Any] = {
            "turn_outcome": turn_outcome,
            "termination_reason": termination_reason,
            "selected_tool_names": selected_tool_names,
            "selected_skill_names": selected_skill_names,
            "context_sources": context_sources,
        }
        if protocol_path:
            diagnostics["protocol_path"] = protocol_path
        if fallback_history:
            diagnostics["fallback_history"] = fallback_history
        if sync_rescue is not None:
            diagnostics["sync_rescue"] = sync_rescue
        if should_record_call_log is not None:
            diagnostics["should_record_call_log"] = should_record_call_log
        if turn_record:
            diagnostics["turn_record"] = turn_record
        if status != CallStatusEnum.SUCCESS.value and error_message:
            diagnostics["error_message"] = error_message
        return diagnostics

    async def log_call(
        self,
        tenant_id: int,
        model_id: int,
        provider_id: int,
        request_type: str,
        request_data: dict,
        response_data: dict | None,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float,
        latency_ms: int,
        status: str = CallStatusEnum.SUCCESS.value,
        error_message: str | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
        trace_id: str | None = None,
        tool_call_id: str | None = None,
        turn_record: dict[str, Any] | None = None,
        protocol_path: str | None = None,
        context_sources: list[dict[str, Any]] | None = None,
        selected_tool_names: list[str] | None = None,
        selected_skill_names: list[str] | None = None,
        fallback_history: list[dict[str, Any]] | None = None,
        sync_rescue: bool | None = None,
        should_record_call_log: bool | None = None,
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
    ) -> AICallLog:
        """
        记录调用日志 / Record call log.

        Args:
            tenant_id: 企业 ID
            model_id: 模型 ID
            provider_id: 供应商 ID
            request_type: 请求类型
            request_data: 请求数据
            response_data: 响应数据
            input_tokens: 输入 tokens
            output_tokens: 输出 tokens
            total_tokens: 总 tokens
            cost: 费用
            latency_ms: 延迟
            status: 调用状态
            error_message: 错误信息
            user_id: 用户 ID
            user_type: 用户类型
            agent_id: 智能体 ID
            conversation_id: 对话 ID
            routed_model_id: 路由后模型 ID
            route_reason: 路由原因

        Returns:
            AICallLog 实例
        """
        request_payload = self._inject_turn_hints(
            request_data,
            turn_record=turn_record,
            selected_tool_names=selected_tool_names,
            selected_skill_names=selected_skill_names,
            protocol_path=protocol_path,
            context_sources=context_sources,
            fallback_history=fallback_history,
            sync_rescue=sync_rescue,
            should_record_call_log=should_record_call_log,
        )
        turn_diagnostics = self._build_turn_diagnostics(
            request_data=request_payload,
            response_data=response_data,
            status=status,
            error_message=error_message,
        )
        if turn_diagnostics:
            request_payload["turn_diagnostics"] = turn_diagnostics
        if isinstance(turn_diagnostics.get("turn_record"), dict):
            request_payload["turn_record"] = turn_diagnostics["turn_record"]

        # 脱敏和截断处理 / Redact and truncate
        sanitized_request = self._sanitize_request(request_payload)
        truncated_response = self._truncate_response(response_data)

        # 生成请求哈希 / Generate request hash
        messages = request_payload.get("messages", [])
        temperature = request_payload.get("temperature", 0.7)
        tools = request_payload.get("tools")
        tool_choice = request_payload.get("tool_choice")
        request_hash = self._generate_request_hash(
            model_id,
            messages,
            temperature,
            tools,
            tool_choice=tool_choice,
        )

        # 创建日志记录 / Create log row
        billing_context = dict(billing_context or {})
        normalized_latency_ms = self._normalize_latency_ms(latency_ms)
        eff_trace = _normalize_trace_for_call_log(trace_id, use_context_var=True)
        eff_tool = _normalize_tool_call_id_for_call_log(tool_call_id)
        eff_call_type = _normalize_call_type_for_call_log(call_type)
        call_log = AICallLog(
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            billing_tenant_id=billing_context.get("billing_tenant_id"),
            actor_user_id=billing_context.get("actor_user_id", user_id),
            actor_user_type=billing_context.get("actor_user_type", user_type),
            access_channel=billing_context.get("access_channel"),
            agent_id=agent_id,
            conversation_id=conversation_id,
            trace_id=eff_trace,
            tool_call_id=eff_tool,
            provider_id=provider_id,
            model_id=model_id,
            request_type=request_type,
            call_type=eff_call_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=cost,
            latency_ms=normalized_latency_ms,
            status=status,
            error_message=error_message,
            request_hash=request_hash,
            request_metadata={
                "request": sanitized_request,
                "response": truncated_response,
                "turn_diagnostics": turn_diagnostics,
                "timestamp": utc_now().isoformat(),
                "agent_id": agent_id,
                "conversation_id": conversation_id,
                "routed_model_id": routed_model_id,
                "route_reason": route_reason,
            },
            routed_model_id=routed_model_id,
            route_reason=route_reason,
            agent_owner_type=billing_context.get("agent_owner_type"),
            agent_owner_tenant_id=billing_context.get("agent_owner_tenant_id"),
            agent_resource_scope=billing_context.get("agent_resource_scope"),
            tenant_publication_id=billing_context.get("tenant_publication_id"),
            publication_enabled_snapshot=billing_context.get(
                "publication_enabled_snapshot"
            ),
            publication_access_type_snapshot=billing_context.get(
                "publication_access_type_snapshot"
            ),
            agent_id_snapshot=billing_context.get("agent_id_snapshot", agent_id),
            agent_name_snapshot=billing_context.get("agent_name_snapshot"),
            billing_tenant_name_snapshot=billing_context.get(
                "billing_tenant_name_snapshot"
            ),
            model_name_snapshot=billing_context.get("model_name_snapshot"),
            provider_name_snapshot=billing_context.get("provider_name_snapshot"),
        )

        self.db.add(call_log)
        await self.db.flush()

        logger.info(
            "AI call logged | tenant_id={} model_id={} total_tokens={} cost={} status={}",
            tenant_id,
            model_id,
            total_tokens,
            cost,
            status,
        )

        return call_log

    async def get_statistics(
        self,
        tenant_id: int | None = None,
        start_date=None,
        end_date=None,
        group_by: str = "daily",
    ):
        """获取调用统计信息（委托给 Repository） / Get call stats (delegate to repo)."""
        return await self.repo.get_statistics(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )

    async def get_overall_summary(
        self,
        tenant_id: int | None = None,
        start_date=None,
        end_date=None,
    ):
        """获取调用汇总统计（委托给 Repository） / Get call summary (delegate to repo)."""
        return await self.repo.get_overall_summary(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_failed_logs(
        self,
        tenant_id: int | None = None,
        start_date=None,
        limit: int = 100,
    ):
        """获取失败的调用日志（委托给 Repository） / Get failed call logs (delegate to repo)."""
        return await self.repo.get_failed_logs(
            tenant_id=tenant_id,
            start_date=start_date,
            limit=limit,
        )

    async def query_list_with_names(
        self,
        spec,
        *,
        include_caller_names: bool = False,
    ):
        """带名称字段查询日志列表 / Query call logs with related display names."""
        return await self.repo.query_list_with_names(
            spec,
            include_caller_names=include_caller_names,
        )

    async def log_call_async(
        self,
        tenant_id: int,
        model_id: int,
        provider_id: int,
        request_type: str,
        request_data: dict,
        response_data: dict | None,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float,
        latency_ms: int,
        status: str = CallStatusEnum.SUCCESS.value,
        error_message: str | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
        trace_id: str | None = None,
        tool_call_id: str | None = None,
        turn_record: dict[str, Any] | None = None,
        protocol_path: str | None = None,
        context_sources: list[dict[str, Any]] | None = None,
        selected_tool_names: list[str] | None = None,
        selected_skill_names: list[str] | None = None,
        fallback_history: list[dict[str, Any]] | None = None,
        sync_rescue: bool | None = None,
        should_record_call_log: bool | None = None,
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
    ):
        """
        异步记录调用日志 (通过 Celery) / Record call log asynchronously via Celery.

        Args:
            同 log_call / Same as log_call.
        """
        from app.tasks.ai import log_ai_call_task

        normalized_latency_ms = self._normalize_latency_ms(latency_ms)
        eff_trace = _normalize_trace_for_call_log(trace_id, use_context_var=True)
        eff_tool = _normalize_tool_call_id_for_call_log(tool_call_id)
        eff_call_type = _normalize_call_type_for_call_log(call_type)
        request_payload = self._inject_turn_hints(
            request_data,
            turn_record=turn_record,
            selected_tool_names=selected_tool_names,
            selected_skill_names=selected_skill_names,
            protocol_path=protocol_path,
            context_sources=context_sources,
            fallback_history=fallback_history,
            sync_rescue=sync_rescue,
            should_record_call_log=should_record_call_log,
        )
        turn_diagnostics = self._build_turn_diagnostics(
            request_data=request_payload,
            response_data=response_data,
            status=status,
            error_message=error_message,
        )
        if turn_diagnostics:
            request_payload["turn_diagnostics"] = turn_diagnostics
        if isinstance(turn_diagnostics.get("turn_record"), dict):
            request_payload["turn_record"] = turn_diagnostics["turn_record"]

        # 发送 Celery 任务
        log_ai_call_task.delay(
            tenant_id=tenant_id,
            model_id=model_id,
            provider_id=provider_id,
            request_type=request_type,
            request_data=request_payload,
            response_data=response_data,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=float(cost),
            latency_ms=normalized_latency_ms,
            status=status,
            error_message=error_message,
            user_id=user_id,
            user_type=user_type,
            agent_id=agent_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            routed_model_id=routed_model_id,
            route_reason=route_reason,
            trace_id=eff_trace,
            tool_call_id=eff_tool,
            call_type=eff_call_type,
        )

        logger.debug(
            "AI call log queued | tenant_id={} model_id={}",
            tenant_id,
            model_id,
        )


__all__ = ["CallLogService"]
