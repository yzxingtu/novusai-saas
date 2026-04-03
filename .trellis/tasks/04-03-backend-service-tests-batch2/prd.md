# Backend Service Unit Tests - Batch 2 (中型服务)

## Purpose

为 4 个中等规模且缺少测试的 AI 服务编写全面的单元测试。

## Target Services

### 1. quota_diagnostics_service.py (289 行)
- 路径: `backend/app/services/ai/quota_diagnostics_service.py`
- 测试文件: `backend/tests/services/test_quota_diagnostics_service.py`

### 2. model_service.py (224 行)
- 路径: `backend/app/services/ai/model_service.py`
- 测试文件: `backend/tests/services/test_model_service.py`

### 3. api_key_service.py (191 行)
- 路径: `backend/app/services/ai/api_key_service.py`
- 测试文件: `backend/tests/services/test_api_key_service.py`

### 4. tenant_analytics_service.py (128 行)
- 路径: `backend/app/services/ai/tenant_analytics_service.py`
- 测试文件: `backend/tests/services/test_tenant_analytics_service.py`

## Testing Conventions

参考现有测试模式（来自 .trellis/spec/backend/quality-guidelines.md）：
- 使用 `__new__` 实例化服务，手动注入 `db`, `tenant_id`, `repo`
- 使用 `pytest.mark.asyncio` 标记异步测试
- 不依赖真实数据库、Redis、网络或第三方 API
- 复用 `backend/tests/services/conftest.py` 中的 fixtures 和 mock factories
- 参考模式文件: `backend/tests/services/test_attachment_service.py`

## Implementation Plan

对每个服务：
1. 阅读服务源码，理解所有公开方法
2. 识别依赖项（repo、db、其他服务）
3. 创建 mock/stub
4. 为每个公开方法编写测试，覆盖：
   - 正常路径（happy path）
   - 边界情况（空数据、无效 ID 等）
   - 异常情况
5. 运行 `pytest tests/services/test_<service>.py -v` 确认通过
6. 运行 `ruff check tests/services/test_<service>.py` 确认无 lint 违规

## Acceptance Criteria

- [ ] 4 个测试文件全部创建
- [ ] 每个服务至少覆盖所有公开方法
- [ ] 所有测试通过
- [ ] ruff check 通过
- [ ] 不依赖外部资源
