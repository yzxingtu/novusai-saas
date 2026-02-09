# 需求文档：AI 网关模块缺陷修复

## 简介

AI 网关模块经过深度代码审查，发现了 13 个后端问题、8 个前端 UI 问题和 10 个 UX 优化建议。本需求文档覆盖所有已识别的缺陷修复和改进项，按优先级分为运行时错误/安全修复、代码规范修复、前端 UI 修复和 UX 优化四大类。

## 术语表

- **Gateway**: AI 网关服务，统一调用各 AI 供应商的入口层（`backend/app/ai/gateway.py`）
- **RateLimiter**: 速率限制器，基于 Redis 滑动窗口算法限制调用频率（`backend/app/ai/rate_limiter.py`）
- **UsageTracker**: 使用量追踪器，基于 Redis 实时追踪 Token 使用量（`backend/app/ai/quota.py`）
- **QuotaManager**: 配额管理器，检查和执行租户配额限制（`backend/app/ai/quota.py`）
- **SSEStreamingResponse**: SSE 流式响应封装，将 AsyncIterator 转换为 SSE 格式（`backend/app/ai/sse.py`）
- **ChatMessage**: 聊天消息数据类（`@dataclass`，非 Pydantic BaseModel）
- **ChatResponse**: 聊天响应数据类，包含 `message` 属性（非 `choices`）
- **LabeledStrEnum**: 项目枚举基类，支持国际化标签
- **Repository**: 数据访问层，负责数据库查询构建
- **AIResponseCache**: AI 响应缓存服务（`backend/app/ai/cache.py`）

## 需求

### 需求 1：修复 Redis 异步调用缺失 await

**用户故事：** 作为平台运维人员，我希望 AI 网关的 Redis 调用正确使用异步模式，以避免运行时错误导致服务不可用。

#### 验收标准

1. WHEN RateLimiter 的 `check_rate_limit` 方法调用 `get_redis()` 时，THE RateLimiter SHALL 使用 `await get_redis()` 获取 Redis 客户端实例
2. WHEN RateLimiter 的 `record_request` 方法调用 `get_redis()` 时，THE RateLimiter SHALL 使用 `await get_redis()` 获取 Redis 客户端实例
3. WHEN RateLimiter 的 `get_current_usage` 方法调用 `get_redis()` 时，THE RateLimiter SHALL 使用 `await get_redis()` 获取 Redis 客户端实例
4. WHEN UsageTracker 的 `get_daily_usage` 方法调用 `get_redis()` 时，THE UsageTracker SHALL 使用 `await get_redis()` 获取 Redis 客户端实例
5. WHEN UsageTracker 的 `get_monthly_usage` 方法调用 `get_redis()` 时，THE UsageTracker SHALL 使用 `await get_redis()` 获取 Redis 客户端实例
6. WHEN UsageTracker 的 `record_usage` 方法调用 `get_redis()` 时，THE UsageTracker SHALL 使用 `await get_redis()` 获取 Redis 客户端实例

### 需求 2：修复 ChatMessage dataclass 的 model_dump() 调用

**用户故事：** 作为平台运维人员，我希望 Gateway 正确序列化 ChatMessage 对象，以避免 `AttributeError` 导致所有 AI 调用失败。

#### 验收标准

1. WHEN Gateway 生成缓存键需要序列化 ChatMessage 列表时，THE Gateway SHALL 使用 `dataclasses.asdict(msg)` 替代 `msg.model_dump()`
2. WHEN Gateway 构建请求数据需要序列化 ChatMessage 列表时，THE Gateway SHALL 使用 `dataclasses.asdict(msg)` 替代 `msg.model_dump()`
3. WHEN Gateway 估算配额需要序列化 ChatMessage 列表时，THE Gateway SHALL 使用 `dataclasses.asdict(msg)` 替代 `msg.model_dump()`

### 需求 3：修复 test_model 方法中 ChatResponse 属性访问错误

**用户故事：** 作为平台管理员，我希望模型测试功能正确提取响应文本，以便验证模型配置是否正确。

#### 验收标准

1. WHEN Gateway 的 `test_model` 方法从非流式响应中提取文本时，THE Gateway SHALL 使用 `response.message.content` 替代 `response.choices[0].message.content`

### 需求 4：修复 SSE on_complete 回调类型签名

**用户故事：** 作为开发者，我希望 SSEStreamingResponse 的回调类型签名与实际使用一致，以避免类型检查错误和潜在的运行时问题。

#### 验收标准

1. THE SSEStreamingResponse SHALL 将 `on_complete` 参数类型声明为 `Callable[[int, int, int], Awaitable[None]] | None`，以匹配实际传入的异步回调函数

### 需求 5：为 stream_chat 添加速率限制和配额检查

**用户故事：** 作为平台运维人员，我希望流式聊天接口与非流式接口具有相同的安全检查，以防止租户通过流式端点绕过限流和配额限制。

#### 验收标准

1. WHEN 租户通过 `stream_chat` 发起流式调用时，THE Gateway SHALL 在创建适配器之前执行速率限制检查
2. WHEN 租户通过 `stream_chat` 发起流式调用时，THE Gateway SHALL 在创建适配器之前执行配额检查
3. WHEN 速率限制检查未通过时，THE Gateway SHALL 抛出 `RateLimitExceeded` 异常并拒绝流式调用
4. WHEN 配额检查未通过时，THE Gateway SHALL 抛出 `QuotaExceeded` 异常并拒绝流式调用

### 需求 6：消除后端硬编码中文字符串

**用户故事：** 作为开发者，我希望所有面向用户的字符串使用国际化函数，以支持多语言环境。

#### 验收标准

1. WHEN QuotaManager 抛出配额超出异常时，THE QuotaManager SHALL 使用 `_()` 国际化函数生成错误消息，替代硬编码中文 `f"配额超出: ..."`
2. WHEN AdminAIGatewayController 声明 API 标签时，THE AdminAIGatewayController SHALL 使用 `_()` 国际化函数替代硬编码中文 `"AI 网关"`

### 需求 7：将魔法字符串替换为 LabeledStrEnum 枚举

**用户故事：** 作为开发者，我希望所有业务常量使用枚举类型，以提高代码可维护性和类型安全性。

#### 验收标准

1. THE 系统 SHALL 在 `backend/app/enums/ai.py` 中新增 `QuotaTypeEnum` 枚举，包含 `HARD` 和 `SOFT` 两个值
2. THE 系统 SHALL 在 `backend/app/enums/ai.py` 中新增 `QuotaPeriodEnum` 枚举，包含 `DAILY` 和 `MONTHLY` 两个值
3. THE 系统 SHALL 在 `backend/app/enums/ai.py` 中新增 `UserTypeEnum` 枚举，包含 `TENANT_ADMIN` 值
4. WHEN QuotaManager 比较配额类型时，THE QuotaManager SHALL 使用 `QuotaTypeEnum` 枚举值替代字符串 `"hard"` 和 `"soft"`
5. WHEN QuotaManager 比较配额周期时，THE QuotaManager SHALL 使用 `QuotaPeriodEnum` 枚举值替代字符串 `"daily"` 和 `"monthly"`
6. WHEN Gateway 记录用户类型时，THE Gateway SHALL 使用 `UserTypeEnum` 枚举值替代字符串 `"tenant_admin"`

### 需求 8：修复模型 __sortable__ 属性命名

**用户故事：** 作为开发者，我希望所有模型遵循统一的属性命名约定，以确保排序功能正常工作。

#### 验收标准

1. THE AIProvider 模型 SHALL 使用 `__sortable__` 替代 `__sortable_fields__` 作为可排序字段声明属性名
2. THE ProviderApiKey 模型 SHALL 使用 `__sortable__` 替代 `__sortable_fields__` 作为可排序字段声明属性名

### 需求 9：将 Gateway 直接数据库查询迁移到 Repository 层

**用户故事：** 作为开发者，我希望 Gateway 通过 Repository 层访问数据库，以遵循项目分层架构规范。

#### 验收标准

1. WHEN Gateway 需要查询供应商信息时，THE Gateway SHALL 通过 Repository 方法获取数据，替代直接使用 `select()` 语句
2. WHEN Gateway 需要查询 API Key 时，THE Gateway SHALL 通过 Repository 方法获取数据，替代直接使用 `select()` 语句
3. WHEN Gateway 需要查询模型信息时，THE Gateway SHALL 通过 Repository 方法获取数据，替代直接使用 `select()` 语句
4. WHEN Gateway 的 `test_model` 方法需要查询供应商和 API Key 时，THE Gateway SHALL 通过 Repository 方法获取数据，替代直接使用 `select()` 语句

### 需求 10：为 stream_chat 添加重试机制

**用户故事：** 作为平台运维人员，我希望流式调用具有与非流式调用相同的重试能力，以提高服务可靠性。

#### 验收标准

1. WHEN 流式调用遇到可重试错误时，THE Gateway SHALL 使用指数退避策略进行重试
2. WHEN 流式调用重试时，THE Gateway SHALL 尝试切换到下一个可用的 API Key

### 需求 11：重构 Gateway 中的循环导入

**用户故事：** 作为开发者，我希望消除函数体内的延迟导入，以提高代码可维护性。

#### 验收标准

1. THE Gateway SHALL 将 `CallLogService` 的导入从函数体内移至模块顶部或通过依赖注入方式解决循环依赖

### 需求 12：修复前端硬编码字符串

**用户故事：** 作为开发者，我希望前端所有用户可见文本使用 `$t()` 国际化函数，以支持多语言。

#### 验收标准

1. WHEN usage/data.ts 定义请求类型下拉选项时，THE 系统 SHALL 使用 `$t()` 替代硬编码英文标签 `'Chat'`、`'Embedding'`、`'Image'`

### 需求 13：将 health 页面 API 调用提取到 API 层

**用户故事：** 作为开发者，我希望所有 API 调用集中在 API 层管理，以遵循项目架构规范。

#### 验收标准

1. THE 系统 SHALL 在 `api/admin/ai.ts` 中新增 `getAIHealthStatusApi` 函数和 `HealthStatus` 接口定义
2. WHEN health/index.vue 加载健康状态数据时，THE 页面 SHALL 调用 `getAIHealthStatusApi` 替代直接使用 `requestClient.get`
3. THE health/index.vue SHALL 从 `api/admin/ai.ts` 导入 `HealthStatus` 类型，替代本地接口定义

### 需求 14：修复模型列表 isActive 显示方式

**用户故事：** 作为平台管理员，我希望模型列表中的启用状态以只读标签形式展示，以避免误导用户认为可以直接切换状态。

#### 验收标准

1. WHEN 模型列表渲染 `isActive` 列时，THE 页面 SHALL 使用 Tag/Badge 组件替代 disabled Switch 组件展示状态

### 需求 15：usage 页面显示名称替代 ID

**用户故事：** 作为平台管理员，我希望使用量统计页面显示租户名称和模型名称，以提高数据可读性。

#### 验收标准

1. WHEN usage 页面显示租户信息时，THE 页面 SHALL 显示租户名称替代原始 `tenant_id`
2. WHEN usage 页面显示模型信息时，THE 页面 SHALL 显示模型名称替代原始 `model_id`

### 需求 16：补充缺失的前端 API 和表单字段

**用户故事：** 作为平台管理员，我希望前端功能与后端模型完整对齐，以便管理所有模型属性。

#### 验收标准

1. THE 系统 SHALL 在 `api/admin/ai.ts` 中新增 `toggleAIModelStatusApi` 函数用于切换模型启用状态
2. WHEN 模型表单编辑模型时，THE 表单 SHALL 包含 `rpm_limit` 和 `tpm_limit` 字段
3. WHEN 模型列表显示价格列时，THE 列 SHALL 显示单位标识 `$/1K tokens`

### 需求 17：UX 优化 - 使用量可视化

**用户故事：** 作为平台管理员，我希望使用量页面提供汇总卡片和图表，以便快速了解整体使用情况。

#### 验收标准

1. WHEN 用户访问使用量页面时，THE 页面 SHALL 在表格上方显示汇总统计卡片（总调用次数、总 Token 数、总费用、成功率）
2. WHEN 用户访问使用量页面时，THE 页面 SHALL 提供日期范围筛选器

### 需求 18：UX 优化 - 调用日志详情

**用户故事：** 作为平台管理员，我希望能查看调用日志的详细信息，以便排查问题。

#### 验收标准

1. WHEN 用户点击调用日志行时，THE 页面 SHALL 打开详情抽屉展示完整的请求和响应数据

### 需求 19：UX 优化 - 模型测试连通性

**用户故事：** 作为平台管理员，我希望在供应商和模型管理页面直接测试连通性，以便快速验证配置。

#### 验收标准

1. WHEN 用户在模型列表页面点击"测试"按钮时，THE 页面 SHALL 调用测试 API 并展示连通性结果

### 需求 20：UX 优化 - 配额管理页面

**用户故事：** 作为平台管理员，我希望有独立的配额管理页面，以便配置和查看租户配额。

#### 验收标准

1. THE 系统 SHALL 提供配额管理 CRUD 页面，支持查看、创建、编辑和删除租户配额配置

### 需求 21：UX 优化 - 调用日志导出

**用户故事：** 作为平台管理员，我希望能导出调用日志数据，以便进行离线分析和报告。

#### 验收标准

1. WHEN 用户在调用日志页面点击"导出"按钮时，THE 页面 SHALL 将当前筛选条件下的日志数据导出为 CSV 文件

