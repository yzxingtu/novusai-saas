"""Slider captcha provider. / 滑动拼图验证码提供者。"""

from __future__ import annotations

import base64
import io
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, ImageDraw, ImageOps
from sqlalchemy import select

from app.captcha.provider import (
    CaptchaChallenge,
    CaptchaVerificationResult,
    ICaptchaProvider,
)
from app.core.base_model import utc_now
from app.core.config import settings
from app.core.database import get_db_context
from app.core.redis import cache_delete, cache_get, cache_set
from app.models.tenant.attachment import Attachment
from app.services.common.storage_config_resolver import StorageConfigResolver
from app.storage import storage_manager

_BUNDLED_BACKGROUND_COUNT = 4
_CHALLENGE_TTL_SECONDS = 120
_CHALLENGE_KEY_PREFIX = "plugin:slider-captcha:challenge"
_MAX_VERIFY_ATTEMPTS = 5
_CANVAS_HEIGHT = 180
_CANVAS_WIDTH = 320
_CAPTURE_LEFT_PADDING = 3
_HTTP_TIMEOUT_SECONDS = 5
_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
_BACKGROUND_DIR = _PLUGIN_ROOT / "frontend" / "src" / "assets" / "backgrounds"


class SliderCaptchaProvider(ICaptchaProvider):
    """Redis-backed slider captcha provider. / 基于 Redis 的滑动拼图验证码提供者。"""

    def _now(self) -> datetime:
        return utc_now()

    @staticmethod
    def _challenge_key(challenge_id: str) -> str:
        return f"{_CHALLENGE_KEY_PREFIX}:{challenge_id}"

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
    def _resolve_difficulty_settings(difficulty: Any) -> tuple[int, int]:
        difficulty_value = str(difficulty or "medium").strip().lower()
        presets = {
            "easy": (40, 9),
            "hard": (44, 4),
            "medium": (42, 6),
        }
        return presets.get(difficulty_value, presets["medium"])

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

    @staticmethod
    def _piece_capture_length(square_length: int, circle_radius: int) -> int:
        return square_length + 2 * circle_radius + _CAPTURE_LEFT_PADDING

    @staticmethod
    def _piece_capture_left(piece_x: int) -> int:
        return max(0, piece_x - _CAPTURE_LEFT_PADDING)

    @staticmethod
    def _piece_capture_top(piece_y: int, circle_radius: int) -> int:
        return max(0, piece_y - 2 * circle_radius - 1)

    @staticmethod
    def _piece_local_origin(
        piece_x: int,
        piece_y: int,
        capture_left: int,
        capture_top: int,
    ) -> tuple[int, int]:
        return piece_x - capture_left, piece_y - capture_top

    @staticmethod
    def _build_piece_mask(
        width: int,
        height: int,
        origin_x: int,
        origin_y: int,
        square_length: int,
        circle_radius: int,
    ) -> Image.Image:
        scale = 6
        mask_hi = Image.new("L", (width * scale, height * scale), 0)
        draw = ImageDraw.Draw(mask_hi)

        ox = origin_x * scale
        oy = origin_y * scale
        sl = square_length * scale
        cr = circle_radius * scale
        ov = 2 * scale

        right = ox + sl
        bottom = oy + sl

        draw.rectangle((ox, oy, right, bottom), fill=255)
        draw.ellipse(
            (
                ox + sl // 2 - cr,
                oy - 2 * cr + ov,
                ox + sl // 2 + cr,
                oy + ov,
            ),
            fill=255,
        )
        draw.ellipse(
            (
                right - ov,
                oy + sl // 2 - cr,
                right + 2 * cr - ov,
                oy + sl // 2 + cr,
            ),
            fill=255,
        )
        draw.ellipse(
            (
                ox - 2 * cr + ov,
                oy + sl // 2 - cr,
                ox + ov,
                oy + sl // 2 + cr,
            ),
            fill=0,
        )
        return mask_hi.resize((width, height), Image.Resampling.LANCZOS)

    @staticmethod
    def _image_to_data_url(image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def _build_background_path(index: int) -> Path:
        return _BACKGROUND_DIR / f"slider-bg-{index + 1:02d}.jpg"

    def _resolve_background_url(self, value: Any) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None

        if raw.isdigit():
            attachment_id = int(raw)
            if attachment_id > 0:
                raw = f"/api/public/attachments/{attachment_id}/image"
            else:
                return None

        parsed = urlparse(raw)
        if parsed.scheme in {"http", "https"}:
            base = urlparse(settings.APP_INTERNAL_BASE_URL)
            if parsed.netloc != base.netloc:
                return None
            return raw

        if raw.startswith("/"):
            return urljoin(
                f"{settings.APP_INTERNAL_BASE_URL.rstrip('/')}/", raw.lstrip("/")
            )
        return None

    async def _load_attachment_bytes(self, attachment_id: int) -> bytes | None:
        if attachment_id <= 0:
            return None

        async with get_db_context() as db:
            result = await db.execute(
                select(Attachment).where(
                    Attachment.id == attachment_id,
                    Attachment.is_deleted.is_(False),
                )
            )
            attachment = result.scalar_one_or_none()
            if not attachment:
                return None

            resolver = StorageConfigResolver(db)
            storage_config = await resolver.resolve_for_attachment_record(attachment)
            driver = storage_manager.get_driver(storage_config)
            stream = await driver.get(attachment.path)
            try:
                return stream.read()
            finally:
                close = getattr(stream, "close", None)
                if callable(close):
                    close()

    async def _fetch_remote_image(self, url: str) -> bytes:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=_HTTP_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def _load_background_image(
        self, plugin_config: dict[str, Any]
    ) -> Image.Image:
        background_index = random.randint(0, _BUNDLED_BACKGROUND_COUNT - 1)
        configured_value = plugin_config.get(f"background_{background_index + 1}")
        image_bytes: bytes | None = None

        raw_value = str(configured_value or "").strip()
        if raw_value.isdigit():
            try:
                image_bytes = await self._load_attachment_bytes(int(raw_value))
            except Exception:
                image_bytes = None

        resolved_url = self._resolve_background_url(configured_value)
        if image_bytes is None and resolved_url:
            try:
                image_bytes = await self._fetch_remote_image(resolved_url)
            except Exception:
                image_bytes = None

        if image_bytes is None:
            local_path = self._build_background_path(background_index)
            image_bytes = local_path.read_bytes()

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return ImageOps.fit(
            image,
            (_CANVAS_WIDTH, _CANVAS_HEIGHT),
            method=Image.Resampling.LANCZOS,
        )

    async def _store_challenge(
        self,
        challenge_id: str,
        data: dict[str, Any],
    ) -> None:
        await cache_set(
            self._challenge_key(challenge_id),
            data,
            ttl=_CHALLENGE_TTL_SECONDS,
        )

    async def _load_stored_challenge(self, challenge_id: str) -> dict[str, Any] | None:
        data = await cache_get(self._challenge_key(challenge_id))
        return data if isinstance(data, dict) else None

    async def _delete_stored_challenge(self, challenge_id: str) -> None:
        await cache_delete(self._challenge_key(challenge_id))

    @staticmethod
    def _build_context_binding(ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "action": str(ctx.get("action") or ""),
            "endpoint": str(ctx.get("endpoint") or ""),
            "ip": str(ctx.get("ip") or ""),
        }

    def _render_images(
        self,
        background: Image.Image,
        *,
        capture_left: int,
        capture_top: int,
        capture_length: int,
        piece_mask: Image.Image,
    ) -> tuple[str, str]:
        board_rgba = background.convert("RGBA")
        piece_rgba = Image.new("RGBA", (capture_length, capture_length), (0, 0, 0, 0))

        piece_crop = board_rgba.crop(
            (
                capture_left,
                capture_top,
                capture_left + capture_length,
                capture_top + capture_length,
            )
        )
        piece_rgba.paste(piece_crop, (0, 0), piece_mask)

        return self._image_to_data_url(board_rgba), self._image_to_data_url(piece_rgba)

    async def generate_challenge(self, ctx: dict[str, Any]) -> CaptchaChallenge:
        plugin_config = (
            ctx.get("plugin_config")
            if isinstance(ctx.get("plugin_config"), dict)
            else {}
        ) or {}

        default_square, default_tolerance = self._resolve_difficulty_settings(
            ctx.get("difficulty")
        )
        square_length = self._clamp_int(
            plugin_config.get("square_length"),
            minimum=36,
            maximum=54,
            default=default_square,
        )
        circle_radius = max(8, min(14, int(round(square_length * 0.24))))
        tolerance_px = self._clamp_int(
            plugin_config.get("tolerance_px"),
            minimum=3,
            maximum=12,
            default=default_tolerance,
        )

        capture_length = self._piece_capture_length(square_length, circle_radius)
        piece_x = random.randint(capture_length, _CANVAS_WIDTH - capture_length)
        piece_y = random.randint(
            3 * circle_radius,
            _CANVAS_HEIGHT - capture_length,
        )
        capture_left = self._piece_capture_left(piece_x)
        capture_top = self._piece_capture_top(piece_y, circle_radius)
        local_origin_x, local_origin_y = self._piece_local_origin(
            piece_x,
            piece_y,
            capture_left,
            capture_top,
        )

        piece_mask = self._build_piece_mask(
            capture_length,
            capture_length,
            local_origin_x,
            local_origin_y,
            square_length,
            circle_radius,
        )
        background = await self._load_background_image(plugin_config)
        board_image, piece_image = self._render_images(
            background,
            capture_left=capture_left,
            capture_top=capture_top,
            capture_length=capture_length,
            piece_mask=piece_mask,
        )

        challenge_id = uuid.uuid4().hex
        expires_at = self._now() + timedelta(seconds=_CHALLENGE_TTL_SECONDS)
        await self._store_challenge(
            challenge_id,
            {
                "attempts": 0,
                "binding": self._build_context_binding(ctx),
                "expected_offset": capture_left,
                "expires_at": expires_at.isoformat(),
                "max_attempts": _MAX_VERIFY_ATTEMPTS,
                "tolerance_px": tolerance_px,
            },
        )

        return CaptchaChallenge(
            challenge_id=challenge_id,
            type="slider",
            payload={
                "board_image": board_image,
                "canvas_height": _CANVAS_HEIGHT,
                "canvas_width": _CANVAS_WIDTH,
                "piece_capture_left": capture_left,
                "piece_geometry": {
                    "circle_radius": circle_radius,
                    "origin_x": local_origin_x,
                    "origin_y": local_origin_y,
                    "square_length": square_length,
                },
                "piece_height": capture_length,
                "piece_image": piece_image,
                "piece_top": capture_top,
                "piece_width": capture_length,
                "tolerance_px": tolerance_px,
            },
            expires_at=expires_at,
            token=None,
        )

    async def verify(
        self,
        challenge_id: str,
        solution: str,
        ctx: dict[str, Any],
    ) -> CaptchaVerificationResult:
        stored = await self._load_stored_challenge(challenge_id)
        if not stored:
            return CaptchaVerificationResult(ok=False, reason="not_found", score=None)

        expires_at_raw = str(stored.get("expires_at") or "").strip()
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except Exception:
            await self._delete_stored_challenge(challenge_id)
            return CaptchaVerificationResult(ok=False, reason="expired", score=None)

        if self._now() > expires_at:
            await self._delete_stored_challenge(challenge_id)
            return CaptchaVerificationResult(ok=False, reason="expired", score=None)

        binding = stored.get("binding")
        current_binding = self._build_context_binding(ctx)
        if not isinstance(binding, dict) or binding != current_binding:
            await self._delete_stored_challenge(challenge_id)
            return CaptchaVerificationResult(
                ok=False, reason="invalid_context", score=None
            )

        offset = self._parse_solution_offset(solution)
        if offset is None:
            attempts = int(stored.get("attempts") or 0) + 1
            max_attempts = int(stored.get("max_attempts") or _MAX_VERIFY_ATTEMPTS)
            if attempts >= max_attempts:
                await self._delete_stored_challenge(challenge_id)
            else:
                stored["attempts"] = attempts
                await self._store_challenge(challenge_id, stored)
            return CaptchaVerificationResult(
                ok=False, reason="invalid_solution", score=None
            )

        expected = int(stored.get("expected_offset") or 0)
        tolerance_px = int(stored.get("tolerance_px") or 6)
        if abs(offset - expected) > tolerance_px:
            attempts = int(stored.get("attempts") or 0) + 1
            max_attempts = int(stored.get("max_attempts") or _MAX_VERIFY_ATTEMPTS)
            if attempts >= max_attempts:
                await self._delete_stored_challenge(challenge_id)
            else:
                stored["attempts"] = attempts
                await self._store_challenge(challenge_id, stored)
            return CaptchaVerificationResult(ok=False, reason="mismatch", score=None)

        await self._delete_stored_challenge(challenge_id)
        return CaptchaVerificationResult(ok=True, reason=None, score=None)
