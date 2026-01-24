from __future__ import annotations
import base64
import uuid
import string
import random
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
try:
    from captcha.image import ImageCaptcha
except Exception:
    ImageCaptcha = None  # type: ignore
from app.captcha.provider import ICaptchaProvider, CaptchaChallenge, CaptchaVerificationResult


class ImageCaptchaProvider(ICaptchaProvider):
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._charsets = {
            "easy": "ABCDEFGHJKLMNPQRSTUVWXYZ23456789",
            "medium": "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789",
            "hard": string.ascii_letters + string.digits,
        }
        self._lengths = {"easy": 4, "medium": 5, "hard": 6}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _gen_text(self, difficulty: str) -> str:
        charset = self._charsets.get(difficulty, self._charsets["medium"])
        length = self._lengths.get(difficulty, self._lengths["medium"])
        return "".join(random.choice(charset) for _ in range(length))

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()

    async def generate_challenge(self, ctx: dict[str, Any]) -> CaptchaChallenge:
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
        self._store[challenge_id] = {
            "hash": self._hash(text),
            "expires_at": expires_at,
            "used": False,
        }
        return CaptchaChallenge(
            challenge_id=challenge_id,
            type="image",
            payload={"image_base64": b64},
            expires_at=expires_at,
            token=None,
        )

    async def verify(self, challenge_id: str, solution: str, ctx: dict[str, Any]) -> CaptchaVerificationResult:
        item = self._store.get(challenge_id)
        if not item:
            return CaptchaVerificationResult(ok=False, reason="not_found", score=None)
        if item.get("used"):
            return CaptchaVerificationResult(ok=False, reason="used", score=None)
        if datetime.now(timezone.utc) > item["expires_at"]:
            del self._store[challenge_id]
            return CaptchaVerificationResult(ok=False, reason="expired", score=None)
        ok = self._hash(solution) == item["hash"]
        if ok:
            item["used"] = True
            del self._store[challenge_id]
            return CaptchaVerificationResult(ok=True, reason=None, score=None)
        return CaptchaVerificationResult(ok=False, reason="mismatch", score=None)
