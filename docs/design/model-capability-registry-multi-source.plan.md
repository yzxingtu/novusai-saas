---
name: 模型能力注册表多源同步
overview: 基于 LiteLLM 主数据和 LLMRing 补充数据构建统一模型能力注册表，写入 Redis（ai:litellm:registry），并与现有 model_capability_lookup 语义严格对齐。
todos:
  - id: constants
    content: 在 scheduled.py 增加常量 LLMRING_REGISTRY_BASE、LLMRING_PROVIDERS、REQUEST_TIMEOUT
    status: completed
  - id: helpers
    content: 实现 _find_registry_key_for_model_id、_is_valid_litellm_entry、_normalize_llmring_entry、_merge_entry_fill_empty、_build_registry_from_litellm、_merge_llmring_into_registry
    status: completed
  - id: sync_task
    content: 将 sync_litellm_registry 改为多源拉取 + 查重合并 + 写 Redis
    status: completed
  - id: verify
    content: 确认定时任务仍为每日 4:00，cron 不变
    status: completed
  - id: optional_lookup
    content: 可选 在 model_capability_lookup._find_entry 中扩展 common_prefixes
    status: completed
isProject: false
---

# 模型能力注册表多源同步方案（修订版）

目标：在不修改下游读取逻辑的前提下，将 LiteLLM 与 LLMRing 多源能力数据合并写入 Redis，并保证字段语义、去重行为、容错策略可预测。

---

## 1. 现状与修订原则

### 1.1 当前代码现状（基线）

- 当前仅有 LiteLLM 同步任务，位于 `backend/app/tasks/scheduled.py` 的 `sync_litellm_registry`。
- 下游读取逻辑位于 `backend/app/services/ai/model_capability_lookup.py`，核心行为：
  - `_find_entry` 使用「精确命中 -> 常见前缀 -> 后缀匹配」。
  - `_extract_capabilities` 会读取 `supports_vision/audio/video/function_calling`，并将 `supports_streaming` 固定为 `True`。
  - mode 映射：`chat`/`completion` -> `chat`，`embedding` -> `embedding`，`image_generation` -> `image`。

### 1.2 修订原则

- 文档约定必须与上述代码语义一致，不引入“看似支持、实际未生效”的字段承诺。
- 对多源去重策略给出默认方案与风险边界，避免跨 provider 的误合并。
- 对异常处理明确“继续/失败”的分界，便于任务稳定运行。

---

## 2. 数据源定义

### 2.1 源 1：LiteLLM（主源）

- URL1（优先）: `https://cdn.jsdelivr.net/gh/BerriAI/litellm@main/model_prices_and_context_window.json`
- URL2（回退）: `https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json`
- 格式：JSON 对象，key 为模型 key（如 `dashscope/qwen-plus`）
- 特殊项：`sample_spec` 必须排除

### 2.2 源 2：LLMRing（补充源）

- URL 模板：`https://llmring.github.io/registry/{provider}/models.json`（jsdelivr 实测 403，改用官方 GitHub Pages）
- 默认 providers：`openai`、`anthropic`、`google`
- 格式：`{"provider": "...", "models": {"openai:gpt-4.1": {...}}}`
- key 归一化：`openai:gpt-4.1` -> `openai/gpt-4.1`（仅替换第一个冒号）

---

## 3. 字段映射与语义对齐

LLMRing 条目归一化为 LiteLLM 风格 entry，供下游 `_extract_capabilities` 直接消费。

### 3.1 数值字段

- `max_input_tokens` <- `max_input_tokens`（可转 int 才写入）
- `max_output_tokens` <- `max_output_tokens`（可转 int 才写入）
- `input_cost_per_token` <- `dollars_per_million_tokens_input / 1_000_000`（可转 float 才写入）
- `output_cost_per_token` <- `dollars_per_million_tokens_output / 1_000_000`（可转 float 才写入）

### 3.2 模型类型字段

- `mode`：LLMRing 无该字段时，默认写 `"chat"`。
- 说明：下游最终类型由 `_normalize_mode` 决定（`completion` 会被视为 `chat`）。

### 3.3 布尔字段（关键修订）

禁止使用 `bool(raw_value)` 直接转换，避免 `"false"` 被转成 `True`。

推荐规则：
- 若值本身是 `bool`，直接使用。
- 若值是字符串，先 `strip().lower()`，仅 `"true"/"1"/"yes"` 视为 `True`，`"false"/"0"/"no"` 视为 `False`。
- 其他类型或无法解析时不写入该字段。

涉及字段：`supports_vision`、`supports_function_calling`、`supports_streaming`。

### 3.4 与下游 lookup 的一致性说明

- 当前下游 `_extract_capabilities` 将 `supports_streaming` 固定为 `True`，因此注册表中的 `supports_streaming` 目前不影响返回值。
- 本方案仍允许写入 `supports_streaming`，作为前向兼容字段，但需在文档中明确“当前 lookup 不消费该值”。

---

## 4. 去重与合并策略

同一模型在多源中可能有多 key（如 `gpt-4o` / `openai/gpt-4o`）。

### 4.1 默认策略（推荐）

- 先构建 LiteLLM registry（主源优先）。
- 合并 LLMRing 时按以下顺序：
  1. `reg_key` 存在：合并填空。
  2. 不存在时，查找同 `model_id` 的已有 key（`key == model_id` 或 `key.endswith("/" + model_id)`）：
     - 找到则合并填空，不新增 key。
     - 找不到才新增 `reg_key`。
- 合并原则：只填空位（`None` 或空字符串），不覆盖主源已有值。

### 4.2 风险边界（必须保留）

- 按 `model_id` 去重存在跨 provider 误合并风险（如 `openai/x` 与 `other/x`）。
- 默认建议：
  - 对 `openai`/`anthropic`/`google` 三个 provider 采用当前 `model_id` 去重策略；
  - 若后续扩展 provider，优先评估是否切换为“仅同 reg_key 去重”的保守模式。

---

## 5. 实现要点（scheduled.py）

以下为实现约束，不要求逐字复制。

### 5.1 常量

在 `backend/app/tasks/scheduled.py` 新增：

```python
LLMRING_REGISTRY_BASE = "https://cdn.jsdelivr.net/gh/llmring/registry@main"
LLMRING_PROVIDERS = ["openai", "anthropic", "google"]
REQUEST_TIMEOUT = 30
```

### 5.2 helper 约束

- `_is_valid_litellm_entry`：过滤 `sample_spec`，且 entry 必须为非空 dict。
- `_normalize_llmring_entry`：完成类型安全转换（含布尔显式解析）。
- `_merge_entry_fill_empty`：只填空，不覆盖已有非空值。
- `_find_registry_key_for_model_id`：按 `model_id` 在现有 registry 中查找可复用 key。
- `_build_registry_from_litellm`：构建主 registry，返回主源有效 key 数。
- `_merge_llmring_into_registry`：合并补充源，返回新增 key 数。

说明：若 helper 入参未被使用（如 `provider`），应移除该入参，避免误导。

### 5.3 任务流程

`sync_litellm_registry` 改造后的流程：

1. 按 `LITELLM_REGISTRY_URLS` 依次拉取 LiteLLM，要求返回 dict 且 `len >= 10`，否则尝试下一个 URL。
2. 所有 LiteLLM URL 均失败时：抛异常并结束任务，不写 Redis。
3. LiteLLM 成功后，构建 `registry = {}` 并写入主源条目。
4. 遍历 `LLMRING_PROVIDERS` 拉取 provider 数据：
   - 失败（网络、超时、非 2xx、JSON 异常、结构不合法）仅 `warning` 并跳过该 provider；
   - 成功则合并入 registry。
5. 写 Redis：`setex(LITELLM_REDIS_KEY, LITELLM_REDIS_TTL, json.dumps(registry, ensure_ascii=False))`。
6. 返回结构建议包含：`source`、`model_count`、`litellm_keys`、`llmring_added_keys`。

---

## 6. 与 model_capability_lookup 的衔接

- Redis 数据结构保持 `dict[key, entry]` 不变，下游无须改造即可读取。
- `_find_entry` 的精确/前缀/后缀匹配机制仍可工作。
- 若需要提高命中率，可在 `common_prefixes` 增加：
  - `dashscope/`
  - `siliconflow/`
  - `minimax/`
  - `kimi/`

---

## 7. 错误处理与日志口径

- LiteLLM 全失败：任务失败并抛错（保持与当前行为一致）。
- LLMRing 单 provider 失败：任务继续，记录 warning（需包含 provider 与错误信息）。
- Redis 写入失败：任务失败并抛错（不吞异常）。
- 返回 JSON 结构异常：
  - LiteLLM：视为该 URL 无效，继续尝试下一个 URL；
  - LLMRing：warning 后跳过该 provider。

---

## 8. 实施检查清单

- [ ] 在 `scheduled.py` 增加 `LLMRING_REGISTRY_BASE`、`LLMRING_PROVIDERS`、`REQUEST_TIMEOUT`。
- [ ] 实现并接入 helper：过滤、归一化、填空合并、按 model_id 查重。
- [ ] 将 `sync_litellm_registry` 改造为“LiteLLM 主源 + LLMRing 补充”流程。
- [ ] 保持 cron 为每日 4:00，不改调度表达式。
- [ ] 可选：扩展 `model_capability_lookup._find_entry` 的 `common_prefixes`。

---

## 9. 验收样例（新增）

### 9.1 功能验收

- 用仅 LiteLLM 数据执行一次任务，确认可写入 Redis 且 `model_count > 0`。
- 模拟 LLMRing 一个 provider 失败，确认任务仍成功，日志有 warning。
- 模拟全部 LiteLLM URL 失败，确认任务失败并抛错。

### 9.2 去重验收

- 准备 `openai/gpt-4.1`（LiteLLM）与 `openai:gpt-4.1`（LLMRing）：
  - 最终仅保留一个 key。
  - 已有字段不被覆盖，缺失字段被补齐。

### 9.3 字段验收

- 布尔字段输入 `"false"` 时结果必须为 `False` 或字段缺失，不能为 `True`。
- 价格字段能正确换算到 per-token（百万分之一）。
- 下游 `lookup("gpt-4.1")` 可通过前缀或后缀命中对应 entry。

---

## 10. 已知风险与默认策略（新增）

- 风险：`model_id` 跨 provider 去重可能误合并同名不同模型。
- 默认策略：先按本方案落地（覆盖当前目标 provider），扩 provider 前复核去重规则。
- 保守替代：仅 `reg_key` 相同才合并，可完全规避跨 provider 误合并，但会增加重复 key 数量。
