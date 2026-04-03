"""
Image Captcha Provider
图形验证码提供者

Generates image-based captcha challenges with configurable difficulty levels.
生成基于图片的验证码挑战，支持可配置的难度级别。

Difficulty levels / 难度级别:
- easy: 4 chars, uppercase + digits / 4位，大写字母+数字
- medium: 5 chars, mixed case + digits / 5位，大小写字母+数字
- hard: 6 chars, full alphanumeric / 6位，全字母数字
"""

from __future__ import annotations

import base64
import hashlib
import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Any

try:
    from captcha.image import ImageCaptcha
except Exception:
    ImageCaptcha = None  # type: ignore / 可选依赖缺失时忽略类型
from app.captcha.provider import (
    CaptchaChallenge,
    CaptchaVerificationResult,
    ICaptchaProvider,
)
from app.core.base_model import utc_now
from app.core.logging import CaptchaLoggerMixin


class ImageCaptchaProvider(ICaptchaProvider, CaptchaLoggerMixin):
    """
    Image Captcha Provider / 图形验证码提供者。

    Uses in-memory store for challenge data (hash + expiry + used flag).
    使用内存存储挑战数据（哈希 + 过期时间 + 已使用标记）。
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._charsets = {
            "easy": "ABCDEFGHJKLMNPQRSTUVWXYZ23456789",
            "medium": "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789",
            "hard": string.ascii_letters + string.digits,
        }
        self._lengths = {"easy": 4, "medium": 5, "hard": 6}

    def _now(self) -> datetime:
        """Get current UTC time / 获取当前 UTC 时间"""
        return utc_now()

    def _gen_text(self, difficulty: str) -> str:
        """Generate random captcha text by difficulty / 根据难度生成随机验证码文本"""
        charset = self._charsets.get(difficulty, self._charsets["medium"])
        length = self._lengths.get(difficulty, self._lengths["medium"])
        return "".join(random.choice(charset) for _ in range(length))

    def _hash(self, text: str) -> str:
        """Hash text for comparison (case-insensitive) / 哈希文本用于比对（不区分大小写）"""
        return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()

    async def generate_challenge(self, ctx: dict[str, Any]) -> CaptchaChallenge:
        """Generate an image captcha challenge / 生成图形验证码挑战"""
        if ImageCaptcha is None:
            raise RuntimeError("captcha_library_missing")
        difficulty = str(ctx.get("difficulty") or "medium")
        ttl_seconds = int(ctx.get("ttl_seconds") or 120)
        text = self._gen_text(difficulty)
        generator = ImageCaptcha(width=160, height=60)
        img_bytes = generator.generate(text).read()
        b64 = base64.b64encode(img_bytes).decode("ascii")
        challenge_id = uuid.uuid4().hex
        expires_at = self._now() + timedelta(seconds=ttl_seconds)
        text_hash = self._hash(text)
        self._store[challenge_id] = {
            "hash": text_hash,
            "expires_at": expires_at,
            "used": False,
        }
        self.logger.debug(
            f"[GENERATE] challenge_id={challenge_id} text={text} "
            f"text_lower={text.strip().lower()} hash={text_hash[:16]}... "
            f"difficulty={difficulty} expires_at={expires_at} store_size={len(self._store)}"
        )
        return CaptchaChallenge(
            challenge_id=challenge_id,
            type="image",
            payload={"image_base64": b64},
            expires_at=expires_at,
            token=None,
        )

    async def verify(
        self, challenge_id: str, solution: str, ctx: dict[str, Any]
    ) -> CaptchaVerificationResult:
        """Verify captcha solution against stored hash / 验证验证码答案与存储的哈希比对"""
        _ = ctx
        self.logger.debug(
            f"[VERIFY] challenge_id={challenge_id} solution={solution} "
            f"solution_lower={solution.strip().lower()} store_keys={list(self._store.keys())}"
        )
        item = self._store.get(challenge_id)
        if not item:
            self.logger.warning(
                f"[VERIFY] NOT_FOUND challenge_id={challenge_id} (not in store)"
            )
            return CaptchaVerificationResult(ok=False, reason="not_found", score=None)
        if item.get("used"):
            self.logger.warning(f"[VERIFY] USED challenge_id={challenge_id}")
            return CaptchaVerificationResult(ok=False, reason="used", score=None)
        now = utc_now()
        if now > item["expires_at"]:
            self.logger.warning(
                f"[VERIFY] EXPIRED challenge_id={challenge_id} "
                f"expires_at={item['expires_at']} now={now}"
            )
            del self._store[challenge_id]
            return CaptchaVerificationResult(ok=False, reason="expired", score=None)
        solution_hash = self._hash(solution)
        stored_hash = item["hash"]
        ok = solution_hash == stored_hash
        self.logger.debug(
            f"[VERIFY] COMPARE challenge_id={challenge_id} "
            f"solution_hash={solution_hash[:16]}... stored_hash={stored_hash[:16]}... match={ok}"
        )
        if ok:
            item["used"] = True
            del self._store[challenge_id]
            self.logger.info(f"[VERIFY] SUCCESS challenge_id={challenge_id}")
            return CaptchaVerificationResult(ok=True, reason=None, score=None)
        self.logger.warning(
            f"[VERIFY] MISMATCH challenge_id={challenge_id} solution={solution}"
        )
        return CaptchaVerificationResult(ok=False, reason="mismatch", score=None)
