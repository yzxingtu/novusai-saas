"""
Tenant Resolution End-to-End Test / 租户识别端到端测试

真实模拟生产场景的 HTTP 请求，验证 TenantMiddleware 在多种 Host/Origin
组合下都能正确识别租户。
Real-HTTP test that exercises TenantMiddleware against a live Postgres,
covering Host/Origin combinations encountered in production.

模拟生产配置 / Simulated production config:
    TENANT_DOMAIN_SUFFIX = .nvuai.online   # 租户默认子域名后缀
    集中式 API 域名         = apidemo.nvuai.cc

测试场景 / Scenarios:
    A. 直连默认子域名:           Host=t3xxx.nvuai.online                 → 200
    B. 跨域调用集中式 API:       Host=apidemo.nvuai.cc + Origin=t3xxx... → 200
    C. 自定义域名 + 集中式 API:  Host=apidemo.nvuai.cc + Origin=a.anc.com → 200
    D. 直连自定义域名:           Host=a.anc.com                          → 200
    E. 非法 Origin 兜底:         Host=apidemo.nvuai.cc + Origin=evil.com  → 404
    F. 缺失 Origin 的恶意请求:   Host=apidemo.nvuai.cc 无 Origin          → 404

Usage:
    cd backend
    uv run python scripts/test_tenant_resolution_e2e.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import traceback
from pathlib import Path

# ⚠️ 必须在 import settings 之前注入环境变量
# Inject env vars BEFORE importing settings to override .env defaults.
os.environ["TENANT_DOMAIN_SUFFIX"] = ".nvuai.online"

# 加载 .env (DATABASE_URL 等) / Load .env to pick up DATABASE_URL etc.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import httpx
from fastapi import FastAPI, Request
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import async_session_factory
from app.middleware.tenant import TenantMiddleware, get_tenant_context
from app.models import Tenant, TenantDomain

# ============================================================
# 测试数据常量 / Test fixtures
# ============================================================
TENANT_CODE = "t3tetj7r5"
TENANT_NAME = "[E2E-TEST] 演示租户4"
DEFAULT_DOMAIN = "t3tetj7r5.nvuai.online"
CUSTOM_DOMAIN = "a.anc.com"
API_DOMAIN = "apidemo.nvuai.cc"
EVIL_ORIGIN_HOST = "evil.attacker.com"


# ============================================================
# 最小化 FastAPI app（仅挂中间件 + 探针路由）
# Minimal FastAPI app with TenantMiddleware + probe route only.
# 这样不会触发完整 app 的 plugin/celery/sio 初始化。
# ============================================================
def build_probe_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/public/tenant/config")
    async def probe(request: Request):
        ctx = get_tenant_context(request)
        if not ctx or not ctx.is_resolved:
            return httpx_404_response()
        return {
            "code": 0,
            "tenant_id": ctx.tenant_id,
            "tenant_code": ctx.tenant_code,
            "domain_type": ctx.domain_type,
            "name": ctx.tenant.name,
        }

    # 中间件挂载顺序：TenantMiddleware 必须最外层（先于路由处理）
    app.add_middleware(TenantMiddleware)
    return app


def httpx_404_response():
    from fastapi import HTTPException, status

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": 4040, "message": "tenant.not_found"},
    )


# ============================================================
# Seed / Cleanup
# ============================================================
async def seed_data() -> int:
    """创建测试租户 + 自定义域名 + 默认子域名记录 / Create fixtures."""
    async with async_session_factory() as db:
        # 清理可能存在的同名残留 / Clean up any leftover test rows
        await _cleanup_inner(db)

        # 创建租户
        tenant = Tenant(
            code=TENANT_CODE,
            name=TENANT_NAME,
            is_active=True,
        )
        db.add(tenant)
        await db.flush()

        # 默认子域名记录（模拟创建租户时自动生成）
        db.add(
            TenantDomain(
                tenant_id=tenant.id,
                domain=DEFAULT_DOMAIN,
                is_verified=True,
                is_primary=True,
                ssl_status="none",
            )
        )
        # 自定义域名（已验证）
        db.add(
            TenantDomain(
                tenant_id=tenant.id,
                domain=CUSTOM_DOMAIN,
                is_verified=True,
                is_primary=False,
                ssl_status="none",
            )
        )
        await db.commit()
        return tenant.id


async def _cleanup_inner(db) -> None:
    # 找现有 tenant
    res = await db.execute(select(Tenant).where(Tenant.code == TENANT_CODE))
    t = res.scalar_one_or_none()
    if t:
        await db.execute(
            delete(TenantDomain).where(TenantDomain.tenant_id == t.id)
        )
        await db.execute(delete(Tenant).where(Tenant.id == t.id))
        await db.commit()


async def cleanup_data() -> None:
    async with async_session_factory() as db:
        await _cleanup_inner(db)


# ============================================================
# 场景执行 / Run scenarios
# ============================================================
SCENARIOS = [
    {
        "name": "A. 直连默认子域名（Stage 1: subdomain）",
        "host": DEFAULT_DOMAIN,
        "origin": None,
        "expect_status": 200,
        "expect_domain_type": "subdomain",
    },
    {
        "name": "B. 跨域 → 集中式 API + 默认子域名 Origin（Stage 2: subdomain）",
        "host": API_DOMAIN,
        "origin": f"https://{DEFAULT_DOMAIN}",
        "expect_status": 200,
        "expect_domain_type": "subdomain",
    },
    {
        "name": "C. 跨域 → 集中式 API + 自定义域名 Origin（Stage 2: custom）★关键场景",
        "host": API_DOMAIN,
        "origin": f"https://{CUSTOM_DOMAIN}",
        "expect_status": 200,
        "expect_domain_type": "custom",
    },
    {
        "name": "D. 直连自定义域名（Stage 1: custom）",
        "host": CUSTOM_DOMAIN,
        "origin": None,
        "expect_status": 200,
        "expect_domain_type": "custom",
    },
    {
        "name": "E. 集中式 API + 非法 Origin（Stage 2 兜底失败）",
        "host": API_DOMAIN,
        "origin": f"https://{EVIL_ORIGIN_HOST}",
        "expect_status": 404,
        "expect_domain_type": None,
    },
    {
        "name": "F. 集中式 API 无 Origin（直接 404）",
        "host": API_DOMAIN,
        "origin": None,
        "expect_status": 404,
        "expect_domain_type": None,
    },
]


async def run_scenarios(app: FastAPI) -> tuple[int, int]:
    """按场景循环发请求，返回 (passed, total)."""
    transport = httpx.ASGITransport(app=app)
    passed = 0
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for sc in SCENARIOS:
            headers = {"host": sc["host"]}
            if sc["origin"]:
                headers["origin"] = sc["origin"]

            t0 = time.perf_counter()
            resp = await client.get("/api/public/tenant/config", headers=headers)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            ok_status = resp.status_code == sc["expect_status"]
            ok_type = True
            actual_type = None
            if resp.status_code == 200:
                try:
                    actual_type = resp.json().get("domain_type")
                except Exception:
                    actual_type = "<not-json>"
                ok_type = actual_type == sc["expect_domain_type"]
            ok = ok_status and ok_type

            mark = "✅" if ok else "❌"
            print(f"\n{mark} {sc['name']}")
            print(f"   Host  : {sc['host']}")
            print(f"   Origin: {sc['origin'] or '(none)'}")
            print(
                f"   → status={resp.status_code} (expected {sc['expect_status']}) "
                f"| domain_type={actual_type} (expected {sc['expect_domain_type']}) "
                f"| {elapsed_ms:.1f}ms"
            )
            if not ok:
                print(f"   body: {resp.text[:200]}")

            if ok:
                passed += 1
    return passed, len(SCENARIOS)


# ============================================================
# Main
# ============================================================
async def main() -> int:
    print("=" * 72)
    print("Tenant Resolution E2E Test")
    print("=" * 72)
    print(f"DATABASE_URL          : {settings.DATABASE_URL.split('@')[-1]}")
    print(f"TENANT_DOMAIN_SUFFIX  : {settings.TENANT_DOMAIN_SUFFIX}")
    print(f"租户子域名             : {DEFAULT_DOMAIN}")
    print(f"租户自定义域名         : {CUSTOM_DOMAIN}")
    print(f"集中式 API 域名        : {API_DOMAIN}")
    print("-" * 72)

    print("\n[1/3] Seed 测试数据 ...")
    tenant_id = await seed_data()
    print(f"      ✓ tenant id={tenant_id}, code={TENANT_CODE}")

    print("\n[2/3] 构建最小 FastAPI app + TenantMiddleware ...")
    app = build_probe_app()
    print("      ✓ app ready")

    print("\n[3/3] 执行场景测试 ...")
    try:
        passed, total = await run_scenarios(app)
    finally:
        print("\n[*]   清理测试数据 ...")
        await cleanup_data()
        print("      ✓ cleaned")

    print("\n" + "=" * 72)
    print(f"Result: {passed}/{total} 通过")
    print("=" * 72)
    return 0 if passed == total else 1


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except Exception:
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
