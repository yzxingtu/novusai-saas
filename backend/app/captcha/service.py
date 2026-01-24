from __future__ import annotations
import uuid
from typing import Any
from datetime import datetime, timedelta, timezone
from app.captcha.registry import registry
from app.captcha.provider import CaptchaChallenge, CaptchaVerificationResult, ICaptchaProvider


class CaptchaService:
    def __init__(self) -> None:
        self._used: set[str] = set()
        self._fail_counts: dict[str, int] = {}

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
        return challenge

    async def verify(self, provider_code: str | None, challenge_id: str, solution: str, ctx: dict[str, Any]) -> CaptchaVerificationResult:
        if challenge_id in self._used:
            return CaptchaVerificationResult(ok=False, reason="used", score=None)
        provider: ICaptchaProvider | None = registry.get(provider_code or "image")
        if provider is None:
            return CaptchaVerificationResult(ok=False, reason="provider_not_found", score=None)
        result = await provider.verify(challenge_id, solution, ctx)
        key = self._key(ctx)
        if result.ok:
            self._used.add(challenge_id)
            self._fail_counts[key] = 0
        else:
            self._fail_counts[key] = self._fail_counts.get(key, 0) + 1
        return result

    def get_fail_count(self, ctx: dict[str, Any]) -> int:
        return self._fail_counts.get(self._key(ctx), 0)


captcha_service = CaptchaService()


__all__ = ["CaptchaService", "captcha_service"]
