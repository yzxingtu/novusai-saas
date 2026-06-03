from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.base_schema import BaseSchema


class CaptchaChallengeRequest(BaseSchema):
    action: str = Field(..., min_length=1)
    endpoint: str = Field(..., min_length=1)
    provider_code: str | None = None
    difficulty: str | None = None


class CaptchaChallengeResponse(BaseSchema):
    challenge_id: str
    type: str
    payload: dict[str, Any]
    expires_at: datetime | None = None
    token: str | None = None


class CaptchaVerifyRequest(BaseSchema):
    challenge_id: str = Field(..., min_length=1)
    solution: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    endpoint: str = Field(..., min_length=1)
    provider_code: str | None = None


class CaptchaVerifyResponse(BaseSchema):
    ok: bool
    reason: str | None = None
    score: float | None = None


__all__ = [
    "CaptchaChallengeRequest",
    "CaptchaChallengeResponse",
    "CaptchaVerifyRequest",
    "CaptchaVerifyResponse",
]
