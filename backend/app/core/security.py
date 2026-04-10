"""
安全模块 / Security Module

提供 JWT Token 生成/验证、密码哈希、Token 黑名单吊销等安全相关功能
Provides JWT token generation/verification, password hashing, token blacklist revoke.
"""

import uuid
from datetime import timedelta
from typing import Any

import bcrypt
from cryptography.fernet import Fernet
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.base_model import utc_now
from app.core.config import settings
from app.core.logging import LogManager

logger = LogManager.get_logger("app.core.security")

# Token 类型常量 / Token type constants
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_IMPERSONATE = (
    "impersonate"  # 一键登录临时 Token / One-click login temporary token
)

# Token 作用域常量（用户类型） / Token scope constants (user types)
TOKEN_SCOPE_ADMIN = "admin"  # 平台管理员 / Platform admin
TOKEN_SCOPE_TENANT_ADMIN = "tenant_admin"  # 企业管理员 / Tenant admin
TOKEN_SCOPE_TENANT_USER = "tenant_user"  # 企业业务用户 / Tenant business user

# Impersonate Token 过期时间（秒） / Impersonate token expiry (seconds)
IMPERSONATE_TOKEN_EXPIRE_SECONDS = 60


def create_access_token(
    subject: str | int,
    scope: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """
    创建 Access Token / Create access token

    Args:
        subject: Token 主体（通常是用户 ID） / Token subject (usually user ID)
        scope: Token 作用域（用户类型），必须为 TOKEN_SCOPE_* 常量之一 / Token scope (user type)
        expires_delta: 过期时间增量 / Expiration time delta
        extra_claims: 额外的 claims / Additional claims

    Returns:
        (token, jti) 元组 / Tuple of (token, jti)
    """
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = str(uuid.uuid4())

    to_encode = {
        "sub": str(subject),
        "scope": scope,
        "exp": expire,
        "iat": utc_now(),
        "type": TOKEN_TYPE_ACCESS,
        "jti": jti,
    }

    if extra_claims:
        to_encode.update(extra_claims)

    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, jti


def create_refresh_token(
    subject: str | int,
    scope: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """
    创建 Refresh Token / Create refresh token

    Args:
        subject: Token 主体（通常是用户 ID） / Token subject (usually user ID)
        scope: Token 作用域（用户类型），必须为 TOKEN_SCOPE_* 常量之一 / Token scope (user type)
        expires_delta: 过期时间增量 / Expiration time delta
        extra_claims: 额外的 claims / Additional claims

    Returns:
        (token, jti) 元组 / Tuple of (token, jti)
    """
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())

    to_encode = {
        "sub": str(subject),
        "scope": scope,
        "exp": expire,
        "iat": utc_now(),
        "type": TOKEN_TYPE_REFRESH,
        "jti": jti,
    }

    if extra_claims:
        to_encode.update(extra_claims)

    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, jti


class TokenExpiredError(Exception):
    """Token 已过期（区别于无效 Token） / Token expired (distinct from invalid token)"""


# Redis key prefix for token blacklist / Token 黑名单 Redis key 前缀
TOKEN_BLACKLIST_PREFIX = "token_blacklist:"
ACTIVE_TOKENS_PREFIX = "active_tokens:"


async def revoke_token(jti: str, ttl_seconds: int) -> None:
    """
    将 Token 加入黑名单（吊销）/ Revoke token by adding to blacklist.

    Args:
        jti: JWT ID
        ttl_seconds: 剩余有效时间（秒），用作 Redis TTL / Remaining TTL in seconds for Redis key
    """
    try:
        from app.core.redis import get_redis_client

        client = get_redis_client()
        key = f"{TOKEN_BLACKLIST_PREFIX}{jti}"
        await client.setex(key, ttl_seconds, "1")
    except Exception as exc:
        logger.debug(
            "Token blacklist add failed: {}", exc
        )  # Redis 不可用时静默失败，Token 将在自然过期后失效


def _decode_token_no_blacklist(token: str) -> dict[str, Any] | None:
    """
    解码 Token（不检查黑名单，用于登出时获取 jti/exp） / Decode token without blacklist check (for logout flow).
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except (ExpiredSignatureError, JWTError):
        return None


async def is_token_revoked(jti: str | None) -> bool:
    """
    检查 Token 是否已被吊销 / Check if token is revoked.

    Args:
        jti: JWT ID，None 或空则视为未吊销（兼容旧 Token）/ None or empty => not revoked (legacy tokens)

    Returns:
        True 表示已吊销 / True if revoked
    """
    if not jti:
        return False
    try:
        from app.core.redis import get_redis_client

        client = get_redis_client()
        key = f"{TOKEN_BLACKLIST_PREFIX}{jti}"
        return bool(await client.exists(key))
    except Exception:
        return False  # Redis 不可用时视为未吊销，避免误杀


async def decode_token(
    token: str, raise_on_expired: bool = False
) -> dict[str, Any] | None:
    """
    解码并验证 Token / Decode and verify token

    Args:
        token: JWT Token 字符串 / JWT token string
        raise_on_expired: 为 True 时，过期 Token 抛出 TokenExpiredError
            而非静默返回 None，允许调用方区分过期和无效。
            When True, raises TokenExpiredError for expired tokens
            instead of silently returning None.

    Returns:
        解码后的 payload，验证失败返回 None / Decoded payload, None on failure

    Raises:
        TokenExpiredError: raise_on_expired=True 且 Token 已过期 / when True and token is expired
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # 旧 Token 无 jti，跳过黑名单检查 / Legacy tokens without jti skip blacklist check
        jti = payload.get("jti")
        if jti and await is_token_revoked(jti):
            return None
        return payload
    except ExpiredSignatureError as exc:
        if raise_on_expired:
            raise TokenExpiredError() from exc
        return None
    except JWTError:
        return None


async def verify_token(token: str, token_type: str = TOKEN_TYPE_ACCESS) -> str | None:
    """
    验证 Token 并返回 subject / Verify token and return subject

    Args:
        token: JWT Token 字符串 / JWT token string
        token_type: 期望的 Token 类型 / Expected token type

    Returns:
        Token 的 subject（用户 ID），验证失败返回 None / Token subject (user ID), None on failure
    """
    payload = await decode_token(token)
    if payload is None:
        return None

    # 检查 Token 类型 / Check token type
    if payload.get("type") != token_type:
        return None

    return payload.get("sub")


async def verify_token_with_scope(
    token: str,
    expected_scope: str,
    token_type: str = TOKEN_TYPE_ACCESS,
    raise_on_expired: bool = False,
) -> tuple[str | None, str | None]:
    """
    验证 Token 并检查 scope / Verify token and check scope

    Args:
        token: JWT Token 字符串 / JWT token string
        expected_scope: 期望的 scope（用户类型） / Expected scope (user type)
        token_type: 期望的 Token 类型 / Expected token type
        raise_on_expired: 为 True 时，过期 Token 抛出 TokenExpiredError / Raise on expired token

    Returns:
        (subject, scope) 元组，验证失败返回 (None, None) / Tuple, (None, None) on failure

    Raises:
        TokenExpiredError: raise_on_expired=True 且 Token 已过期 / when True and token is expired
    """
    payload = await decode_token(token, raise_on_expired=raise_on_expired)
    if payload is None:
        return None, None

    # 检查 Token 类型 / Check token type
    if payload.get("type") != token_type:
        return None, None

    # 检查 scope / Check scope
    scope = payload.get("scope")
    if scope != expected_scope:
        return None, None

    return payload.get("sub"), scope


async def get_token_payload(
    token: str,
    token_type: str = TOKEN_TYPE_ACCESS,
) -> dict[str, Any] | None:
    """
    获取 Token 的完整 payload / Get full token payload

    Args:
        token: JWT Token 字符串 / JWT token string
        token_type: 期望的 Token 类型 / Expected token type

    Returns:
        Token 的 payload，验证失败返回 None / Token payload, None on failure
    """
    payload = await decode_token(token)
    if payload is None:
        return None

    # 检查 Token 类型 / Check token type
    if payload.get("type") != token_type:
        return None

    return payload


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码 / Verify password

    Args:
        plain_password: 明文密码 / Plain text password
        hashed_password: 哈希后的密码 / Hashed password

    Returns:
        密码是否正确 / Whether the password is correct
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """
    获取密码哈希 / Get password hash

    Args:
        password: 明文密码 / Plain text password

    Returns:
        哈希后的密码 / Hashed password
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_token_pair(
    subject: str | int,
    scope: str,
    extra_claims: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    创建 Token 对（access_token + refresh_token） / Create token pair

    Args:
        subject: Token 主体 / Token subject
        scope: Token 作用域（用户类型） / Token scope (user type)
        extra_claims: 额外的 claims（仅添加到 access_token） / Extra claims (access_token only)

    Returns:
        包含 access_token、refresh_token、access_jti、refresh_jti 的字典
        Dict with access_token, refresh_token, access_jti, refresh_jti
    """
    access_token, access_jti = create_access_token(
        subject, scope=scope, extra_claims=extra_claims
    )
    refresh_token, refresh_jti = create_refresh_token(subject, scope=scope)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_jti": access_jti,
        "refresh_jti": refresh_jti,
        "token_type": "bearer",
    }


def create_impersonate_token(
    admin_id: int,
    target_scope: str,
    target_tenant_id: int,
    target_role_id: int | None = None,
    expires_seconds: int = IMPERSONATE_TOKEN_EXPIRE_SECONDS,
) -> str:
    """
    创建一键登录临时 Token / Create one-click login temporary token

    用于平台管理员一键登录企业后台或企业管理员一键登录用户端
    Used for admin one-click login to tenant backend or tenant admin one-click login to user side.

    Args:
        admin_id: 发起者 ID（平台管理员或企业管理员） / Initiator ID (admin or tenant admin)
        target_scope: 目标 scope（tenant_admin 或 tenant_user） / Target scope
        target_tenant_id: 目标企业 ID / Target tenant ID
        target_role_id: 目标角色 ID（可选） / Target role ID (optional)
        expires_seconds: 过期时间（秒），默认 60 秒 / Expiry in seconds, default 60

    Returns:
        编码后的 JWT Token / Encoded JWT token
    """
    expire = utc_now() + timedelta(seconds=expires_seconds)

    to_encode = {
        "sub": str(admin_id),  # 发起者 ID / Initiator ID
        "type": TOKEN_TYPE_IMPERSONATE,
        "target_scope": target_scope,
        "target_tenant_id": target_tenant_id,
        "exp": expire,
        "iat": utc_now(),
    }

    if target_role_id is not None:
        to_encode["target_role_id"] = target_role_id

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def verify_impersonate_token(
    token: str,
    expected_target_scope: str,
) -> dict[str, Any] | None:
    """
    验证一键登录 Token / Verify one-click login token

    Args:
        token: JWT Token 字符串 / JWT token string
        expected_target_scope: 期望的目标 scope / Expected target scope

    Returns:
        Token 的 payload，验证失败返回 None / Token payload, None on failure
        payload 包含 / contains: sub, target_scope, target_tenant_id, target_role_id(可选/optional)
    """
    payload = await decode_token(token)
    if payload is None:
        return None

    # 检查 Token 类型 / Check token type
    if payload.get("type") != TOKEN_TYPE_IMPERSONATE:
        return None

    # 检查目标 scope / Check target scope
    if payload.get("target_scope") != expected_target_scope:
        return None

    return payload


def _get_encryption_key() -> bytes:
    """
    获取加密密钥 / Get encryption key

    使用 SECRET_KEY 派生 Fernet 密钥 / Derives Fernet key from SECRET_KEY
    Fernet 需要 32 字节的 base64 编码密钥 / Fernet requires 32-byte base64-encoded key
    """
    # 确保密钥长度符合 Fernet 要求 / Ensure key length meets Fernet requirements
    key = settings.SECRET_KEY.encode()
    # 使用 SHA256 生成固定长度的密钥 / Use SHA256 to generate fixed-length key
    import base64
    import hashlib

    hash_key = hashlib.sha256(key).digest()
    return base64.urlsafe_b64encode(hash_key)


def encrypt_data(plaintext: str) -> str:
    """
    加密数据 / Encrypt data

    Args:
        plaintext: 明文 / Plain text

    Returns:
        加密后的密文（Base64 编码） / Encrypted ciphertext (Base64 encoded)
    """
    f = Fernet(_get_encryption_key())
    encrypted = f.encrypt(plaintext.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_data(ciphertext: str) -> str:
    """
    解密数据 / Decrypt data

    Args:
        ciphertext: 密文（Base64 编码） / Ciphertext (Base64 encoded)

    Returns:
        解密后的明文 / Decrypted plain text
    """
    f = Fernet(_get_encryption_key())
    decrypted = f.decrypt(ciphertext.encode("utf-8"))
    return decrypted.decode("utf-8")


__all__ = [
    "create_access_token",
    "create_refresh_token",
    "revoke_token",
    "is_token_revoked",
    "decode_token",
    "verify_token",
    "verify_token_with_scope",
    "get_token_payload",
    "verify_password",
    "get_password_hash",
    "create_token_pair",
    "create_impersonate_token",
    "verify_impersonate_token",
    "encrypt_data",
    "decrypt_data",
    "TokenExpiredError",
    "TOKEN_TYPE_ACCESS",
    "TOKEN_TYPE_REFRESH",
    "TOKEN_TYPE_IMPERSONATE",
    "TOKEN_SCOPE_ADMIN",
    "TOKEN_SCOPE_TENANT_ADMIN",
    "TOKEN_SCOPE_TENANT_USER",
    "IMPERSONATE_TOKEN_EXPIRE_SECONDS",
]
