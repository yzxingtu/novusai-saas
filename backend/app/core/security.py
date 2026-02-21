"""
安全模块

提供 JWT Token 生成/验证、密码哈希等安全相关功能
"""

from datetime import timedelta
from typing import Any

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.base_model import utc_now

# Token 类型常量
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_IMPERSONATE = "impersonate"  # 一键登录临时 Token

# Token 作用域常量（用户类型）
TOKEN_SCOPE_ADMIN = "admin"             # 平台管理员
TOKEN_SCOPE_TENANT_ADMIN = "tenant_admin"  # 租户管理员
TOKEN_SCOPE_TENANT_USER = "tenant_user"    # 租户业务用户

# Impersonate Token 过期时间（秒）
IMPERSONATE_TOKEN_EXPIRE_SECONDS = 60


def create_access_token(
    subject: str | int,
    scope: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    创建 Access Token
    
    Args:
        subject: Token 主体（通常是用户 ID）
        scope: Token 作用域（用户类型），必须为 TOKEN_SCOPE_* 常量之一
        expires_delta: 过期时间增量
        extra_claims: 额外的 claims
        
    Returns:
        编码后的 JWT Token
    """
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "sub": str(subject),
        "scope": scope,
        "exp": expire,
        "iat": utc_now(),
        "type": TOKEN_TYPE_ACCESS,
    }
    
    if extra_claims:
        to_encode.update(extra_claims)
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: str | int,
    scope: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    创建 Refresh Token
    
    Args:
        subject: Token 主体（通常是用户 ID）
        scope: Token 作用域（用户类型），必须为 TOKEN_SCOPE_* 常量之一
        expires_delta: 过期时间增量
        
    Returns:
        编码后的 JWT Token
    """
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode = {
        "sub": str(subject),
        "scope": scope,
        "exp": expire,
        "iat": utc_now(),
        "type": TOKEN_TYPE_REFRESH,
    }
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


class TokenExpiredError(Exception):
    """Token 已过期（区别于无效 Token）"""


def decode_token(token: str, raise_on_expired: bool = False) -> dict[str, Any] | None:
    """
    解码并验证 Token
    
    Args:
        token: JWT Token 字符串
        raise_on_expired: 为 True 时，过期 Token 抛出 TokenExpiredError
            而非静默返回 None，允许调用方区分过期和无效。
        
    Returns:
        解码后的 payload，验证失败返回 None
    
    Raises:
        TokenExpiredError: raise_on_expired=True 且 Token 已过期
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except ExpiredSignatureError:
        if raise_on_expired:
            raise TokenExpiredError()
        return None
    except JWTError:
        return None


def verify_token(token: str, token_type: str = TOKEN_TYPE_ACCESS) -> str | None:
    """
    验证 Token 并返回 subject
    
    Args:
        token: JWT Token 字符串
        token_type: 期望的 Token 类型
        
    Returns:
        Token 的 subject（用户 ID），验证失败返回 None
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    # 检查 Token 类型
    if payload.get("type") != token_type:
        return None
    
    return payload.get("sub")


def verify_token_with_scope(
    token: str,
    expected_scope: str,
    token_type: str = TOKEN_TYPE_ACCESS,
    raise_on_expired: bool = False,
) -> tuple[str | None, str | None]:
    """
    验证 Token 并检查 scope
    
    Args:
        token: JWT Token 字符串
        expected_scope: 期望的 scope（用户类型）
        token_type: 期望的 Token 类型
        raise_on_expired: 为 True 时，过期 Token 抛出 TokenExpiredError
        
    Returns:
        (subject, scope) 元组，验证失败返回 (None, None)
    
    Raises:
        TokenExpiredError: raise_on_expired=True 且 Token 已过期
    """
    payload = decode_token(token, raise_on_expired=raise_on_expired)
    if payload is None:
        return None, None
    
    # 检查 Token 类型
    if payload.get("type") != token_type:
        return None, None
    
    # 检查 scope
    scope = payload.get("scope")
    if scope != expected_scope:
        return None, None
    
    return payload.get("sub"), scope


def get_token_payload(
    token: str,
    token_type: str = TOKEN_TYPE_ACCESS,
) -> dict[str, Any] | None:
    """
    获取 Token 的完整 payload
    
    Args:
        token: JWT Token 字符串
        token_type: 期望的 Token 类型
        
    Returns:
        Token 的 payload，验证失败返回 None
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    # 检查 Token 类型
    if payload.get("type") != token_type:
        return None
    
    return payload


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
        
    Returns:
        密码是否正确
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """
    获取密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')


def create_token_pair(
    subject: str | int,
    scope: str,
    extra_claims: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    创建 Token 对（access_token + refresh_token）
    
    Args:
        subject: Token 主体
        scope: Token 作用域（用户类型）
        extra_claims: 额外的 claims（仅添加到 access_token）
        
    Returns:
        包含 access_token 和 refresh_token 的字典
    """
    return {
        "access_token": create_access_token(subject, scope=scope, extra_claims=extra_claims),
        "refresh_token": create_refresh_token(subject, scope=scope),
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
    创建一键登录临时 Token
    
    用于平台管理员一键登录租户后台或租户管理员一键登录用户端
    
    Args:
        admin_id: 发起者 ID（平台管理员或租户管理员）
        target_scope: 目标 scope（tenant_admin 或 tenant_user）
        target_tenant_id: 目标租户 ID
        target_role_id: 目标角色 ID（可选）
        expires_seconds: 过期时间（秒），默认 60 秒
        
    Returns:
        编码后的 JWT Token
    """
    expire = utc_now() + timedelta(seconds=expires_seconds)
    
    to_encode = {
        "sub": str(admin_id),  # 发起者 ID
        "type": TOKEN_TYPE_IMPERSONATE,
        "target_scope": target_scope,
        "target_tenant_id": target_tenant_id,
        "exp": expire,
        "iat": utc_now(),
    }
    
    if target_role_id is not None:
        to_encode["target_role_id"] = target_role_id
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_impersonate_token(
    token: str,
    expected_target_scope: str,
) -> dict[str, Any] | None:
    """
    验证一键登录 Token
    
    Args:
        token: JWT Token 字符串
        expected_target_scope: 期望的目标 scope
        
    Returns:
        Token 的 payload，验证失败返回 None
        payload 包含: sub, target_scope, target_tenant_id, target_role_id(可选)
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    # 检查 Token 类型
    if payload.get("type") != TOKEN_TYPE_IMPERSONATE:
        return None
    
    # 检查目标 scope
    if payload.get("target_scope") != expected_target_scope:
        return None
    
    return payload


def _get_encryption_key() -> bytes:
    """
    获取加密密钥
    
    使用 SECRET_KEY 派生 Fernet 密钥
    Fernet 需要 32 字节的 base64 编码密钥
    """
    # 确保密钥长度符合 Fernet 要求
    key = settings.SECRET_KEY.encode()
    # 使用 SHA256 生成固定长度的密钥
    import hashlib
    import base64
    hash_key = hashlib.sha256(key).digest()
    return base64.urlsafe_b64encode(hash_key)


def encrypt_data(plaintext: str) -> str:
    """
    加密数据
    
    Args:
        plaintext: 明文
        
    Returns:
        加密后的密文（Base64 编码）
    """
    f = Fernet(_get_encryption_key())
    encrypted = f.encrypt(plaintext.encode('utf-8'))
    return encrypted.decode('utf-8')


def decrypt_data(ciphertext: str) -> str:
    """
    解密数据
    
    Args:
        ciphertext: 密文（Base64 编码）
        
    Returns:
        解密后的明文
    """
    f = Fernet(_get_encryption_key())
    decrypted = f.decrypt(ciphertext.encode('utf-8'))
    return decrypted.decode('utf-8')


__all__ = [
    "create_access_token",
    "create_refresh_token",
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
    "TOKEN_TYPE_ACCESS",
    "TOKEN_TYPE_REFRESH",
    "TOKEN_TYPE_IMPERSONATE",
    "TOKEN_SCOPE_ADMIN",
    "TOKEN_SCOPE_TENANT_ADMIN",
    "TOKEN_SCOPE_TENANT_USER",
    "IMPERSONATE_TOKEN_EXPIRE_SECONDS",
]
