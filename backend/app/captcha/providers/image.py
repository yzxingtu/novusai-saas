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
from app.core.logging import get_captcha_logger

# 延迟初始化 logger，避免在模块导入时 LogManager 还未初始化
_logger = None

def _get_logger():
    global _logger
    if _logger is None:
        _logger = get_captcha_logger()
    return _logger


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
        text_hash = self._hash(text)
        self._store[challenge_id] = {
            "hash": text_hash,
            "expires_at": expires_at,
            "used": False,
        }
        _get_logger().debug(
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

    async def verify(self, challenge_id: str, solution: str, ctx: dict[str, Any]) -> CaptchaVerificationResult:
        logger = _get_logger()
        logger.debug(
            f"[VERIFY] challenge_id={challenge_id} solution={solution} "
            f"solution_lower={solution.strip().lower()} store_keys={list(self._store.keys())}"
        )
        item = self._store.get(challenge_id)
        if not item:
            logger.warning(f"[VERIFY] NOT_FOUND challenge_id={challenge_id} (not in store)")
            return CaptchaVerificationResult(ok=False, reason="not_found", score=None)
        if item.get("used"):
            logger.warning(f"[VERIFY] USED challenge_id={challenge_id}")
            return CaptchaVerificationResult(ok=False, reason="used", score=None)
        now = datetime.now(timezone.utc)
        if now > item["expires_at"]:
            logger.warning(
                f"[VERIFY] EXPIRED challenge_id={challenge_id} "
                f"expires_at={item['expires_at']} now={now}"
            )
            del self._store[challenge_id]
            return CaptchaVerificationResult(ok=False, reason="expired", score=None)
        solution_hash = self._hash(solution)
        stored_hash = item["hash"]
        ok = solution_hash == stored_hash
        logger.debug(
            f"[VERIFY] COMPARE challenge_id={challenge_id} "
            f"solution_hash={solution_hash[:16]}... stored_hash={stored_hash[:16]}... match={ok}"
        )
        if ok:
            item["used"] = True
            del self._store[challenge_id]
            logger.info(f"[VERIFY] SUCCESS challenge_id={challenge_id}")
            return CaptchaVerificationResult(ok=True, reason=None, score=None)
        logger.warning(f"[VERIFY] MISMATCH challenge_id={challenge_id} solution={solution}")
        return CaptchaVerificationResult(ok=False, reason="mismatch", score=None)
