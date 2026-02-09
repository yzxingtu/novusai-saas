# Implementation Plan: AI Gateway Fixes

## Overview

修复 AI 网关模块的 31 项问题，按优先级分阶段实施：先修复运行时错误和安全漏洞，再修复代码规范问题，然后修复前端 UI，最后实现 UX 优化。

## Tasks

- [x] 1. 修复后端运行时错误（HIGH PRIORITY）
  - [x] 1.1 修复 `rate_limiter.py` 中 `get_redis()` 缺失 `await`
    - 将 `check_rate_limit()`、`record_request()`、`get_current_usage()` 中的 `redis = get_redis()` 改为 `redis = await get_redis()`
    - 参考 `cache.py` 中的正确模式
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 1.2 修复 `quota.py` 中 `get_redis()` 缺失 `await`
    - 将 `UsageTracker` 的 `get_daily_usage()`、`get_monthly_usage()`、`record_usage()` 中的 `redis = get_redis()` 改为 `redis = await get_redis()`
    - _Requirements: 1.4, 1.5, 1.6_
  - [x] 1.3 修复 `gateway.py` 中 `ChatMessage.model_dump()` 调用
    - 在文件顶部添加 `import dataclasses`
    - 将所有 `msg.model_dump()` 替换为 `dataclasses.asdict(msg)`（3 处：缓存键生成、配额估算、请求数据构建）
    - _Requirements: 2.1, 2.2, 2.3_
  - [x] 1.4 修复 `gateway.py` 中 `test_model` 的 `response.choices` 错误
    - 将 `response.choices[0].message.content` 替换为 `response.message.content`
    - _Requirements: 3.1_
  - [x] 1.5 修复 `sse.py` 中 `on_complete` 回调类型签名
    - 添加 `from typing import Awaitable` 导入
    - 将 `Callable[[int, int, int], None]` 改为 `Callable[[int, int, int], Awaitable[None]]`
    - _Requirements: 4.1_
  - [x] 1.6 为 `stream_chat` 添加速率限制和配额检查
    - 将 `stream_chat` 改为 `async def`
    - 在 `generate_chunks()` 之前添加 `_get_provider_and_key`、`_get_model` 调用
    - 添加 `RateLimiter.check_rate_limit()` 和 `self.quota_manager.check_quota()` 检查
    - 使用 `dataclasses.asdict(msg)` 进行 token 估算
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [ ]* 1.7 Write property test for ChatMessage serialization round-trip
    - **Property 1: ChatMessage serialization round-trip**
    - 使用 hypothesis 生成随机 ChatMessage，验证 `dataclasses.asdict()` → 重建的一致性
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 2. Checkpoint - 验证运行时修复
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. 修复后端代码规范问题（MEDIUM PRIORITY）
  - [x] 3.1 新增枚举类型到 `backend/app/enums/ai.py`
    - 添加 `QuotaTypeEnum`（HARD, SOFT）
    - 添加 `QuotaPeriodEnum`（DAILY, MONTHLY）
    - 添加 `UserTypeEnum`（TENANT_ADMIN）
    - 更新 `__all__` 导出列表
    - _Requirements: 7.1, 7.2, 7.3_
  - [x] 3.2 修复 `quota.py` 硬编码中文和魔法字符串
    - 将 `f"配额超出: ..."` 替换为 `_("ai.error.quota_exceeded").format(...)`
    - 将 `quota.quota_type == "hard"/"soft"` 替换为 `QuotaTypeEnum` 枚举比较
    - 将 `period == "daily"/"monthly"` 替换为 `QuotaPeriodEnum` 枚举比较
    - _Requirements: 6.1, 7.4, 7.5_
  - [x] 3.3 修复 `gateway.py` 魔法字符串和硬编码中文
    - 将 `user_type="tenant_admin"` 替换为 `UserTypeEnum.TENANT_ADMIN.value`
    - _Requirements: 7.6_
  - [x] 3.4 修复 `ai_gateway.py` 控制器硬编码中文标签
    - 将 `tags = ["AI 网关"]` 替换为 `tags = [_("menu.admin.ai_gateway_api")]`
    - _Requirements: 6.2_
  - [x] 3.5 修复 `AIProvider` 和 `ProviderApiKey` 模型 `__sortable_fields__` 命名
    - 将 `provider.py` 中 `__sortable_fields__` 重命名为 `__sortable__`
    - 将 `api_key.py` 中 `__sortable_fields__` 重命名为 `__sortable__`
    - 更新 `base_repository.py` 的 `get_sortable_fields()` 方法以兼容 `__sortable__` 字典格式
    - _Requirements: 8.1, 8.2_
  - [x] 3.6 将 Gateway 直接数据库查询迁移到 Repository 层
    - 在 `AIModelRepository` 新增 `get_active_by_name_and_provider()` 方法
    - 在 `ProviderApiKeyRepository` 新增 `get_next_available_key()` 方法
    - 修改 `AIGateway.__init__` 注入三个 Repository 实例
    - 重构 `_get_provider_and_key()` 使用 `provider_repo.get_by_code()` 和 `api_key_repo.get_available_key()`
    - 重构 `_get_model()` 使用 `model_repo.get_active_by_name_and_provider()`
    - 重构 `_get_next_api_key()` 使用 `api_key_repo.get_next_available_key()`
    - 重构 `test_model()` 使用 Repository 方法替代直接 `select()`
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  - [x] 3.7 为 `stream_chat` 添加重试机制
    - 在 `generate_chunks()` 内部包裹重试循环
    - 使用 `MAX_RETRIES`、`RETRY_BASE_DELAY`、`RETRY_MULTIPLIER` 常量
    - 重试时通过 `api_key_repo.get_next_available_key()` 切换 Key
    - _Requirements: 10.1, 10.2_
  - [x] 3.8 重构 `gateway.py` 循环导入
    - 将 `from app.services.ai import CallLogService` 移至模块顶部或 `__init__` 中
    - 如存在真正循环依赖则保留函数内导入并添加注释
    - _Requirements: 11.1_
  - [ ]* 3.9 Write property test for stream_chat rate limit enforcement
    - **Property 2: stream_chat rate limit enforcement**
    - Mock RateLimiter 使其抛出 RateLimitExceeded，验证 stream_chat 在 yield 前抛出异常
    - **Validates: Requirements 5.1, 5.3**
  - [ ]* 3.10 Write property test for stream_chat quota enforcement
    - **Property 3: stream_chat quota enforcement**
    - Mock QuotaManager 使其抛出 QuotaExceeded，验证 stream_chat 在 yield 前抛出异常
    - **Validates: Requirements 5.2, 5.4**
  - [ ]* 3.11 Write property test for stream_chat retry with key rotation
    - **Property 4: stream_chat retry with key rotation**
    - 生成随机重试场景，验证重试次数和 Key 轮换行为
    - **Validates: Requirements 10.1, 10.2**

- [x] 4. Checkpoint - 验证后端代码规范修复
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. 修复前端 UI 问题
  - [x] 5.1 修复 `usage/data.ts` 硬编码英文标签
    - 将 `'Chat'`、`'Embedding'`、`'Image'` 替换为 `$t('admin.ai.usage.type_options.chat')` 等
    - 添加对应的 i18n 翻译 key 到中英文 JSON 文件
    - _Requirements: 12.1_
  - [x] 5.2 将 health 页面 API 调用提取到 API 层
    - 在 `api/admin/ai.ts` 新增 `HealthStatus` 接口和 `getAIHealthStatusApi` 函数
    - 修改 `health/index.vue` 导入并使用 `getAIHealthStatusApi` 替代 `requestClient.get`
    - 删除 `health/index.vue` 中的本地 `HealthStatus` 接口定义
    - _Requirements: 13.1, 13.2, 13.3_
  - [x] 5.3 修复模型列表 `isActive` 显示方式
    - 将 `models/index.vue` 中 `isActive_cell` 的 `<Switch disabled>` 替换为 `<Tag>` 组件
    - 使用 `success`/`default` 颜色区分启用/禁用状态
    - _Requirements: 14.1_
  - [x] 5.4 修复 usage 页面显示名称替代 ID
    - 修改 `usage/data.ts` 列定义：`tenant_id` → `tenant_name`，`model_id` → `model_name`
    - 更新列标题 i18n key
    - _Requirements: 15.1, 15.2_
  - [x] 5.5 补充缺失的前端 API 和表单字段
    - 在 `api/admin/ai.ts` 新增 `toggleAIModelStatusApi` 函数
    - 在 `AIModelInfo` 接口添加 `rpm_limit` 和 `tpm_limit` 字段
    - 在 `models/data.ts` 表单 Schema 添加 `rpm_limit` 和 `tpm_limit` 字段
    - 修改价格列标题添加单位 `($/1K)`
    - _Requirements: 16.1, 16.2, 16.3_

- [x] 6. Checkpoint - 验证前端修复
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. UX 优化 - 使用量可视化
  - [x] 7.1 添加使用量汇总统计卡片
    - 在 usage 页面表格上方添加统计卡片组件（总调用次数、总 Token 数、总费用、成功率）
    - 调用 `getAICallLogStatisticsApi` 或新增汇总 API 获取数据
    - _Requirements: 17.1_
  - [x] 7.2 添加日期范围筛选器
    - 在 usage 搜索表单添加日期范围字段 `filter[stat_date][gte]` 和 `filter[stat_date][lte]`
    - _Requirements: 17.2_

- [x] 8. UX 优化 - 调用日志详情
  - [x] 8.1 新增调用日志详情抽屉组件
    - 创建 `views/admin/ai/call-logs/modules/detail.vue`
    - 展示完整请求/响应 JSON、Token 用量、延迟、状态等
    - 在列表页行点击时打开抽屉
    - _Requirements: 18.1_

- [x] 9. UX 优化 - 模型测试连通性
  - [x] 9.1 在模型列表添加测试按钮
    - 在 `models/data.ts` 操作列添加 "test" 选项
    - 调用 `/admin/ai/gateway/test` API 并展示结果（连通性、延迟、响应文本）
    - _Requirements: 19.1_

- [x] 10. UX 优化 - 配额管理页面
  - [x] 10.1 创建配额管理 CRUD 页面
    - 创建 `views/admin/ai/quotas/data.ts`（列定义、搜索、表单 Schema）
    - 创建 `views/admin/ai/quotas/index.vue`（列表页，使用 `useCrudPage`）
    - 创建 `views/admin/ai/quotas/modules/form.vue`（表单抽屉，使用 `useCrudDrawer`）
    - 在 `api/admin/ai.ts` 添加配额相关 API 函数
    - 添加路由配置和 i18n 翻译
    - _Requirements: 20.1_

- [x] 11. UX 优化 - 调用日志导出
  - [x] 11.1 添加调用日志导出功能
    - 在调用日志页面工具栏添加导出按钮
    - 实现前端 CSV 生成或调用后端导出 API
    - _Requirements: 21.1_
  - [ ]* 11.2 Write property test for CSV export validity
    - **Property 5: CSV export validity**
    - 生成随机调用日志记录集，验证 CSV 输出行数和字段完整性
    - **Validates: Requirements 21.1**

- [x] 12. Final checkpoint - 全部验证
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- 后端修改涉及的主要文件：`gateway.py`、`rate_limiter.py`、`quota.py`、`sse.py`、`enums/ai.py`、`models/ai/provider.py`、`models/ai/api_key.py`、`repositories/ai/*.py`、`api/admin/ai_gateway.py`
- 前端修改涉及的主要文件：`api/admin/ai.ts`、`views/admin/ai/usage/data.ts`、`views/admin/ai/health/index.vue`、`views/admin/ai/models/data.ts`、`views/admin/ai/models/index.vue`
