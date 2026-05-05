"""Model request resolution and metadata helpers for OpenAI-compatible adapters."""

from __future__ import annotations

import json
from typing import Any

from app.ai.text_semantics import split_last_suffix
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")

RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES: tuple[str, ...] = (
    "gpt-5",
    "o1",
    "o3",
    "o4",
)
_SUPPORTED_REASONING_EFFORTS: tuple[str, ...] = (
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
)
_OPENAI_RUNTIME_OVERRIDE_PATHS: dict[str, str] = {
    "responses_reasoning_effort": (
        "runtime_overrides.openai_compatible.responses.reasoning.effort"
    ),
    "chat_completions_reasoning_effort": (
        "runtime_overrides.openai_compatible.chat_completions.reasoning_effort"
    ),
    "legacy_reasoning_effort": "reasoning.effort",
    "legacy_reasoning_effort_flat": "reasoning_effort",
    "legacy_reasoning_effort_camel": "reasoningEffort",
    "legacy_model_code_alias": "legacy_model_code_alias",
}


class OpenAIAdapterModelRequestMixin:
    """Shared effective-model resolution helpers extracted from the facade."""

    @staticmethod
    def _normalize_wire_api_value(wire_api: Any) -> str:
        from app.ai.adapters.openai_compatible.capabilities import normalize_wire_api

        return normalize_wire_api(wire_api)

    @staticmethod
    def _normalize_reasoning_effort(value: Any) -> str | None:
        normalized = str(value or "").strip().lower()
        if normalized in _SUPPORTED_REASONING_EFFORTS:
            return normalized
        return None

    @staticmethod
    def _extract_runtime_overrides(model_config: Any) -> dict[str, Any]:
        if not isinstance(model_config, dict):
            return {}
        runtime_overrides = model_config.get("runtime_overrides")
        if isinstance(runtime_overrides, dict):
            return runtime_overrides.copy()
        return {}

    @classmethod
    def _extract_protocol_reasoning_effort_override(
        cls,
        model_config: Any,
        *,
        wire_api: str,
    ) -> tuple[str | None, list[str], dict[str, str]]:
        runtime_overrides = cls._extract_runtime_overrides(model_config)
        openai_overrides = runtime_overrides.get("openai_compatible")
        if not isinstance(openai_overrides, dict):
            return (None, [], {})

        normalized_wire_api = (
            "responses"
            if str(wire_api or "").strip().lower() == "responses"
            else "chat_completions"
        )

        ignored_overrides: list[str] = []
        ignore_reasons: dict[str, str] = {}

        if normalized_wire_api == "responses":
            path = _OPENAI_RUNTIME_OVERRIDE_PATHS["responses_reasoning_effort"]
            responses_overrides = openai_overrides.get("responses")
            if not isinstance(responses_overrides, dict):
                return (None, ignored_overrides, ignore_reasons)
            reasoning = responses_overrides.get("reasoning")
            raw_effort = (
                reasoning.get("effort") if isinstance(reasoning, dict) else None
            )
        else:
            path = _OPENAI_RUNTIME_OVERRIDE_PATHS["chat_completions_reasoning_effort"]
            chat_overrides = openai_overrides.get("chat_completions")
            if not isinstance(chat_overrides, dict):
                return (None, ignored_overrides, ignore_reasons)
            raw_effort = chat_overrides.get("reasoning_effort")

        if raw_effort is None:
            return (None, ignored_overrides, ignore_reasons)

        normalized_effort = cls._normalize_reasoning_effort(raw_effort)
        if normalized_effort is None:
            ignored_overrides.append(path)
            ignore_reasons[path] = "invalid_value"
            return (None, ignored_overrides, ignore_reasons)

        return (normalized_effort, ignored_overrides, ignore_reasons)

    @classmethod
    def _extract_legacy_reasoning_effort_from_model_config(
        cls,
        model_config: Any,
    ) -> str | None:
        if not isinstance(model_config, dict):
            return None

        reasoning = model_config.get("reasoning")
        if isinstance(reasoning, dict):
            effort = cls._normalize_reasoning_effort(reasoning.get("effort"))
            if effort is not None:
                return effort

        return cls._normalize_reasoning_effort(
            model_config.get("reasoning_effort") or model_config.get("reasoningEffort"),
        )

    @classmethod
    def _get_runtime_overrides_for_provider(
        cls,
        model_config: Any,
        provider_type: str,
    ) -> dict[str, Any]:
        if not isinstance(model_config, dict):
            return {}
        runtime_overrides = model_config.get("runtime_overrides")
        if not isinstance(runtime_overrides, dict):
            return {}
        provider_overrides = runtime_overrides.get(provider_type)
        if not isinstance(provider_overrides, dict):
            return {}
        return dict(provider_overrides)

    @classmethod
    def _get_openai_protocol_override(
        cls,
        *,
        model_config: Any,
        wire_api: str | None,
    ) -> tuple[str | None, str | None]:
        provider_overrides = cls._get_runtime_overrides_for_provider(
            model_config,
            "openai_compatible",
        )
        normalized_wire_api = cls._normalize_wire_api_value(wire_api)
        protocol_overrides = provider_overrides.get(normalized_wire_api)
        if not isinstance(protocol_overrides, dict):
            return (None, None)

        if normalized_wire_api == "responses":
            reasoning = protocol_overrides.get("reasoning")
            if not isinstance(reasoning, dict):
                return (None, None)
            return (
                cls._normalize_reasoning_effort(reasoning.get("effort")),
                "runtime_overrides.openai_compatible.responses.reasoning.effort",
            )

        return (
            cls._normalize_reasoning_effort(protocol_overrides.get("reasoning_effort")),
            "runtime_overrides.openai_compatible.chat_completions.reasoning_effort",
        )

    @classmethod
    def _supports_reasoning_effort_model(cls, model: str) -> bool:
        normalized = str(model or "").strip().lower()
        if not normalized:
            return False
        return any(
            normalized.startswith(prefix)
            for prefix in RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES
        )

    @classmethod
    def _extract_legacy_reasoning_effort_from_model(
        cls,
        model: str,
    ) -> tuple[str, str | None]:
        normalized_model = str(model or "").strip()
        if not normalized_model:
            return ("", None)

        base_model, effort = split_last_suffix(
            normalized_model,
            separator="-",
            allowed_suffixes=("none", "minimal", "low", "medium", "high", "xhigh"),
        )
        if effort is None:
            return (normalized_model, None)

        if not any(
            base_model.lower().startswith(prefix)
            for prefix in RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES
        ):
            return (normalized_model, None)

        return (base_model, effort)

    @classmethod
    def resolve_effective_model_request(
        cls,
        *,
        model: str,
        model_config: Any = None,
        wire_api: str | None = None,
    ) -> dict[str, Any]:
        logical_model_code = str(model or "").strip()
        normalized_wire_api = cls._normalize_wire_api_value(wire_api)
        effective_request: dict[str, Any] = {
            "logical_model_code": logical_model_code,
            "upstream_model": logical_model_code,
            "reasoning_effort": None,
            "effective_params": {},
            "applied_overrides": [],
            "ignored_overrides": [],
            "ignore_reasons": {},
            "override_source": "model_code",
        }

        config_effort, config_path = cls._get_openai_protocol_override(
            model_config=model_config,
            wire_api=normalized_wire_api,
        )
        if config_path is not None:
            if config_effort is None:
                effective_request["ignored_overrides"].append(config_path)
                effective_request["ignore_reasons"][config_path] = "invalid_value"
            elif not cls._supports_reasoning_effort_model(logical_model_code):
                effective_request["ignored_overrides"].append(config_path)
                effective_request["ignore_reasons"][config_path] = (
                    "unsupported_model_family"
                )
            else:
                effective_request["reasoning_effort"] = config_effort
                effective_request["override_source"] = "runtime_overrides"
                effective_request["applied_overrides"].append(config_path)

        if effective_request["reasoning_effort"] is None:
            legacy_config_effort = (
                cls._extract_legacy_reasoning_effort_from_model_config(model_config)
            )
            if legacy_config_effort is not None:
                legacy_path = "config.reasoning.effort"
                if cls._supports_reasoning_effort_model(logical_model_code):
                    effective_request["reasoning_effort"] = legacy_config_effort
                    effective_request["override_source"] = "legacy_model_config"
                    effective_request["applied_overrides"].append(legacy_path)
                else:
                    effective_request["ignored_overrides"].append(legacy_path)
                    effective_request["ignore_reasons"][legacy_path] = (
                        "unsupported_model_family"
                    )

        upstream_model, legacy_effort = cls._extract_legacy_reasoning_effort_from_model(
            logical_model_code
        )
        if legacy_effort is not None:
            effective_request["upstream_model"] = upstream_model
            if effective_request["reasoning_effort"] is None:
                effective_request["reasoning_effort"] = legacy_effort
                effective_request["override_source"] = "legacy_model_code"
                effective_request["applied_overrides"].append(
                    "legacy_model_code_suffix"
                )

        if effective_request["reasoning_effort"] is not None:
            if normalized_wire_api == "responses":
                effective_request["effective_params"]["reasoning"] = {
                    "effort": effective_request["reasoning_effort"]
                }
            else:
                effective_request["effective_params"]["reasoning_effort"] = (
                    effective_request["reasoning_effort"]
                )

        return effective_request

    def _log_effective_model_request(
        self,
        *,
        effective_request: dict[str, Any],
        wire_api: str,
    ) -> None:
        logger.info(
            "AI model request resolved: provider_type=openai_compatible logical_model_code={} effective_upstream_model={} effective_reasoning_effort={} wire_api={} override_source={} applied_overrides={} ignored_overrides={} ignore_reasons={}",
            effective_request.get("logical_model_code", ""),
            effective_request.get("upstream_model", ""),
            effective_request.get("reasoning_effort", "") or "",
            wire_api,
            effective_request.get("override_source", ""),
            json.dumps(
                effective_request.get("applied_overrides", []), ensure_ascii=False
            ),
            json.dumps(
                effective_request.get("ignored_overrides", []), ensure_ascii=False
            ),
            json.dumps(effective_request.get("ignore_reasons", {}), ensure_ascii=False),
        )

    @staticmethod
    def _augment_request_metadata(
        metadata: dict[str, Any] | None,
        *,
        effective_request: dict[str, Any],
    ) -> dict[str, Any]:
        enriched = dict(metadata or {})
        enriched["logical_model_code"] = effective_request.get("logical_model_code")
        enriched["effective_upstream_model"] = effective_request.get("upstream_model")
        if effective_request.get("reasoning_effort") is not None:
            enriched["effective_reasoning_effort"] = effective_request.get(
                "reasoning_effort"
            )
        enriched["effective_params"] = dict(
            effective_request.get("effective_params", {}) or {}
        )
        enriched["applied_overrides"] = list(
            effective_request.get("applied_overrides", []) or []
        )
        enriched["ignored_overrides"] = list(
            effective_request.get("ignored_overrides", []) or []
        )
        enriched["ignore_reasons"] = dict(
            effective_request.get("ignore_reasons", {}) or {}
        )
        enriched["model_override_source"] = effective_request.get("override_source")
        return enriched

    @classmethod
    def _apply_runtime_reasoning_effort_override(
        cls,
        effective_request: dict[str, Any],
        *,
        reasoning_effort: Any,
        wire_api: str,
    ) -> dict[str, Any]:
        override = cls._normalize_reasoning_effort(reasoning_effort)
        if override is None:
            return effective_request

        marker = "runtime_reasoning_effort_override"
        logical_model_code = str(
            effective_request.get("logical_model_code")
            or effective_request.get("upstream_model")
            or ""
        )
        if not cls._supports_reasoning_effort_model(logical_model_code):
            ignored_overrides = list(
                effective_request.get("ignored_overrides", []) or []
            )
            if marker not in ignored_overrides:
                ignored_overrides.append(marker)
            ignore_reasons = dict(effective_request.get("ignore_reasons", {}) or {})
            ignore_reasons[marker] = "unsupported_model_family"
            effective_request["ignored_overrides"] = ignored_overrides
            effective_request["ignore_reasons"] = ignore_reasons
            return effective_request

        effective_request["reasoning_effort"] = override
        effective_request["override_source"] = "runtime_call_override"
        applied_overrides = list(effective_request.get("applied_overrides", []) or [])
        if marker not in applied_overrides:
            applied_overrides.append(marker)
        effective_request["applied_overrides"] = applied_overrides

        normalized_wire_api = cls._normalize_wire_api_value(wire_api)
        effective_params = dict(effective_request.get("effective_params", {}) or {})
        if normalized_wire_api == "responses":
            effective_params["reasoning"] = {"effort": override}
            effective_params.pop("reasoning_effort", None)
        else:
            effective_params["reasoning_effort"] = override
            effective_params.pop("reasoning", None)
        effective_request["effective_params"] = effective_params
        return effective_request


__all__ = [
    "OpenAIAdapterModelRequestMixin",
    "RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES",
]
