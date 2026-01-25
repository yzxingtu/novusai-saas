from __future__ import annotations
import uuid
from typing import Any
from datetime import datetime, timedelta, timezone
from app.core.logging import CaptchaLoggerMixin
from app.captcha.registry import registry
from app.captcha.provider import CaptchaChallenge, CaptchaVerificationResult, ICaptchaProvider


class CaptchaService(CaptchaLoggerMixin):
    """验证码服务"""
    
    def __init__(self) -> None:
        self._used: dict[str, datetime] = {}
        self._fail_counts: dict[str, tuple[int, datetime]] = {}
        self._rate_limits: dict[str, tuple[int, datetime]] = {}
        self._used_ttl_seconds = 600
        self._fail_window_seconds = 900
        self._limit_map: dict[str, tuple[int, int]] = {
            "challenge": (30, 60),
            "verify": (60, 60),
        }

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _key(self, ctx: dict[str, Any]) -> str:
        ip = ctx.get("ip") or ""
        endpoint = ctx.get("endpoint") or ""
        action = ctx.get("action") or ""
        return f"{ip}|{endpoint}|{action}"

    async def generate_challenge(self, provider_code: str | None, ctx: dict[str, Any]) -> CaptchaChallenge:
        provider: ICaptchaProvider | None = registry.get(provider_code or "image")
        if provider is None:
            raise ValueError("provider_not_found")
        challenge = await provider.generate_challenge(ctx)
        if challenge.challenge_id == "stub":
            challenge.challenge_id = uuid.uuid4().hex
            challenge.expires_at = self._now() + timedelta(minutes=2)
        self.logger.info(
            f"challenge created provider={provider_code or 'image'} "
            f"endpoint={ctx.get('endpoint')} action={ctx.get('action')} ip={ctx.get('ip')}"
        )
        return challenge

    async def verify(self, provider_code: str | None, challenge_id: str, solution: str, ctx: dict[str, Any]) -> CaptchaVerificationResult:
        now = self._now()
        used_expires_at = self._used.get(challenge_id)
        if used_expires_at and used_expires_at > now:
            return CaptchaVerificationResult(ok=False, reason="used", score=None)
        if used_expires_at and used_expires_at <= now:
            self._used.pop(challenge_id, None)
        provider: ICaptchaProvider | None = registry.get(provider_code or "image")
        if provider is None:
            return CaptchaVerificationResult(ok=False, reason="provider_not_found", score=None)
        result = await provider.verify(challenge_id, solution, ctx)
        key = self._key(ctx)
        if result.ok:
            self._used[challenge_id] = now + timedelta(seconds=self._used_ttl_seconds)
            self._fail_counts[key] = (0, now + timedelta(seconds=self._fail_window_seconds))
        else:
            count, reset_at = self._fail_counts.get(
                key, (0, now + timedelta(seconds=self._fail_window_seconds))
            )
            if reset_at <= now:
                count = 0
                reset_at = now + timedelta(seconds=self._fail_window_seconds)
            self._fail_counts[key] = (count + 1, reset_at)
        self.logger.info(
            f"verify result={result.ok} reason={result.reason} provider={provider_code or 'image'} "
            f"endpoint={ctx.get('endpoint')} action={ctx.get('action')} ip={ctx.get('ip')}"
        )
        return result

    def get_fail_count(self, ctx: dict[str, Any]) -> int:
        now = self._now()
        count, reset_at = self._fail_counts.get(
            self._key(ctx), (0, now + timedelta(seconds=self._fail_window_seconds))
        )
        if reset_at <= now:
            self._fail_counts.pop(self._key(ctx), None)
            return 0
        return count

    def check_rate_limit(self, ctx: dict[str, Any], kind: str) -> bool:
        limit, window_seconds = self._limit_map.get(kind, (60, 60))
        now = self._now()
        key = f"{kind}|{self._key(ctx)}"
        count, reset_at = self._rate_limits.get(key, (0, now + timedelta(seconds=window_seconds)))
        if reset_at <= now:
            count = 0
            reset_at = now + timedelta(seconds=window_seconds)
        count += 1
        self._rate_limits[key] = (count, reset_at)
        return count <= limit


captcha_service = CaptchaService()


__all__ = ["CaptchaService", "captcha_service"]
