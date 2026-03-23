"""Slider captcha provider. / 滑动拼图验证码提供者。"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.captcha.provider import (
    CaptchaChallenge,
    CaptchaVerificationResult,
    ICaptchaProvider,
)
from app.core.base_model import utc_now

_BUNDLED_BACKGROUND_COUNT = 4
_CHALLENGE_TTL_SECONDS = 120


class SliderCaptchaProvider(ICaptchaProvider):
    """In-memory slider captcha provider. / 基于内存的滑动拼图验证码提供者。"""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def _now(self) -> datetime:
        return utc_now()

    def _gc(self) -> None:
        now = self._now()
        expired_keys = [
            key
            for key, item in self._store.items()
            if item.get("used") or item.get("expires_at") <= now
        ]
        for key in expired_keys:
            self._store.pop(key, None)

    @staticmethod
    def _clamp_int(
        value: Any,
        *,
        minimum: int,
        maximum: int,
        default: int,
    ) -> int:
        try:
            parsed = int(value)
        except Exception:
            return default
        return max(minimum, min(maximum, parsed))

    @staticmethod
    def _resolve_background_url(value: Any) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None

        if raw.isdigit():
            attachment_id = int(raw)
            if attachment_id > 0:
                return f"/api/public/attachments/{attachment_id}/image"
            return None

        return raw

    def _pick_background(self, plugin_config: dict[str, Any]) -> dict[str, Any]:
        background_index = random.randint(0, _BUNDLED_BACKGROUND_COUNT - 1)
        background_value = plugin_config.get(f"background_{background_index + 1}")
        payload = {"background_index": background_index}

        resolved = self._resolve_background_url(background_value)
        if resolved:
            payload["background_url"] = resolved
        return payload

    @staticmethod
    def _parse_solution_offset(solution: str) -> int | None:
        raw = str(solution or "").strip()
        if not raw:
            return None

        try:
            return int(round(float(raw)))
        except Exception:
            pass

        try:
            data = json.loads(raw)
        except Exception:
            return None

        if not isinstance(data, dict):
            return None

        for key in ("offset", "x", "left", "moveX"):
            value = data.get(key)
            if value is None:
                continue
            try:
                return int(round(float(value)))
            except Exception:
                continue
        return None

    async def generate_challenge(self, ctx: dict[str, Any]) -> CaptchaChallenge:
        self._gc()

        plugin_config = (
            ctx.get("plugin_config")
            if isinstance(ctx.get("plugin_config"), dict)
            else {}
        ) or {}

        canvas_width = 320
        canvas_height = 180
        square_length = self._clamp_int(
            plugin_config.get("square_length"),
            minimum=36,
            maximum=54,
            default=42,
        )
        circle_radius = max(8, min(14, int(round(square_length * 0.24))))
        tolerance_px = self._clamp_int(
            plugin_config.get("tolerance_px"),
            minimum=3,
            maximum=12,
            default=6,
        )

        piece_length = square_length + 2 * circle_radius + 3
        piece_x = random.randint(
            piece_length,
            canvas_width - piece_length,
        )
        piece_y = random.randint(
            3 * circle_radius,
            canvas_height - piece_length,
        )

        challenge_id = uuid.uuid4().hex
        expires_at = self._now() + timedelta(seconds=_CHALLENGE_TTL_SECONDS)

        self._store[challenge_id] = {
            "expires_at": expires_at,
            "piece_x": piece_x,
            "tolerance_px": tolerance_px,
            "used": False,
        }

        payload = {
            "canvas_height": canvas_height,
            "canvas_width": canvas_width,
            "circle_radius": circle_radius,
            "piece_x": piece_x,
            "piece_y": piece_y,
            "square_length": square_length,
            "tolerance_px": tolerance_px,
            **self._pick_background(plugin_config),
        }

        return CaptchaChallenge(
            challenge_id=challenge_id,
            type="slider",
            payload=payload,
            expires_at=expires_at,
            token=None,
        )

    async def verify(
        self,
        challenge_id: str,
        solution: str,
        ctx: dict[str, Any],
    ) -> CaptchaVerificationResult:
        _ = ctx
        self._gc()

        item = self._store.get(challenge_id)
        if not item:
            return CaptchaVerificationResult(ok=False, reason="not_found", score=None)

        if item.get("used"):
            return CaptchaVerificationResult(ok=False, reason="used", score=None)

        expires_at = item.get("expires_at")
        if not isinstance(expires_at, datetime) or self._now() > expires_at:
            self._store.pop(challenge_id, None)
            return CaptchaVerificationResult(ok=False, reason="expired", score=None)

        offset = self._parse_solution_offset(solution)
        if offset is None:
            return CaptchaVerificationResult(ok=False, reason="invalid_solution", score=None)

        expected = int(item.get("piece_x") or 0)
        tolerance_px = int(item.get("tolerance_px") or 6)
        if abs(offset - expected) > tolerance_px:
            return CaptchaVerificationResult(ok=False, reason="mismatch", score=None)

        item["used"] = True
        self._store.pop(challenge_id, None)
        return CaptchaVerificationResult(ok=True, reason=None, score=None)
