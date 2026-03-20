# 多模型路由规范（M264）

> 智能路由根据对话复杂度、附件类型和 Token 数量自动为每次对话选择最合适的 AI 模型，平衡性能与成本。

---

## 一、模型 Tier（级别）

### 枚举定义

```python
class ModelTierEnum(LabeledStrEnum):
    FAST    = "fast"     # 快速型 — 低延迟低成本，适合简单问答
    STANDARD= "standard" # 标准型 — 均衡，适合多数场景
    PREMIUM = "premium"  # 高级型 — 最强能力，适合复杂推理/代码/长上下文
```

- 文件位置：`backend/app/enums/ai.py`
- DB 字段：`ai_models.tier`（新增，`nullable=True`，默认 `None`）

### Tier 分配原则

| 模型特征 | 推荐 Tier |
|---------|-----------|
| GPT-4o mini / Claude Haiku / Gemini Flash | `fast` |
| GPT-4o / Claude Sonnet / Gemini Pro | `standard` |
| o1 / Claude Opus / Gemini Ultra / 长上下文旗舰 | `premium` |

**配置路径（管理端）：** 管理端 → AI → 模型管理 → 编辑模型 → 模型级别（Tier）

---

## 二、ModelRouter 路由引擎

**文件：** `backend/app/ai/routing/router.py`

### 路由优先级（从高到低）

| 优先级 | 条件 | 结果 |
|-------|------|------|
| 1 | `enable_routing=False` | 直接返回 agent 原始 model（向后兼容） |
| 2 | 有图片附件 | 路由到 Vision 模型（优先显式配置的 `vision_model_id`） |
| 3 | Token 超过 `long_context_threshold` | 路由到长上下文模型 |
| 4 | ComplexityClassifier 评分 | 按 tier 查询 DB 模型（同 provider 优先 + 价格 ASC） |
| 5 | Provider 健康检查 | 不健康则降 tier |
| 6 | 兜底 | 始终返回 agent.model，**永不抛出异常** |

### `routing_config` JSON 字段（存于 Agent.routing_config）

| 字段 | 类型 | 说明 |
|------|------|------|
| `enable_routing` | bool | 是否启用智能路由（默认 false） |
| `max_tier` | str \| null | 成本上限（`fast`/`standard`/`premium`） |
| `vision_model_id` | int \| null | Vision 专用模型 ID |
| `long_context_model_id` | int \| null | 长上下文专用模型 ID |
| `long_context_threshold` | int | Token 阈值，超过后切换长上下文模型（默认 32000） |

### RouteResult 数据类

```python
@dataclass
class RouteResult:
    provider_code: str
    model_code: str
    model_id: int
    tier: str | None
    reason: str          # 路由原因（见下表）
    is_overridden: bool  # True=路由覆写了 agent.model，False=使用原始模型
```

### `reason` 值说明

| reason | 含义 |
|--------|------|
| `routing_disabled` | 路由未启用 |
| `vision:explicit_config` | Vision 显式配置触发 |
| `vision:tier_fallback` | Vision tier 降级触发 |
| `long_context:explicit_config` | 长上下文显式配置触发 |
| `long_context:tier_fallback` | 长上下文 tier 降级触发 |
| `complexity:simple` | 复杂度评分 → 简单 |
| `complexity:medium` | 复杂度评分 → 中等 |
| `complexity:complex` | 复杂度评分 → 复杂 |
| `no_tier_model_found` | 找不到合适 tier 模型，已兜底 |
| `exception: ...` | 路由异常，已兜底 |

---

## 三、ComplexityClassifier 评分规则

**文件：** `backend/app/ai/routing/complexity_classifier.py`

### 评分项

| 条件 | 加分 |
|------|------|
| 消息轮数 > 10 | +2 |
| 消息轮数 > 20 | 额外 +1 |
| 最新用户消息 > 500 字符 | +1 |
| 含高复杂度关键词（分析/推理/代码/analyze/reasoning/code...） | +2 |
| 含中复杂度关键词（综合/评估/数学/synthesize/evaluate/math...） | +1 |
| 工具数量 > 5 | +1 |
| 有图片附件 | 至少升为 MEDIUM |

### 分级

| 分数 | 级别 | 优先 Tier |
|------|------|-----------|
| 0–1 | SIMPLE | fast → standard → premium |
| 2–3 | MEDIUM | standard → premium → fast |
| ≥4 | COMPLEX | premium → standard → fast |

---

## 四、Engine 集成

### `_prepare_execution`（base.py）

```python
route_result = await ModelRouter(self.db).route(agent, request, estimated_tokens)
```

- `request.attachments`（列表，非空则 `has_attachments=True`）
- `estimated_tokens`：通过 `TokenCounter.count_messages_tokens` 估算

### `_call_llm` / `_stream_llm_chunks` Vision 过滤规则

```python
# is_vision 必须是 bool，不能是 None
is_vision: bool = "vision" in (route_result.reason or "")
# is_vision=False → 过滤消息中的 image 附件（避免发给非 Vision API）
if is_vision is False:
    ...filter image attachments...
```

### `_handle_tool_calls` 模型一致性

工具调用循环内的所有 `_call_llm` 均传入相同 `route_result`，确保多轮工具调用使用同一模型。

---

## 五、前端配置（智能路由 Tab）

### 路径
- **管理端**：管理端 → AI → 智能体 → 详情 → 「智能路由」Tab
- **企业端**：企业端 → AI → 智能体 → 详情 → 「智能路由」Tab

### 配置项组件

| 配置项 | 组件 | 说明 |
|--------|------|------|
| 启用智能路由 | Switch | `routing_config.enable_routing` |
| 成本上限 | Select（fast/standard/premium/不限制） | `routing_config.max_tier` |
| Vision 专用模型 | Select（Vision 模型列表） | `routing_config.vision_model_id` |
| 长上下文模型 | Select（模型列表） | `routing_config.long_context_model_id` |
| 长上下文触发阈值 | InputNumber（tokens） | `routing_config.long_context_threshold` |

**模型列表加载过滤器：**
```
GET /admin/ai/models?filter[type][eq]=chat&filter[is_active][eq]=true
GET /admin/ai/models?filter[type][eq]=chat&filter[is_active][eq]=true&filter[supports_vision][eq]=true
```

---

## 六、AIModel.__filterable__ 必须包含的能力字段

```python
__filterable__ = {
    ...
    "supports_vision": "supports_vision",
    "supports_function_calling": "supports_function_calling",
    "supports_streaming": "supports_streaming",
    "tier": "tier",
}
```

---

## 七、CallLog 路由记录

新增字段（`ai_call_logs` 表）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `routed_model_id` | Integer FK → ai_models | 路由选出的模型 ID |
| `route_reason` | String(200) | 路由原因（`reason` 值） |

**管理端展示**：管理端 → AI → 调用日志 → 「路由原因」列

---

## 八、已知限制

| 限制 | 说明 |
|------|------|
| 配额/限流按 `agent.model` 计算 | `_stream_llm_chunks` 路由覆写时，限流仍按原始模型计算，V1 接受此限制 |
| `_route_for_long_context` fallback | 只查 PREMIUM tier，不尝试其他 tier |
| task.py 不参与路由 | 任务引擎不调用 `_prepare_execution`，不使用路由 |
