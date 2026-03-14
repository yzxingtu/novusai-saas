#!/usr/bin/env python3
"""
NovusAI License Key 生成工具

用法:
  # 生成永久 License / Generate perpetual license
  python scripts/generate_license_key.py --plugin weather-widget --email admin@example.com

  # 生成 365 天有效期 License / Generate 365-day license
  python scripts/generate_license_key.py --plugin weather-widget --email admin@example.com --days 365

  # 使用已有密钥对 / Use existing keypair
  python scripts/generate_license_key.py --plugin weather-widget --private-key <base64>

  # 生成新密钥对（首次使用）
  python scripts/generate_license_key.py --gen-keys

密钥对管理:
  首次运行时自动在 ~/.novusai/ 目录生成 Ed25519 密钥对。
  公钥需配置到环境变量 NOVUSAI_LICENSE_PUBLIC_KEY。
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

# 将 backend 目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def get_key_dir() -> Path:
    key_dir = Path.home() / ".novusai" / "license-keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    return key_dir


def generate_keypair() -> tuple[str, str]:
    """生成 Ed25519 密钥对，返回 (private_key_b64, public_key_b64)"""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes_raw()
    public_bytes = private_key.public_key().public_bytes_raw()

    return (
        base64.b64encode(private_bytes).decode(),
        base64.b64encode(public_bytes).decode(),
    )


def load_or_create_keypair() -> tuple[str, str]:
    """加载或创建密钥对"""
    key_dir = get_key_dir()
    priv_file = key_dir / "private.key"
    pub_file = key_dir / "public.key"

    if priv_file.exists() and pub_file.exists():
        private_b64 = priv_file.read_text().strip()
        public_b64 = pub_file.read_text().strip()
        return private_b64, public_b64

    print("[INFO] Generating new Ed25519 keypair...")
    private_b64, public_b64 = generate_keypair()

    priv_file.write_text(private_b64)
    pub_file.write_text(public_b64)
    priv_file.chmod(0o600)

    print(f"[INFO] Private key saved to: {priv_file}")
    print(f"[INFO] Public key saved to:  {pub_file}")
    print()

    return private_b64, public_b64


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NovusAI License Key Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--plugin", type=str, help="Plugin name (e.g. weather-widget)")
    parser.add_argument("--email", type=str, default="", help="Buyer email")
    parser.add_argument("--scope", type=str, default="*", help="Version scope (default: *)")
    parser.add_argument("--days", type=int, default=None, help="License validity in days (default: perpetual)")
    parser.add_argument("--private-key", type=str, default=None, help="Ed25519 private key (base64)")
    parser.add_argument("--gen-keys", action="store_true", help="Generate keypair and exit")
    parser.add_argument("--verify", type=str, default=None, help="Verify a license key")

    args = parser.parse_args()

    # 生成密钥对
    if args.gen_keys:
        private_b64, public_b64 = generate_keypair()
        key_dir = get_key_dir()
        (key_dir / "private.key").write_text(private_b64)
        (key_dir / "public.key").write_text(public_b64)
        (key_dir / "private.key").chmod(0o600)
        print(f"Private key: {private_b64}")
        print(f"Public key:  {public_b64}")
        print()
        print(f"Keys saved to: {key_dir}")
        print()
        print("Set environment variable for backend:")
        print(f"  NOVUSAI_LICENSE_PUBLIC_KEY={public_b64}")
        return

    # 验证 Key
    if args.verify:
        if not args.plugin:
            parser.error("--plugin is required for verification")
        from app.plugins.license import verify_license_key
        result = verify_license_key(args.verify, args.plugin)
        if result:
            print("[OK] License key is valid!")
            print(f"  Plugin:    {result.get('plugin')}")
            print(f"  Buyer:     {result.get('buyer', 'N/A')}")
            print(f"  Issued at: {result.get('issued_at')}")
            expires = result.get("expires_at")
            if expires:
                import datetime
                dt = datetime.datetime.fromtimestamp(expires, tz=datetime.timezone.utc)
                print(f"  Expires:   {dt.isoformat()}")
            else:
                print("  Expires:   Never (perpetual)")
        else:
            print("[FAIL] License key verification failed!")
            sys.exit(1)
        return

    # 生成 Key
    if not args.plugin:
        parser.error("--plugin is required")

    private_b64 = args.private_key
    public_b64 = None
    if not private_b64:
        private_b64, public_b64 = load_or_create_keypair()

    from app.plugins.license import generate_license_key

    key = generate_license_key(
        plugin_name=args.plugin,
        version_scope=args.scope,
        buyer_email=args.email,
        private_key_b64=private_b64,
        expires_days=args.days,
    )

    print("=" * 60)
    print("Generated License Key:")
    print("=" * 60)
    print(key)
    print("=" * 60)
    print()
    print(f"Plugin:  {args.plugin}")
    print(f"Email:   {args.email or 'N/A'}")
    print(f"Scope:   {args.scope}")
    if args.days:
        print(f"Expires: {args.days} days")
    else:
        print("Expires: Never (perpetual)")
    print()

    if public_b64:
        print("Public key for NOVUSAI_LICENSE_PUBLIC_KEY:")
        print(f"  {public_b64}")


if __name__ == "__main__":
    main()
