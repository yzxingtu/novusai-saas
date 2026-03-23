"""Captcha Provider Interface
验证码提供者接口

Defines the captcha provider protocol and data models:
定义验证码提供者协议和数据模型：
- CaptchaChallenge: Challenge data returned to client / 返回给客户端的挑战数据
- CaptchaVerificationResult: Verification result / 验证结果
- ICaptchaProvider: Provider protocol (generate + verify) / 提供者协议（生成 + 验证）
- StubImageCaptchaProvider: Stub implementation for fallback / 存根实现用于降级
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel


class CaptchaChallenge(BaseModel):
    """Captcha challenge data returned to client / 返回给客户端的验证码挑战数据"""
    challenge_id: str
    type: str
    payload: dict[str, Any]
    expires_at: datetime | None = None
    token: str | None = None


class CaptchaVerificationResult(BaseModel):
    """Captcha verification result / 验证码验证结果"""
    ok: bool
    reason: str | None = None
    score: float | None = None


@dataclass(slots=True)
class CaptchaProviderMetadata:
    """Captcha provider runtime metadata / 验证码提供者运行时元数据"""

    plugin_name: str | None = None
    public_endpoints: list[str] = field(default_factory=list)
    frontend_runtime: dict[str, str] = field(default_factory=dict)
    display_name: dict[str, str] = field(default_factory=dict)


class ICaptchaProvider(Protocol):
    """Captcha provider protocol / 验证码提供者协议"""

    async def generate_challenge(self, ctx: dict[str, Any]) -> CaptchaChallenge:
        """Generate a captcha challenge / 生成验证码挑战"""
        ...

    async def verify(self, challenge_id: str, solution: str, ctx: dict[str, Any]) -> CaptchaVerificationResult:
        """Verify user's solution / 验证用户的答案"""
        ...


class StubImageCaptchaProvider:
    """Stub captcha provider (always fails, used as fallback) / 存根验证码提供者（始终失败，用于降级）"""

    async def generate_challenge(self, ctx: dict[str, Any]) -> CaptchaChallenge:
        """Generate a stub challenge / 生成存根挑战"""
        _ = ctx
        return CaptchaChallenge(
            challenge_id="stub",
            type="image",
            payload={},
            expires_at=None,
            token=None,
        )

    async def verify(self, challenge_id: str, solution: str, ctx: dict[str, Any]) -> CaptchaVerificationResult:
        """Stub verify (always returns failure) / 存根验证（始终返回失败）"""
        _ = (challenge_id, solution, ctx)
        return CaptchaVerificationResult(ok=False, reason="not_implemented", score=None)
