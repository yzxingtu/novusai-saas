"""Captcha config helpers. / 验证码配置辅助函数。"""

from __future__ import annotations

from collections.abc import Iterable

from app.captcha.provider import CaptchaProviderMetadata
from app.captcha.registry import registry as captcha_registry
from app.core.i18n import _, get_locale
from app.plugins.preview import resolve_i18n

_CAPTCHA_PROVIDER_CONFIG_KEYS = {"captcha_provider", "tenant_captcha_provider"}


def _to_manifest_locale(locale: str) -> str:
    normalized = str(locale or "").strip()
    if normalized == "zh_CN":
        return "zh-CN"
    return normalized or "zh-CN"


def _resolve_provider_label(
    provider_code: str,
    metadata: CaptchaProviderMetadata | None,
) -> str:
    if metadata and metadata.display_name:
        return (
            resolve_i18n(
                metadata.display_name,
                locale=_to_manifest_locale(get_locale()),
            )
            or provider_code
        )
    return provider_code


def _supports_required_endpoints(
    provider_code: str,
    metadata: CaptchaProviderMetadata | None,
    required_endpoints: set[str],
) -> bool:
    if provider_code == "image":
        return True
    if not required_endpoints:
        return True

    endpoints = {
        str(item or "").strip().lower()
        for item in (metadata.public_endpoints if metadata else [])
    }
    return required_endpoints.issubset(endpoints)


def inject_captcha_provider_options(
    configs: list[dict],
    *,
    required_endpoints: Iterable[str],
    unavailable_label_key: str,
) -> None:
    """Inject registered captcha providers into config select options.
    / 将已注册验证码提供者动态注入配置下拉选项。
    """

    required = {
        str(item or "").strip().lower()
        for item in required_endpoints
        if str(item or "").strip()
    }

    for cfg in configs:
        if cfg.get("key") not in _CAPTCHA_PROVIDER_CONFIG_KEYS:
            continue
        if str(cfg.get("value_type") or "").strip().lower() != "select":
            continue

        existing_options = list(cfg.get("options") or [])
        existing_values = {
            str(opt.get("value") or "").strip() for opt in existing_options
        }

        dynamic_options: list[dict[str, str]] = []
        for provider_code, metadata in captcha_registry.items():
            code = str(provider_code or "").strip()
            if not code or code == "image":
                continue
            if code in existing_values:
                continue
            if not _supports_required_endpoints(code, metadata, required):
                continue

            dynamic_options.append(
                {
                    "value": code,
                    "label": _resolve_provider_label(code, metadata),
                }
            )

        dynamic_options.sort(key=lambda item: str(item["label"]).lower())
        cfg["options"] = [*existing_options, *dynamic_options]

        current_value = str(cfg.get("value") or "").strip()
        final_values = {str(opt.get("value") or "").strip() for opt in cfg["options"]}
        if current_value and current_value not in final_values:
            cfg["options"].append(
                {
                    "value": current_value,
                    "label": _(
                        unavailable_label_key,
                        provider=current_value,
                    ),
                }
            )
        break


__all__ = ["inject_captcha_provider_options"]
