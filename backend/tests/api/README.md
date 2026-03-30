# API 测试

本目录包含针对管理端与企业端接口的手工集成测试脚本。测试风格统一继承 `BaseAPITest`，通过 `httpx` 直接请求已启动的本地 API 服务。

## 主要文件

```text
tests/api/
├── README.md
├── base.py
├── config.py
├── run_all.py
├── test_admin_auth.py
├── test_admin_permissions.py
├── test_admin_permission_roles.py
├── test_admin_organization.py
├── test_admin_admins.py
├── test_admin_tenants.py
├── test_admin_periodic_tasks.py
├── test_captcha_flow.py
├── test_tenant_auth.py
├── test_tenant_permission_roles.py
├── test_tenant_organization.py
└── test_tenant_admins.py
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

1. 确保 API 服务已启动。
2. 确保数据库已迁移并有初始化数据。
3. 安装测试依赖：`pip install httpx`。
4. 企业端认证与组织测试必须使用企业专属域名作为 `TEST_API_BASE_URL`，例如 `http://ss.dakkii.cn:8000`。

### 运行所有测试

```bash
cd /path/to/backend
python -m tests.api.run_all

# 只运行平台管理端测试
python -m tests.api.run_all --module admin

# 只运行企业管理端测试
python -m tests.api.run_all --module tenant
```

### 运行单个模块测试

```bash
python -m tests.api.test_admin_auth
python -m tests.api.test_admin_permissions
python -m tests.api.test_admin_permission_roles
python -m tests.api.test_admin_organization
python -m tests.api.test_admin_admins
python -m tests.api.test_admin_tenants
python -m tests.api.test_admin_periodic_tasks
python -m tests.api.test_captcha_flow
python -m tests.api.test_tenant_auth
python -m tests.api.test_tenant_permission_roles
python -m tests.api.test_tenant_organization
python -m tests.api.test_tenant_admins
```

## 测试覆盖范围

### 平台管理端（`/admin`）

| 模块 | 接口 | 测试项 |
|------|------|--------|
| 认证 | `POST /admin/auth/login` | 正确凭据、错误密码、不存在用户 |
| 认证 | `GET /admin/auth/me` | 已认证、未认证 |
| 认证 | `POST /admin/auth/refresh` | 有效 Token、无效 Token |
| 认证 | `PUT /admin/auth/password` | 正确旧密码、错误旧密码（错误旧密码返回 `422`，业务码 `4004`） |
| 认证 | `POST /admin/auth/logout` | 登出 |
| 权限 | `GET /admin/permissions` | 获取权限树、展平校验、检查 menu/operation 节点 |
| 权限 | `GET /admin/permissions/menus` | 获取用户菜单 |
| 权限绑定 | `GET /admin/permissions` | 获取平台权限树 |
| 权限绑定 | `POST /admin/organization` | 创建带权限的组织节点 |
| 权限绑定 | `GET /admin/organization/{org_node_id}` | 获取组织节点权限详情 |
| 权限绑定 | `PUT /admin/organization/{org_node_id}` | 更新或清空组织节点权限绑定 |
| 权限绑定 | `DELETE /admin/organization/{org_node_id}` | 删除权限绑定测试节点 |
| 组织架构 | `GET /admin/organization` | 获取组织根节点 |
| 组织架构 | `GET /admin/organization/tree` | 获取组织树 |
| 组织架构 | `GET /admin/organization/{org_node_id}` | 获取节点详情 |
| 组织架构 | `POST /admin/organization` | 创建组织节点 |
| 组织架构 | `PUT /admin/organization/{org_node_id}` | 更新组织节点 |
| 组织架构 | `PUT /admin/organization/{org_node_id}/authority` | 更新数据范围策略 |
| 组织架构 | `GET /admin/organization/{org_node_id}/members` | 获取成员列表 |
| 组织架构 | `POST /admin/organization/{org_node_id}/members/create` | 在节点下创建成员 |
| 组织架构 | `PUT /admin/organization/{org_node_id}/members/{admin_id}` | 更新成员组织归属与权限角色 |
| 组织架构 | `PUT /admin/organization/{org_node_id}/leader` | 设置或清空负责人 |
| 组织架构 | `DELETE /admin/organization/{org_node_id}/members/{admin_id}` | 从节点移除成员 |
| 组织架构 | `DELETE /admin/organization/{org_node_id}` | 删除组织节点 |
| 管理员成员 | `POST /admin/organization/{org_node_id}/members/create` | 在组织节点下创建平台管理员成员 |
| 管理员成员 | `GET /admin/organization/{org_node_id}/members` | 获取成员列表 |
| 管理员成员 | `PUT /admin/organization/{org_node_id}/members/{admin_id}` | 更新成员资料或迁移节点 |
| 管理员成员 | `PUT /admin/organization/{org_node_id}/members/{admin_id}/reset-password` | 重置成员密码 |
| 管理员成员 | `PUT /admin/organization/{org_node_id}/members/{admin_id}/status` | 切换成员状态 |
| 管理员成员 | `DELETE /admin/organization/{org_node_id}/members/{admin_id}` | 从组织节点移除成员 |
| 企业 | `GET /admin/tenants` | 列表、分页、过滤 |
| 企业 | `POST /admin/tenants` | 创建（需携带 owner 账号字段） |
| 企业 | `GET /admin/tenants/{id}` | 详情、不存在 |
| 企业 | `PUT /admin/tenants/{id}` | 更新 |
| 企业 | `PUT /admin/tenants/{id}/status` | 切换状态 |
| 企业 | `DELETE /admin/tenants/{id}` | 当前校验 owner 依赖阻塞删除 |
| 定时任务 | `GET /admin/periodic-tasks` | 列表 |
| 定时任务 | `POST /admin/periodic-tasks` | 创建 selected_tenants 待绑定任务、拒绝不支持 tenant 分发的处理器 |
| 定时任务 | `PUT /admin/periodic-tasks/{id}/bindings` | 省略 scope 更新显式绑定、保留显式作用域 |
| 定时任务 | `PUT /admin/periodic-tasks/{id}` | 切换到 all_tenants 时清空显式 binding |
| 定时任务 | `POST /admin/periodic-tasks/{id}/trigger` | 待绑定任务/禁用插件任务的明确错误提示 |

### 企业管理端（`/tenant`）

| 模块 | 接口 | 测试项 |
|------|------|--------|
| 认证 | `POST /tenant/auth/login` | 正确凭据、错误密码 |
| 认证 | `GET /tenant/auth/me` | 已认证、未认证 |
| 认证 | `POST /tenant/auth/refresh` | 有效 Token、无效 Token |
| 认证 | `POST /tenant/auth/logout` | 登出 |
| 权限角色 | `GET /tenant/permission-roles` | 获取权限角色列表 |
| 权限角色 | `POST /tenant/permission-roles` | 创建权限角色 |
| 权限角色 | `GET /tenant/permission-roles/{role_id}` | 获取权限角色详情 |
| 权限角色 | `PUT /tenant/permission-roles/{role_id}` | 更新权限角色 |
| 权限角色 | `PUT /tenant/permission-roles/{role_id}/permissions` | 分配权限 |
| 权限角色 | `DELETE /tenant/permission-roles/{role_id}` | 删除权限角色 |
| 组织架构 | `GET /tenant/organization` | 获取组织根节点 |
| 组织架构 | `GET /tenant/organization/tree` | 获取组织树 |
| 组织架构 | `GET /tenant/organization/{org_node_id}` | 获取节点详情 |
| 组织架构 | `POST /tenant/organization` | 创建组织节点 |
| 组织架构 | `PUT /tenant/organization/{org_node_id}` | 更新组织节点 |
| 组织架构 | `PUT /tenant/organization/{org_node_id}/authority` | 更新数据范围策略 |
| 组织架构 | `GET /tenant/organization/{org_node_id}/members` | 获取成员列表 |
| 组织架构 | `POST /tenant/organization/{org_node_id}/members/create` | 在节点下创建成员 |
| 组织架构 | `PUT /tenant/organization/{org_node_id}/members/{admin_id}` | 更新成员组织归属与权限角色 |
| 组织架构 | `PUT /tenant/organization/{org_node_id}/leader` | 设置或清空负责人 |
| 组织架构 | `DELETE /tenant/organization/{org_node_id}/members/{admin_id}` | 从节点移除成员 |
| 组织架构 | `DELETE /tenant/organization/{org_node_id}` | 删除组织节点 |
| 管理员 | `GET /tenant/admins` | 列表、分页 |
| 管理员 | `POST /tenant/admins` | 创建 |
| 管理员 | `GET /tenant/admins/{id}` | 详情 |
| 管理员 | `PUT /tenant/admins/{id}` | 更新 |
| 管理员 | `PUT /tenant/admins/{id}/status` | 切换状态 |
| 管理员 | `PUT /tenant/admins/{id}/reset-password` | 重置密码 |
| 管理员 | `DELETE /tenant/admins/{id}` | 删除、删除自己 |

## 扩展测试

新增测试模块时，继续沿用当前模式：

1. 继承 `BaseAPITest`。
2. 在 `setup()` 中完成登录和测试数据初始化。
3. 在 `teardown()` 中用 `contextlib.suppress(Exception)` 清理资源。
4. 使用 `assert_success`、`assert_error`、`assert_equals`、`assert_has_keys`、`assert_true` 做断言。

最小模板示例：

```python
#!/usr/bin/env python3
from tests.api.base import BaseAPITest, assert_success, config


class ManualTestNewModule(BaseAPITest):
    module_name = "新模块"

    def setup(self):
        self._do_login()

    def _run_tests(self):
        self.run_test("测试用例 1", self.test_case_1)

    def test_case_1(self):
        resp = self.client.get("/some/endpoint")
        assert_success(resp)

    def _do_login(self):
        resp = self.client.post("/admin/auth/login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD,
        })
        self.client.set_token(resp.json()["data"]["access_token"])


if __name__ == "__main__":
    test = ManualTestNewModule()
    report = test.run_all()
    report.print_summary()
```
