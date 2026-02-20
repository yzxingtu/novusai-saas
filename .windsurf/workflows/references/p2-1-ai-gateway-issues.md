# P2-1 AI 网关核心 - 问题清单与修复建议

## 文档信息
- **模块**: P2-1 AI 网关核心
- **检查日期**: 2026-02-09
- **检查人**: Code Review
- **严重程度**: 🔴 高（3项）| 🟡 中（2项）| 🟢 低（1项）

---

## 一、后端架构问题

### 1.1 🔴 Repository 继承错误 - AICallLogRepository

**问题描述**:
`AICallLogRepository` 继承 `BaseRepository` 而不是 `TenantRepository`，但对应的模型 `AICallLog` 继承 `TenantModel`。

**文件位置**:
```
backend/app/repositories/ai/call_log_repository.py:L22
```

**当前代码**:
```python
class AICallLogRepository(BaseRepository[AICallLog]):
    """
    AI 调用日志 Repository
    """
    
    def __init__(self, db: AsyncSession):
        super().__init__(AICallLog, db)
```

**问题影响**:
- ❌ 租户隔离失效 - `TenantRepository` 的自动 `tenant_id` 过滤不生效
- ❌ 所有租户可以看到其他租户的调用日志
- ❌ 违反项目分层架构规范

**修复方案**:
```python
from app.core.base_repository import TenantRepository  # 修改导入

class AICallLogRepository(TenantRepository[AICallLog]):  # 修改继承
    """
    AI 调用日志 Repository
    """
    
    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        super().__init__(AICallLog, db, tenant_id)  # 调用父类构造
```

**关联修改**:
- `AICallLogService` 需要传入 `tenant_id`
- 管理端查询所有租户日志时，需要特殊处理（传 `tenant_id=None`）

---

### 1.2 🔴 Repository 位置和继承双重错误 - UsageStatRepository

**问题描述**:
`UsageStatRepository` 定义在 `metering_service.py` 中（违反分层规范），且继承 `BaseRepository` 而不是 `TenantRepository`。

**文件位置**:
```
backend/app/services/ai/metering_service.py:L132
```

**当前代码**:
```python
# 错误 1: 定义在 Service 文件中
class UsageStatRepository(BaseRepository[UsageStat]):  # 错误 2: 继承 BaseRepository
    """
    使用量统计 Repository
    """
    
    def __init__(self, db: AsyncSession):
        super().__init__(UsageStat, db)
```

**问题影响**:
- ❌ 违反分层架构 - Repository 应该独立放在 `repositories/ai/` 目录
- ❌ 租户隔离失效 - `UsageStat` 是 `TenantModel`，但用 `BaseRepository` 无自动过滤
- ❌ 代码难以维护 - 其他 Service 想使用 `UsageStatRepository` 时必须导入 `metering_service`

**修复方案**:

**步骤 1**: 创建独立文件 `backend/app/repositories/ai/usage_stat_repository.py`:
```python
"""
使用量统计 Repository

提供使用量统计的查询和聚合功能
"""

from datetime import date
from typing import Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantRepository
from app.models.ai import UsageStat


class UsageStatRepository(TenantRepository[UsageStat]):
    """
    使用量统计 Repository
    """
    
    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        super().__init__(UsageStat, db, tenant_id)
    
    async def get_or_create_stat(
        self,
        tenant_id: int,
        model_id: int,
        request_type: str,
        stat_date: date,
        user_id: Optional[int] = None,
    ) -> UsageStat:
        """
        获取或创建统计记录
        
        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            request_type: 请求类型
            stat_date: 统计日期
            user_id: 用户 ID（可选）
            
        Returns:
            UsageStat 实例
        """
        stmt = select(UsageStat).where(
            and_(
                UsageStat.tenant_id == tenant_id,
                UsageStat.model_id == model_id,
                UsageStat.request_type == request_type,
                UsageStat.stat_date == stat_date,
                UsageStat.user_id == user_id if user_id else UsageStat.user_id.is_(None)
            )
        )
        result = await self.db.execute(stmt)
        stat = result.scalar_one_or_none()
        
        if not stat:
            stat = UsageStat(
                tenant_id=tenant_id,
                model_id=model_id,
                request_type=request_type,
                stat_date=stat_date,
                user_id=user_id,
                call_count=0,
                total_tokens=0,
                input_tokens=0,
                output_tokens=0,
                total_cost=0.0,
                success_count=0,
                failed_count=0,
            )
            self.db.add(stat)
            await self.db.flush()
        
        return stat
    
    async def get_usage_summary(
        self,
        tenant_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        获取用量汇总统计
        
        Args:
            tenant_id: 租户 ID
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            汇总数据字典
        """
        # 使用 TenantRepository 的 _apply_tenant_filter 自动过滤
        stmt = select(
            func.sum(UsageStat.total_tokens).label("total_tokens"),
            func.sum(UsageStat.input_tokens).label("input_tokens"),
            func.sum(UsageStat.output_tokens).label("output_tokens"),
            func.sum(UsageStat.call_count).label("call_count"),
            func.sum(UsageStat.total_cost).label("total_cost"),
            func.sum(UsageStat.success_count).label("success_count"),
            func.sum(UsageStat.failed_count).label("failed_count"),
        )
        
        # 应用租户过滤
        stmt = self._apply_tenant_filter(stmt)
        
        if start_date:
            stmt = stmt.where(UsageStat.stat_date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStat.stat_date <= end_date)
        
        result = await self.db.execute(stmt)
        row = result.one()
        
        return {
            "total_tokens": row.total_tokens or 0,
            "input_tokens": row.input_tokens or 0,
            "output_tokens": row.output_tokens or 0,
            "call_count": row.call_count or 0,
            "total_cost": row.total_cost or 0.0,
            "success_count": row.success_count or 0,
            "failed_count": row.failed_count or 0,
        }
```

**步骤 2**: 修改 `metering_service.py`，移除内嵌的 `UsageStatRepository`:
```python
# 删除以下代码
# class UsageStatRepository(BaseRepository[UsageStat]): ...

# 改为导入
from app.repositories.ai.usage_stat_repository import UsageStatRepository
```

**步骤 3**: 更新 `backend/app/repositories/ai/__init__.py`:
```python
from app.repositories.ai.usage_stat_repository import UsageStatRepository

__all__ = [
    # ... 其他导出
    "UsageStatRepository",
]
```

---

### 1.3 🟡 Service 继承问题 - 所有 AI Service 继承 BaseService

**问题描述**:
所有 AI 相关的 Service（`TenantQuotaService`, `CallLogService` 等）都继承 `BaseService` 而不是 `TenantService`，即使它们处理的是租户级数据。

**文件位置**:
```
backend/app/services/ai/tenant_quota_service.py:L20
backend/app/services/ai/call_log_service.py:L23
backend/app/services/ai/tenant_rate_limit_service.py:L18
```

**当前代码**:
```python
class TenantQuotaService(BaseService[TenantQuota, TenantQuotaRepository]):
    ...
```

**问题影响**:
- 🟡 代码一致性差 - 其他租户级 Service 都继承 `TenantService`
- 🟡 需要手动传递 `tenant_id`，容易出错
- 🟡 无法使用 `TenantService` 提供的自动隔离方法

**修复方案**:
```python
from app.core.base_service import TenantService  # 修改导入

class TenantQuotaService(TenantService[TenantQuota, TenantQuotaRepository]):
    """
    租户 AI 配额配置 Service
    """
    
    model = TenantQuota
    repository_class = TenantQuotaRepository
    
    def __init__(self, db: AsyncSession, tenant_id: int) -> None:
        super().__init__(db, tenant_id)  # TenantService 接收 tenant_id
    
    async def get_quota(
        self,
        model_id: Optional[int] = None,
        period: str = "monthly"
    ) -> Optional[TenantQuota]:
        """
        获取租户配额配置
        
        不需要再传 tenant_id，使用 self.tenant_id
        """
        return await self.repository.get_by_tenant_and_model(
            self.tenant_id, model_id, period  # 使用 self.tenant_id
        )
```

**注意**: 此修复需要配合 Repository 的修复一起进行。

---

## 二、前端问题

### 2.1 🔴 缺少英文翻译文件

**问题描述**:
AI 模块的 i18n 只有中文（`zh-CN/admin/ai.json` 和 `zh-CN/tenant/ai.json`），缺少对应的英文翻译文件。

**缺失文件**:
```
frontend/apps/web-antd/src/locales/langs/en-US/admin/ai.json      ❌ 缺失
frontend/apps/web-antd/src/locales/langs/en-US/tenant/ai.json     ❌ 缺失
```

**现有文件**:
```
frontend/apps/web-antd/src/locales/langs/zh-CN/admin/ai.json      ✅ 存在
frontend/apps/web-antd/src/locales/langs/zh-CN/tenant/ai.json     ✅ 存在
```

**问题影响**:
- ❌ 切换英文语言时，AI 模块显示中文或 i18n key
- ❌ 不符合项目国际化规范
- ❌ 影响海外用户使用

**修复方案**:

创建 `frontend/apps/web-antd/src/locales/langs/en-US/admin/ai.json`:
```json
{
  "title": "AI Gateway Management",
  "provider": {
    "title": "Provider Management",
    "name": "Provider Name",
    "code": "Provider Code",
    "type": "Provider Type",
    "baseUrl": "API URL",
    "description": "Description",
    "icon": "Icon",
    "isActive": "Status",
    "sortOrder": "Sort Order",
    "modelCount": "Model Count",
    "config": "Configuration",
    "create": "Add Provider",
    "placeholder": {
      "searchName": "Search provider name",
      "inputName": "Enter provider name",
      "inputCode": "Enter provider code",
      "selectType": "Select provider type",
      "inputBaseUrl": "Enter API URL",
      "inputDescription": "Enter description"
    },
    "type_options": {
      "openai_compatible": "OpenAI Compatible",
      "anthropic": "Anthropic"
    },
    "messages": {
      "toggleSuccess": "Provider status updated"
    }
  },
  "model": {
    "title": "Model Management",
    "name": "Model Name",
    "code": "Model Code",
    "type": "Model Type",
    "providerId": "Provider",
    "providerName": "Provider",
    "contextWindow": "Context Window",
    "maxOutputTokens": "Max Output Tokens",
    "inputPrice": "Input Price ($/1K)",
    "outputPrice": "Output Price ($/1K)",
    "functionCalling": "Function Calling",
    "vision": "Vision",
    "streaming": "Streaming",
    "isActive": "Status",
    "fallbackModel": "Fallback Model",
    "create": "Add Model",
    "section": {
      "basic": "Basic Info",
      "pricing": "Pricing",
      "capability": "Capabilities",
      "failover": "Failover"
    },
    "placeholder": {
      "searchName": "Search model name",
      "inputName": "Enter model name",
      "inputCode": "Enter model code",
      "selectType": "Select model type",
      "selectProvider": "Select provider",
      "allProviders": "All Providers",
      "allTypes": "All Types",
      "inputContextWindow": "e.g. 128000",
      "inputMaxOutput": "e.g. 4096",
      "inputPrice": "e.g. 0.015",
      "selectFallback": "Select fallback model (optional)"
    },
    "type_options": {
      "chat": "Chat",
      "embedding": "Embedding",
      "image": "Image"
    }
  },
  "apiKey": {
    "title": "API Key Management",
    "name": "Key Name",
    "providerId": "Provider",
    "providerName": "Provider",
    "tenantId": "Tenant",
    "tenantName": "Tenant",
    "apiKey": "API Key",
    "keyPreview": "Key Preview",
    "isActive": "Status",
    "isAvailable": "Available",
    "usageLimit": "Usage Limit",
    "usageCount": "Used Count",
    "lastUsedAt": "Last Used",
    "expiresAt": "Expires At",
    "create": "Add API Key",
    "scope": {
      "platform": "Platform",
      "tenant": "Tenant"
    },
    "placeholder": {
      "searchName": "Search key name",
      "inputName": "Enter key name",
      "inputApiKey": "Enter API Key",
      "selectProvider": "Select provider",
      "selectTenant": "Select tenant (leave empty for platform)",
      "allProviders": "All Providers",
      "inputUsageLimit": "Leave empty for unlimited"
    },
    "messages": {
      "toggleSuccess": "API Key status updated"
    }
  },
  "callLog": {
    "title": "Call Logs",
    "requestType": "Request Type",
    "inputTokens": "Input Tokens",
    "outputTokens": "Output Tokens",
    "totalTokens": "Total Tokens",
    "cost": "Cost",
    "latency": "Latency (ms)",
    "status": "Status",
    "tenantName": "Tenant",
    "modelName": "Model",
    "providerName": "Provider",
    "userId": "User ID",
    "errorMessage": "Error Message",
    "createdAt": "Created At",
    "placeholder": {
      "allStatuses": "All Statuses",
      "allModels": "All Models"
    },
    "status_options": {
      "success": "Success",
      "failed": "Failed",
      "timeout": "Timeout"
    }
  },
  "health": {
    "title": "Health Monitoring",
    "providers": "providers",
    "refresh": "Refresh",
    "responseTime": "Response Time",
    "failures": "Consecutive Failures",
    "lastCheck": "Last Check",
    "noData": "No health check data",
    "status": {
      "healthy": "Healthy",
      "degraded": "Degraded",
      "unavailable": "Unavailable"
    }
  }
}
```

创建 `frontend/apps/web-antd/src/locales/langs/en-US/tenant/ai.json`:
```json
{
  "title": "AI Management",
  "model": {
    "title": "Available Models",
    "name": "Model Name",
    "code": "Model Code",
    "type": "Type",
    "providerName": "Provider",
    "contextWindow": "Context Window",
    "inputPrice": "Input Price ($/1K)",
    "outputPrice": "Output Price ($/1K)",
    "functionCalling": "Function Calling",
    "vision": "Vision",
    "streaming": "Streaming",
    "isActive": "Status",
    "placeholder": {
      "searchName": "Search model name",
      "allTypes": "All Types",
      "allProviders": "All Providers"
    },
    "type_options": {
      "chat": "Chat",
      "embedding": "Embedding",
      "image": "Image"
    },
    "capability": {
      "functionCalling": "Function Calling",
      "vision": "Vision",
      "streaming": "Streaming"
    }
  },
  "apiKey": {
    "title": "API Key Management",
    "name": "Key Name",
    "providerId": "Provider",
    "providerName": "Provider",
    "apiKey": "API Key",
    "keyPreview": "Key Preview",
    "isActive": "Status",
    "isAvailable": "Available",
    "usageCount": "Usage Count",
    "lastUsedAt": "Last Used",
    "create": "Add API Key",
    "confirmDelete": "Are you sure to delete this API Key?",
    "placeholder": {
      "inputName": "Enter key name",
      "inputApiKey": "Enter API Key",
      "selectProvider": "Select provider"
    },
    "messages": {
      "createSuccess": "API Key created successfully",
      "deleteSuccess": "API Key deleted"
    }
  },
  "usage": {
    "title": "Usage Statistics",
    "summary": {
      "totalTokens": "Total Tokens",
      "totalCost": "Total Cost",
      "totalCalls": "Total Calls",
      "successRate": "Success Rate"
    },
    "chart": {
      "dailyTrend": "Daily Usage Trend",
      "modelDistribution": "Model Usage Distribution",
      "tokens": "Tokens",
      "cost": "Cost ($)",
      "calls": "Calls"
    },
    "dateRange": "Date Range",
    "thisMonth": "This Month",
    "last7Days": "Last 7 Days",
    "last30Days": "Last 30 Days"
  },
  "callLog": {
    "title": "Call Logs",
    "requestType": "Request Type",
    "inputTokens": "Input Tokens",
    "outputTokens": "Output Tokens",
    "totalTokens": "Total Tokens",
    "cost": "Cost",
    "latency": "Latency (ms)",
    "status": "Status",
    "modelName": "Model",
    "providerName": "Provider",
    "createdAt": "Created At",
    "errorMessage": "Error Message",
    "requestData": "Request Data",
    "responseData": "Response Data",
    "viewDetail": "View Detail",
    "detailTitle": "Call Log Detail",
    "placeholder": {
      "allStatuses": "All Statuses",
      "allModels": "All Models"
    },
    "status_options": {
      "success": "Success",
      "failed": "Failed",
      "timeout": "Timeout"
    }
  }
}
```

---

### 2.2 🔴 菜单未归纳分组

**问题描述**:
AI 相关的菜单项都是独立的一级菜单（`hideInMenu: true`），没有归纳到一个"AI 网关"或"AI 管理"的分组下。

**当前路由配置**（`admin/index.ts`）:
```typescript
// 每个都是独立的一级菜单，hideInMenu: true
{
  name: 'AdminAIProviders',
  path: 'ai/providers',
  meta: { hideInMenu: true, title: $t('admin.ai.provider.title') },
},
{
  name: 'AdminAIModels',
  path: 'ai/models',
  meta: { hideInMenu: true, title: $t('admin.ai.model.title') },
},
// ... 还有 3 个
```

**问题影响**:
- ❌ 用户无法在侧边栏看到 AI 相关菜单入口（因为 `hideInMenu: true`）
- ❌ 菜单结构混乱，AI 功能分散
- ❌ 不符合项目其他模块的菜单组织方式（如"系统管理"下有多个子菜单）

**修复方案**:

修改 `frontend/apps/web-antd/src/router/routes/admin/index.ts`:

```typescript
// 添加 AI 网关父菜单和子菜单结构
{
  name: 'AdminAIGateway',
  path: 'ai',
  meta: {
    title: $t('admin.ai.title'),  // "AI 网关管理"
    icon: 'lucide:bot',
    order: 5,  // 调整顺序
  },
  children: [
    {
      name: 'AdminAIProviders',
      path: 'providers',
      component: () => import('#/views/admin/ai/providers/index.vue'),
      meta: {
        title: $t('admin.ai.provider.title'),  // "供应商管理"
        icon: 'lucide:cpu',
      },
    },
    {
      name: 'AdminAIModels',
      path: 'models',
      component: () => import('#/views/admin/ai/models/index.vue'),
      meta: {
        title: $t('admin.ai.model.title'),  // "模型管理"
        icon: 'lucide:brain',
      },
    },
    {
      name: 'AdminAIApiKeys',
      path: 'api-keys',
      component: () => import('#/views/admin/ai/api-keys/index.vue'),
      meta: {
        title: $t('admin.ai.apiKey.title'),  // "API Key 管理"
        icon: 'lucide:key',
      },
    },
    {
      name: 'AdminAICallLogs',
      path: 'call-logs',
      component: () => import('#/views/admin/ai/call-logs/index.vue'),
      meta: {
        title: $t('admin.ai.callLog.title'),  // "调用日志"
        icon: 'lucide:scroll-text',
      },
    },
    {
      name: 'AdminAIHealth',
      path: 'health',
      component: () => import('#/views/admin/ai/health/index.vue'),
      meta: {
        title: $t('admin.ai.health.title'),  // "健康状态监控"
        icon: 'lucide:heart-pulse',
      },
    },
  ],
},
```

同样修改 `tenant/index.ts`:

```typescript
{
  name: 'TenantAI',
  path: 'ai',
  meta: {
    title: $t('tenant.ai.title'),  // "AI 管理"
    icon: 'lucide:bot',
    order: 4,
  },
  children: [
    {
      name: 'TenantAIModels',
      path: 'config',
      component: () => import('#/views/tenant/ai/models/index.vue'),
      meta: {
        title: $t('tenant.ai.model.title'),  // "可用模型"
        icon: 'lucide:brain',
      },
    },
    {
      name: 'TenantAIApiKeys',
      path: 'api-keys',
      component: () => import('#/views/tenant/ai/api-keys/index.vue'),
      meta: {
        title: $t('tenant.ai.apiKey.title'),  // "API Key 管理"
        icon: 'lucide:key',
      },
    },
    {
      name: 'TenantAIUsage',
      path: 'usage',
      component: () => import('#/views/tenant/ai/usage/index.vue'),
      meta: {
        title: $t('tenant.ai.usage.title'),  // "用量统计"
        icon: 'lucide:bar-chart-3',
      },
    },
    {
      name: 'TenantAICallLogs',
      path: 'call-logs',
      component: () => import('#/views/tenant/ai/call-logs/index.vue'),
      meta: {
        title: $t('tenant.ai.callLog.title'),  // "调用日志"
        icon: 'lucide:scroll-text',
      },
    },
  ],
},
```

---

## 三、可选优化项

### 3.1 🟢 模型 Fallback 逻辑未充分利用

**问题描述**:
迁移文件 `005_add_model_fallback.py` 已为 `ai_models` 表添加 `fallback_model_id` 字段，但 `AIGateway` 中未实现自动故障转移逻辑。

**当前状态**:
- ✅ 字段已存在
- ❌ 故障时未自动切换到备用模型

**建议实现**:
在 `AIGateway._call_with_retry` 中，当主模型连续失败达到阈值时，检查并切换到 `fallback_model_id` 指定的备用模型。

---

## 四、修复优先级建议

| 优先级 | 问题 | 原因 |
|--------|------|------|
| P0 | Repository 继承错误（1.1, 1.2） | 安全风险 - 租户数据隔离失效 |
| P1 | 缺少英文翻译（2.1） | 功能完整性 - 国际化缺失 |
| P1 | 菜单未分组（2.2） | 用户体验 - 无法导航到功能 |
| P2 | Service 继承问题（1.3） | 代码规范 - 一致性 |
| P3 | Fallback 逻辑（3.1） | 功能增强 - 非阻塞 |

---

## 五、验证检查清单

修复完成后，请验证以下项目：

- [ ] `AICallLogRepository` 继承 `TenantRepository[AICallLog]`
- [ ] `UsageStatRepository` 移到 `repositories/ai/` 并继承 `TenantRepository`
- [ ] `UsageStatRepository` 从 `metering_service.py` 中移除
- [ ] 英文翻译文件 `en-US/admin/ai.json` 存在且完整
- [ ] 英文翻译文件 `en-US/tenant/ai.json` 存在且完整
- [ ] 管理端侧边栏显示"AI 网关管理"分组，包含 5 个子菜单
- [ ] 租户端侧边栏显示"AI 管理"分组，包含 4 个子菜单
- [ ] 切换英文语言后，AI 模块所有文本正常显示英文
- [ ] 租户 A 无法看到租户 B 的调用日志（隔离验证）
