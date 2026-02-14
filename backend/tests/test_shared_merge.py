"""
共享文件确定性合并 — 单元测试

覆盖：
- 文件类型分类
- 前端 Router 合并（新增/去重/排序）
- 前端 API Export 合并（新增/去重/排序）
- 后端路由注册 __init__.py 合并（import + include_router）
- 统一入口 merge_shared_file
- 幂等性验证
"""

import pytest

from app.codegen.shared_merge import (
    SharedFileType,
    classify_shared_file,
    is_shared_file,
    merge_backend_router_init,
    merge_frontend_api_export,
    merge_frontend_router,
    merge_shared_file,
)


# ============================================================
# 文件类型分类
# ============================================================


class TestClassifySharedFile:
    """共享文件类型分类"""

    def test_frontend_router_admin(self):
        path = "frontend/apps/web-antd/src/router/routes/admin/index.ts"
        assert classify_shared_file(path) == SharedFileType.FRONTEND_ROUTER

    def test_frontend_router_tenant(self):
        path = "frontend/apps/web-antd/src/router/routes/tenant/index.ts"
        assert classify_shared_file(path) == SharedFileType.FRONTEND_ROUTER

    def test_frontend_api_export_admin(self):
        path = "frontend/apps/web-antd/src/api/admin/index.ts"
        assert classify_shared_file(path) == SharedFileType.FRONTEND_API_EXPORT

    def test_frontend_api_export_tenant(self):
        path = "frontend/apps/web-antd/src/api/tenant/index.ts"
        assert classify_shared_file(path) == SharedFileType.FRONTEND_API_EXPORT

    def test_backend_router_init_admin(self):
        path = "backend/app/api/admin/__init__.py"
        assert classify_shared_file(path) == SharedFileType.BACKEND_ROUTER_INIT

    def test_backend_router_init_tenant(self):
        path = "backend/app/api/tenant/__init__.py"
        assert classify_shared_file(path) == SharedFileType.BACKEND_ROUTER_INIT

    def test_i18n_json(self):
        path = "frontend/apps/web-antd/src/locales/langs/zh-CN/admin/system.json"
        assert classify_shared_file(path) == SharedFileType.I18N_JSON

    def test_unknown_file(self):
        path = "backend/app/models/order.py"
        assert classify_shared_file(path) == SharedFileType.UNKNOWN

    def test_is_shared_file_true(self):
        assert is_shared_file("backend/app/api/admin/__init__.py")

    def test_is_shared_file_false(self):
        assert not is_shared_file("backend/app/models/order.py")

    def test_backslash_normalization(self):
        path = "frontend\\apps\\web-antd\\src\\api\\admin\\index.ts"
        assert classify_shared_file(path) == SharedFileType.FRONTEND_API_EXPORT


# ============================================================
# 前端 Router 合并
# ============================================================


class TestMergeFrontendRouter:
    """前端路由文件合并"""

    EXISTING_ROUTER = """\
import { BasicLayout } from '#/layouts';
import OrderRoutes from './order';

const routes = [
  {
    component: BasicLayout,
    path: '/admin',
    children: [
      ...OrderRoutes,
    ],
  },
];

export default routes;
"""

    NEW_ROUTER_PRODUCT = """\
import ProductRoutes from './product';

      ...ProductRoutes,
"""

    NEW_ROUTER_ORDER = """\
import OrderRoutes from './order';

      ...OrderRoutes,
"""

    def test_add_new_import(self):
        """新增 import 不重复"""
        result = merge_frontend_router(self.EXISTING_ROUTER, self.NEW_ROUTER_PRODUCT)
        assert result.success
        assert "./product" in result.added
        assert "import ProductRoutes from './product';" in result.content

    def test_skip_duplicate_import(self):
        """已存在 import 被跳过"""
        result = merge_frontend_router(self.EXISTING_ROUTER, self.NEW_ROUTER_ORDER)
        assert "./order" in result.skipped
        # 不应重复
        count = result.content.count("import OrderRoutes from './order'")
        assert count == 1

    def test_idempotent_merge(self):
        """重复 merge 结果一致"""
        r1 = merge_frontend_router(self.EXISTING_ROUTER, self.NEW_ROUTER_PRODUCT)
        r2 = merge_frontend_router(r1.content, self.NEW_ROUTER_PRODUCT)
        assert r1.content == r2.content

    def test_multiple_entities_sorted(self):
        """多实体 import 按字母序排列"""
        new_content = """\
import CustomerRoutes from './customer';
import ProductRoutes from './product';
"""
        result = merge_frontend_router(self.EXISTING_ROUTER, new_content)
        # customer 和 product 都应该被添加
        assert "./customer" in result.added
        assert "./product" in result.added

        # 验证 import 顺序
        lines = result.content.splitlines()
        import_lines = [l for l in lines if l.strip().startswith("import")]
        import_sources = []
        for l in import_lines:
            if "from" in l:
                src = l.split("from")[1].strip().strip("'\"").rstrip(";")
                import_sources.append(src)
        # customer 应在 product 之前（字母序）
        cust_idx = next(i for i, s in enumerate(import_sources) if "customer" in s)
        prod_idx = next(i for i, s in enumerate(import_sources) if "product" in s)
        assert cust_idx < prod_idx

    def test_preserves_trailing_newline(self):
        """保留末尾换行"""
        result = merge_frontend_router(self.EXISTING_ROUTER, self.NEW_ROUTER_PRODUCT)
        assert result.content.endswith("\n")


# ============================================================
# 前端 API Export 合并
# ============================================================


class TestMergeFrontendApiExport:
    """前端 API export 聚合文件合并"""

    EXISTING_EXPORT = """\
export * from './orders';
export * from './users';
"""

    def test_add_new_export(self):
        """新增 export 行"""
        new_content = "export * from './products';\n"
        result = merge_frontend_api_export(self.EXISTING_EXPORT, new_content)
        assert result.success
        assert "./products" in result.added
        assert "export * from './products';" in result.content

    def test_skip_duplicate_export(self):
        """已存在 export 被跳过"""
        new_content = "export * from './orders';\n"
        result = merge_frontend_api_export(self.EXISTING_EXPORT, new_content)
        assert "./orders" in result.skipped
        count = result.content.count("export * from './orders'")
        assert count == 1

    def test_idempotent_export_merge(self):
        """重复 merge 结果一致"""
        new_content = "export * from './products';\n"
        r1 = merge_frontend_api_export(self.EXISTING_EXPORT, new_content)
        r2 = merge_frontend_api_export(r1.content, new_content)
        assert r1.content == r2.content

    def test_multiple_exports_sorted(self):
        """多个 export 按字母序排序"""
        new_content = """\
export * from './categories';
export * from './products';
export * from './brands';
"""
        result = merge_frontend_api_export(self.EXISTING_EXPORT, new_content)
        assert len(result.added) == 3

        # 所有 export 行按字母序全局排序
        lines = result.content.strip().splitlines()
        export_lines = [l for l in lines if l.strip().startswith("export")]
        sources = []
        for l in export_lines:
            src = l.split("from")[1].strip().strip("'\"").rstrip(";")
            sources.append(src)
        assert sources == sorted(sources)

    def test_named_export(self):
        """命名 export 合并"""
        existing = "export { getOrdersApi } from './orders';\n"
        new_content = "export { getProductsApi } from './products';\n"
        result = merge_frontend_api_export(existing, new_content)
        assert "./products" in result.added
        assert "export { getProductsApi } from './products';" in result.content

    def test_preserves_trailing_newline(self):
        """保留末尾换行"""
        new_content = "export * from './products';\n"
        result = merge_frontend_api_export(self.EXISTING_EXPORT, new_content)
        assert result.content.endswith("\n")


# ============================================================
# 后端路由注册 __init__.py 合并
# ============================================================


class TestMergeBackendRouterInit:
    """后端路由注册聚合文件合并"""

    EXISTING_INIT = """\
from fastapi import APIRouter

from app.api.admin.orders import OrderController
from app.api.admin.users import UserController

router = APIRouter(prefix="/admin")

router.include_router(OrderController.router, tags=["orders"])
router.include_router(UserController.router, tags=["users"])
"""

    def test_add_new_import_and_router(self):
        """新增 import + include_router"""
        new_content = """\
from app.api.admin.products import ProductController

router.include_router(ProductController.router, tags=["products"])
"""
        result = merge_backend_router_init(self.EXISTING_INIT, new_content)
        assert result.success
        assert "import:app.api.admin.products" in result.added
        assert "include_router:ProductController" in result.added
        assert "from app.api.admin.products import ProductController" in result.content
        assert "router.include_router(ProductController.router" in result.content

    def test_skip_duplicate_import(self):
        """已存在 import 被跳过"""
        new_content = """\
from app.api.admin.orders import OrderController

router.include_router(OrderController.router, tags=["orders"])
"""
        result = merge_backend_router_init(self.EXISTING_INIT, new_content)
        assert "import:app.api.admin.orders" in result.skipped
        assert "include_router:OrderController" in result.skipped
        count = result.content.count("from app.api.admin.orders import OrderController")
        assert count == 1

    def test_idempotent_merge(self):
        """重复 merge 结果一致"""
        new_content = """\
from app.api.admin.products import ProductController

router.include_router(ProductController.router, tags=["products"])
"""
        r1 = merge_backend_router_init(self.EXISTING_INIT, new_content)
        r2 = merge_backend_router_init(r1.content, new_content)
        assert r1.content == r2.content

    def test_multiple_entities_sorted(self):
        """多实体按字母序排列"""
        new_content = """\
from app.api.admin.products import ProductController
from app.api.admin.categories import CategoryController

router.include_router(ProductController.router, tags=["products"])
router.include_router(CategoryController.router, tags=["categories"])
"""
        result = merge_backend_router_init(self.EXISTING_INIT, new_content)
        # 验证 import 顺序（category 在 product 之前）
        lines = result.content.splitlines()
        import_lines = [
            l for l in lines
            if l.strip().startswith("from app.api.admin.")
        ]
        modules = [l.split("from ")[1].split(" import")[0] for l in import_lines]
        # categories 应在 products 之前（字母序）
        cat_idx = next(i for i, m in enumerate(modules) if "categories" in m)
        prod_idx = next(i for i, m in enumerate(modules) if "products" in m)
        assert cat_idx < prod_idx

    def test_preserves_trailing_newline(self):
        """保留末尾换行"""
        existing = self.EXISTING_INIT
        if not existing.endswith("\n"):
            existing += "\n"
        new_content = """\
from app.api.admin.products import ProductController

router.include_router(ProductController.router, tags=["products"])
"""
        result = merge_backend_router_init(existing, new_content)
        assert result.content.endswith("\n")


# ============================================================
# 统一入口 merge_shared_file
# ============================================================


class TestMergeSharedFile:
    """统一合并入口"""

    def test_frontend_router_dispatch(self):
        """前端 router 文件正确分发"""
        path = "frontend/apps/web-antd/src/router/routes/admin/index.ts"
        existing = "import OrderRoutes from './order';\n"
        new_content = "import ProductRoutes from './product';\n"
        result = merge_shared_file(path, existing, new_content)
        assert result.success
        assert "./product" in result.added

    def test_frontend_api_dispatch(self):
        """前端 API export 文件正确分发"""
        path = "frontend/apps/web-antd/src/api/admin/index.ts"
        existing = "export * from './orders';\n"
        new_content = "export * from './products';\n"
        result = merge_shared_file(path, existing, new_content)
        assert result.success
        assert "./products" in result.added

    def test_backend_router_dispatch(self):
        """后端 __init__.py 文件正确分发"""
        path = "backend/app/api/admin/__init__.py"
        existing = "from app.api.admin.orders import OrderController\nrouter = APIRouter()\n"
        new_content = "from app.api.admin.products import ProductController\n"
        result = merge_shared_file(path, existing, new_content)
        assert result.success

    def test_unknown_file_error(self):
        """未知文件返回错误"""
        path = "backend/app/models/order.py"
        result = merge_shared_file(path, "existing", "new")
        assert not result.success
        assert "Unknown" in result.error

    def test_i18n_passthrough(self):
        """i18n JSON 直接传递（由 writer 处理）"""
        path = "frontend/apps/web-antd/src/locales/langs/zh-CN/admin.json"
        result = merge_shared_file(path, "{}", '{"new": "value"}')
        assert result.success


# ============================================================
# 顺序无关性
# ============================================================


class TestOrderIndependence:
    """实体顺序变化不影响最终结果"""

    def test_router_order_independent(self):
        """不同实体顺序生成相同路由文件"""
        base = "import OrderRoutes from './order';\n"

        # 顺序 1: product → customer
        r1 = merge_frontend_router(base, "import ProductRoutes from './product';\n")
        r1 = merge_frontend_router(r1.content, "import CustomerRoutes from './customer';\n")

        # 顺序 2: customer → product
        r2 = merge_frontend_router(base, "import CustomerRoutes from './customer';\n")
        r2 = merge_frontend_router(r2.content, "import ProductRoutes from './product';\n")

        assert r1.content == r2.content

    def test_api_export_order_independent(self):
        """不同实体顺序生成相同 API export 文件"""
        base = "export * from './orders';\n"

        r1 = merge_frontend_api_export(base, "export * from './products';\n")
        r1 = merge_frontend_api_export(r1.content, "export * from './customers';\n")

        r2 = merge_frontend_api_export(base, "export * from './customers';\n")
        r2 = merge_frontend_api_export(r2.content, "export * from './products';\n")

        assert r1.content == r2.content

    def test_backend_init_order_independent(self):
        """不同实体顺序生成相同后端 __init__.py"""
        base = """\
from fastapi import APIRouter
from app.api.admin.orders import OrderController

router = APIRouter()
router.include_router(OrderController.router, tags=["orders"])
"""
        new_product = """\
from app.api.admin.products import ProductController

router.include_router(ProductController.router, tags=["products"])
"""
        new_customer = """\
from app.api.admin.customers import CustomerController

router.include_router(CustomerController.router, tags=["customers"])
"""
        r1 = merge_backend_router_init(base, new_product)
        r1 = merge_backend_router_init(r1.content, new_customer)

        r2 = merge_backend_router_init(base, new_customer)
        r2 = merge_backend_router_init(r2.content, new_product)

        assert r1.content == r2.content
