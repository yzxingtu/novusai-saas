from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel


class CaptchaChallenge(BaseModel):
    challenge_id: str
    type: str
    payload: dict[str, Any]
    expires_at: datetime | None = None
    token: str | None = None


class CaptchaVerificationResult(BaseModel):
    ok: bool
    reason: str | None = None
    score: float | None = None


class ICaptchaProvider(Protocol):
    async def generate_challenge(self, ctx: dict[str, Any]) -> CaptchaChallenge: ...
    async def verify(self, challenge_id: str, solution: str, ctx: dict[str, Any]) -> CaptchaVerificationResult: ...


class StubImageCaptchaProvider:
    async def generate_challenge(self, ctx: dict[str, Any]) -> CaptchaChallenge:
        _ = ctx
        return CaptchaChallenge(
            challenge_id="stub",
            type="image",
            payload={},
            expires_at=None,
            token=None,
        )

    async def verify(self, challenge_id: str, solution: str, ctx: dict[str, Any]) -> CaptchaVerificationResult:
        _ = (challenge_id, solution, ctx)
        return CaptchaVerificationResult(ok=False, reason="not_implemented", score=None)
