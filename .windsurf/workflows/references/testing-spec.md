# 后端单元测试规范

> 基于 `tests/services/` 实际代码编写，最后更新：2026-02-27

## 一、技术栈

| 组件 | 版本/工具 |
|------|----------|
| 测试框架 | pytest + pytest-asyncio |
| Mock | unittest.mock (AsyncMock / MagicMock / patch) |
| DB Mock | AsyncMock session (不依赖真实数据库) |
| Redis Mock | AsyncMock (不依赖真实 Redis) |
| 断言 | pytest.raises / assert |

## 二、目录结构

```
backend/tests/
├── __init__.py
├── services/                      # Service 层单元测试
│   ├── __init__.py
│   ├── conftest.py                # 共享 fixtures + mock 工厂
│   ├── test_auth_service.py       # AuthService（12 cases）
│   ├── test_agent_service.py      # AgentService（8 cases）
│   ├── test_analytics_service.py  # AnalyticsService（10 cases）
│   ├── test_conversation_service.py
│   ├── test_knowledge_base_service.py
│   ├── test_skill_service.py
│   ├── test_call_log_service.py
│   ├── test_tenant_service.py
│   ├── test_admin_service.py
│   ├── test_attachment_service.py
│   ├── test_quota_service.py
│   ├── test_quota_rate_limit_service.py
│   ├── test_notification_service.py
│   └── test_email_service.py
├── plugins/                       # 插件系统测试（已有 ~15 个文件）
├── api/                           # API 集成测试（按需）
└── fixtures/                      # 测试数据文件
```

## 三、conftest.py 共享 Fixtures

文件位置：`tests/services/conftest.py`

### 3.1 Mock DB Session

```python
@pytest.fixture()
def mock_db():
    """Mock AsyncSession，支持 execute/flush/commit/refresh/add/delete"""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db
```

### 3.2 Mock Redis / Celery

```python
@pytest.fixture()
def mock_redis():
    """Mock Redis client — get/set/delete/ping/exists/incr/expire"""

@pytest.fixture()
def mock_celery():
    """Mock Celery app — send_task/inspect.ping"""
```

### 3.3 Sample Data Factories

```python
@pytest.fixture()
def sample_admin_data() -> dict       # 平台管理员
def sample_tenant_data() -> dict      # 租户
def sample_tenant_admin_data() -> dict # 租户管理员
def sample_agent_data() -> dict       # 智能体
def sample_call_log_data() -> dict    # AI 调用日志
```

### 3.4 Mock 工具函数

```python
def make_mock_model(**kwargs) -> MagicMock:
    """创建 mock ORM model，支持 .attr 访问 + .to_dict()"""

def make_scalar_result(value) -> MagicMock:
    """mock db.execute() → .scalar() / .scalar_one_or_none()"""

def make_scalars_result(items: list) -> MagicMock:
    """mock db.execute() → .scalars().all() / .scalars().first()"""

def make_row_result(row_data: dict) -> MagicMock:
    """mock db.execute() → .one() 命名 Row"""
```

## 四、测试编写规范

### 4.1 文件命名

```
test_{service_name}.py
```

每个 Service 一个测试文件，文件名与 Service 文件名对应。

### 4.2 类组织

按功能分组为 `class Test{Feature}`：

```python
class TestPasswordPolicy:
    """密码策略验证测试"""

class TestAdminLogin:
    """管理员登录测试"""

class TestChangePassword:
    """密码修改测试"""
```

### 4.3 测试方法命名

```python
async def test_{action}_{scenario}(self, mock_db):
```

示例：
- `test_login_user_not_found`
- `test_duplicate_name_raises`
- `test_archive_success`
- `test_daily_limit_exceeded`

### 4.4 异步测试

所有 Service 方法是 async，测试必须标记：

```python
@pytest.mark.asyncio
async def test_something(self, mock_db):
    ...
```

### 4.5 Mock Service 实例化

Service 继承 `TenantService` / `GlobalService`，构造函数需要 DB session + tenant_id。使用 `__new__` 跳过 `__init__`：

```python
service = AgentService.__new__(AgentService)
service.db = mock_db
service.tenant_id = 1
service.repo = AsyncMock()
```

### 4.6 Mock 外部依赖

使用 `patch` 替换外部调用：

```python
with patch("app.services.common.auth_service.verify_password", return_value=False):
    with pytest.raises(AuthenticationException):
        await service.authenticate_admin("admin", "wrong")
```

对于 Service 内部方法，使用 `patch.object`：

```python
with patch.object(service, "_is_account_locked", new_callable=AsyncMock, return_value=True):
    ...
```

### 4.7 Mock DB 查询结果

```python
# 单值查询（scalar）
mock_db.execute.return_value = make_scalar_result(admin_obj)

# 列表查询（scalars）
mock_db.execute.return_value = make_scalars_result([item1, item2])

# 聚合行查询（.one()）
mock_db.execute.return_value = make_row_result({"total": 100, "avg": 50.0})
```

### 4.8 每个测试文件最低要求

- **≥ 6 个测试用例**
- 覆盖：正常流程 + 边界条件 + 错误处理
- 关键 Service（Auth/Agent/Analytics）≥ 10 个

## 五、运行测试

```bash
# 运行所有 Service 测试
cd backend
pytest tests/services/ -v

# 运行单个文件
pytest tests/services/test_auth_service.py -v

# 运行单个测试类
pytest tests/services/test_auth_service.py::TestAdminLogin -v

# 运行单个用例
pytest tests/services/test_auth_service.py::TestAdminLogin::test_login_success -v

# 带覆盖率
pytest tests/services/ --cov=app/services --cov-report=term-missing
```

## 六、测试覆盖范围

| 服务层 | 文件 | 覆盖重点 |
|--------|------|---------|
| AI | test_agent_service.py | CRUD 钩子、系统智能体保护、版本发布 |
| AI | test_conversation_service.py | 详情/归档/导出/聊天创建 |
| AI | test_knowledge_base_service.py | CRUD、toggle active |
| AI | test_skill_service.py | 包 CRUD、技能绑定/解绑 |
| AI | test_call_log_service.py | 日志查询、统计、计量 |
| AI | test_analytics_service.py | 趋势/分布/排行/延迟(CASE WHEN) |
| AI | test_quota_rate_limit_service.py | 配额检查/扣减/重置/速率限制 |
| System | test_admin_service.py | CRUD、超管保护、状态变更 |
| System | test_tenant_service.py | CRUD、slug 唯一、状态 |
| System | test_operation_log_service.py | 日志记录/查询/清理 |
| Tenant | test_attachment_service.py | 上传/删除/存储统计 |
| Tenant | test_quota_service.py | 存储/用户配额检查 |
| Common | test_auth_service.py | 登录/密码策略/Token/锁定 |
| Common | test_notification_service.py | 创建/查询/标记已读/删除 |
| Common | test_email_service.py | 发送/SMTP配置/模板/错误 |

## 七、禁止事项

- **禁止依赖真实数据库** — 所有 DB 操作通过 mock_db
- **禁止依赖真实 Redis** — 通过 mock_redis
- **禁止依赖网络** — HTTP 调用通过 patch
- **禁止测试间共享状态** — 每个测试独立 fixture
- **禁止 sleep/delay** — 异步测试不需要等待
- **禁止硬编码路径** — 使用相对路径或 fixture
