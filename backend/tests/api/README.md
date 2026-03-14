# API 测试

本目录包含针对所有已实现 API 接口的集成测试脚本。

## 目录结构

```
tests/api/
├── README.md               # 本文档
├── __init__.py
├── config.py               # 测试配置文件
├── base.py                 # 基础测试工具类
├── run_all.py              # 测试运行入口
├── test_admin_auth.py      # 平台管理员认证测试
├── test_admin_permissions.py # 平台权限管理测试
├── test_admin_roles.py     # 平台角色管理测试
├── test_admin_admins.py    # 平台管理员管理测试
├── test_admin_tenants.py   # 企业管理测试
├── test_captcha_flow.py    # 验证码最小化自测
├── test_tenant_auth.py     # 企业管理员认证测试
├── test_tenant_roles.py    # 企业角色管理测试
└── test_tenant_admins.py   # 企业管理员管理测试
```

## 配置

### 方式一：修改配置文件

编辑 `config.py` 中的 `TestConfig` 类：

```python
class TestConfig:
    BASE_URL = "http://localhost:8000"
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "admin123456"
    TENANT_ADMIN_USERNAME = ""  # 如需测试企业端，请配置
    TENANT_ADMIN_PASSWORD = ""
```

### 方式二：使用环境变量

```bash
export TEST_API_BASE_URL=http://localhost:8000
export TEST_ADMIN_USERNAME=admin
export TEST_ADMIN_PASSWORD=admin123456
export TEST_TENANT_ADMIN_USERNAME=tenant_admin
export TEST_TENANT_ADMIN_PASSWORD=tenant123456
export TEST_LANGUAGE=zh-cn
```

## 运行测试

### 前提条件

1. 确保 API 服务已启动
2. 确保数据库已迁移并有初始数据（至少有一个超级管理员）
3. 安装测试依赖：`pip install httpx`

### 运行所有测试

```bash
# 在项目根目录下运行
cd /path/to/backend
python -m tests.api.run_all

# 只运行平台管理端测试
python -m tests.api.run_all --module admin

# 只运行企业管理端测试
python -m tests.api.run_all --module tenant
```

### 运行单个模块测试

```bash
# 平台管理员认证
python -m tests.api.test_admin_auth
 
# 验证码最小化自测
python -m tests.api.test_captcha_flow

# 平台权限管理
python -m tests.api.test_admin_permissions

# 平台角色管理
python -m tests.api.test_admin_roles

# 平台管理员管理
python -m tests.api.test_admin_admins

# 企业管理
python -m tests.api.test_admin_tenants

# 企业管理员认证
python -m tests.api.test_tenant_auth

# 企业角色管理
python -m tests.api.test_tenant_roles

# 企业管理员管理
python -m tests.api.test_tenant_admins
```

## 测试覆盖范围

### 平台管理端 (/admin)

| 模块 | 接口 | 测试项 |
|------|------|--------|
| 认证 | POST /admin/auth/login | 正确凭据、错误密码、不存在用户 |
| 认证 | GET /admin/auth/me | 已认证、未认证 |
| 认证 | POST /admin/auth/refresh | 有效Token、无效Token |
| 认证 | PUT /admin/auth/password | 正确旧密码、错误旧密码 |
| 认证 | POST /admin/auth/logout | 登出 |
| 权限 | GET /admin/permissions | 获取权限树 |
| 权限 | GET /admin/permissions/list | 获取权限列表、按类型过滤 |
| 权限 | GET /admin/permissions/menus | 获取用户菜单 |
| 角色 | GET /admin/roles | 获取角色列表 |
| 角色 | POST /admin/roles | 创建角色、重复代码 |
| 角色 | GET /admin/roles/{id} | 获取详情、不存在 |
| 角色 | PUT /admin/roles/{id} | 更新角色 |
| 角色 | PUT /admin/roles/{id}/permissions | 分配权限 |
| 角色 | DELETE /admin/roles/{id} | 删除角色、不存在 |
| 管理员 | GET /admin/admins | 列表、分页、过滤 |
| 管理员 | POST /admin/admins | 创建、重复用户名 |
| 管理员 | GET /admin/admins/{id} | 详情、不存在 |
| 管理员 | PUT /admin/admins/{id} | 更新 |
| 管理员 | PUT /admin/admins/{id}/status | 切换状态 |
| 管理员 | PUT /admin/admins/{id}/reset-password | 重置密码 |
| 管理员 | DELETE /admin/admins/{id} | 删除、删除自己 |
| 企业 | GET /admin/tenants | 列表、分页、过滤 |
| 企业 | POST /admin/tenants | 创建、重复代码 |
| 企业 | GET /admin/tenants/{id} | 详情、不存在 |
| 企业 | PUT /admin/tenants/{id} | 更新 |
| 企业 | PUT /admin/tenants/{id}/status | 切换状态 |
| 企业 | DELETE /admin/tenants/{id} | 删除 |

### 企业管理端 (/tenant)

| 模块 | 接口 | 测试项 |
|------|------|--------|
| 认证 | POST /tenant/auth/login | 正确凭据、错误密码 |
| 认证 | GET /tenant/auth/me | 已认证、未认证 |
| 认证 | POST /tenant/auth/refresh | 有效Token、无效Token |
| 认证 | POST /tenant/auth/logout | 登出 |
| 角色 | GET /tenant/roles | 获取角色列表 |
| 角色 | POST /tenant/roles | 创建角色、重复代码 |
| 角色 | GET /tenant/roles/{id} | 获取详情 |
| 角色 | PUT /tenant/roles/{id} | 更新角色 |
| 角色 | PUT /tenant/roles/{id}/permissions | 分配权限 |
| 角色 | DELETE /tenant/roles/{id} | 删除角色 |
| 管理员 | GET /tenant/admins | 列表、分页 |
| 管理员 | POST /tenant/admins | 创建 |
| 管理员 | GET /tenant/admins/{id} | 详情 |
| 管理员 | PUT /tenant/admins/{id} | 更新 |
| 管理员 | PUT /tenant/admins/{id}/status | 切换状态 |
| 管理员 | PUT /tenant/admins/{id}/reset-password | 重置密码 |
| 管理员 | DELETE /tenant/admins/{id} | 删除、删除自己 |

## 测试输出示例

```
🚀 开始 API 测试...
📍 测试目标: http://localhost:8000

======================================================================
📋 测试模块: 平台管理员认证 (/admin/auth)
======================================================================
✅ PASSED 登录 - 正确凭据 (0.15s)
✅ PASSED 登录 - 错误密码 (0.08s)
✅ PASSED 登录 - 不存在的用户 (0.07s)
✅ PASSED 获取当前用户信息 - 已认证 (0.05s)
✅ PASSED 获取当前用户信息 - 未认证 (0.04s)
✅ PASSED 刷新 Token - 有效 Token (0.06s)
✅ PASSED 刷新 Token - 无效 Token (0.04s)
✅ PASSED 修改密码 - 正确旧密码 (0.25s)
✅ PASSED 修改密码 - 错误旧密码 (0.05s)
✅ PASSED 登出 (0.04s)
----------------------------------------------------------------------
📊 总计: 10 | ✅ 通过: 10 | ❌ 失败: 0 | ⏭️ 跳过: 0
⏱️  耗时: 0.83s
======================================================================
```

## 扩展测试

要添加新的测试模块，可以参考现有测试文件的结构：

```python
#!/usr/bin/env python3
from tests.api.base import BaseAPITest, assert_success, assert_error, config

class TestNewModule(BaseAPITest):
    module_name = "新模块名称"
    
    def setup(self):
        self._do_login()
    
    def _run_tests(self):
        self.run_test("测试用例1", self.test_case_1)
        self.run_test("测试用例2", self.test_case_2)
    
    def test_case_1(self):
        resp = self.client.get("/some/endpoint")
        assert_success(resp)
    
    def test_case_2(self):
        resp = self.client.post("/some/endpoint", data={"key": "value"})
        assert_success(resp)
    
    def _do_login(self):
        resp = self.client.post("/admin/auth/login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD,
        })
        self.client.set_token(resp.json()["data"]["access_token"])

if __name__ == "__main__":
    test = TestNewModule()
    report = test.run_all()
    report.print_summary()
```
