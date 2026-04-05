# LLM Dynamic Capability Awareness E2E Report

日期: 2026-04-02  
环境: 本地开发环境 (`http://localhost:8000`, `http://localhost:5666`)  
执行人: Codex

## Summary

本次针对已实现的 LLM 动态能力感知功能完成了真实环境验证、配置开关验证与基础性能观察。

结论摘要:

- 技能能力感知: 通过
- 知识库能力感知: 通过
- 组合能力感知: 通过（已完成路由修复并复测）
- 配置关闭回退: 通过
- 简洁模式: 通过

## Test Target

测试对象:

- Agent: `admin/ai/agents/20` `数据分析助手`
- 运行态模型: `gpt-5.4-xhigh`
- 测试知识库: `知识库 ID 1 / 测试知识库`

说明:

- 为验证知识库场景，临时将 `知识库 ID 1` 绑定到 `Agent 20`。
- 验证结束后，运行态配置已恢复为默认值:
  - `enable_dynamic_capability_awareness = true`
  - `capability_description_style = detailed`
  - `max_capability_items_per_category = 20`

## Scenario Results

### Scenario 1: Skill Capability Awareness

请求:

```text
帮我查询有多少个用户
```

结果:

- 返回成功
- 模型主动调用了 `data_query`
- 未出现“无法访问数据库”类回复
- 最终回答为“当前共有 3 个用户”

关键证据:

- `tool_calls[*].function.name` 包含 `data_query`
- `context_diagnostics.tool_planner.family = data_ops`

结论: 通过

### Scenario 2: Knowledge Base Capability Awareness

请求:

```text
产品的主要功能有哪些？请优先使用你已绑定的知识库
```

结果:

- 返回成功
- 未调用外部工具
- 响应内容明确以“我先从已绑定知识库中检索”开头
- `rag_source_kinds` 为 `formal_kb`

结论: 通过

### Scenario 3: Combined Capability Awareness

初始验证阶段，请求 1:

```text
请查询最近一周创建的用户数量，并结合已绑定知识库告诉我产品主要功能
```

结果:

- 未得到最终自然语言回答
- 模型异常多次调用 `get_page_context`
- 最终 `message` 为空

初始验证阶段，请求 2:

```text
请统计最近7天创建的终端用户数量，再根据已绑定知识库概括产品主要功能
```

结果:

- 成功执行 `data_query`
- 后续又触发 `web_search` 的 `pending_consent`
- 没有优先停留在已绑定知识库范围内完成第二部分

初始验证阶段，请求 3:

```text
不要联网。请统计最近7天创建的终端用户数量，再只根据已绑定知识库概括产品主要功能
```

结果:

- 返回成功
- 实际调用了 `data_query`
- 最终回答同时包含数据统计结果和知识库概括
- `rag_source_kinds` 为 `formal_kb`
- 但 `context_diagnostics.tool_planner.family` 仍显示为 `web_research`

修复后复测:

请求 1:

```text
请查询最近一周创建的用户数量，并结合已绑定知识库告诉我产品主要功能
```

结果:

- 返回成功
- 调用了 `data_query`
- 使用了已绑定知识库，`rag_source_kinds = formal_kb`
- `context_diagnostics.tool_planner.family = data_ops`
- 得到完整自然语言回答

请求 2:

```text
请统计最近7天创建的终端用户数量，再根据已绑定知识库概括产品主要功能
```

结果:

- 返回成功
- 调用了 `data_query`
- 未再触发 `web_search` 或 `pending_consent`
- 使用了已绑定知识库，`rag_source_kinds = formal_kb`
- `context_diagnostics.tool_planner.family = data_ops`

请求 3:

```text
不要联网。请统计最近7天创建的终端用户数量，再只根据已绑定知识库概括产品主要功能
```

结果:

- 返回成功
- 调用了 `data_query`
- 使用了已绑定知识库，`rag_source_kinds = formal_kb`
- `context_diagnostics.tool_planner.family = data_ops`
- `reason = no_web_explicit_data`

结论:

- 组合能力路由问题已修复
- 数据 + 知识库组合场景可稳定工作

状态: 通过

### Scenario 4: Configuration Disabled

运行态配置:

```text
enable_dynamic_capability_awareness = false
capability_description_style = detailed
```

验证结果:

- 本地运行态装配确认 system prompt 中不包含 `[CAPABILITIES]`
- 真实聊天接口仍可正常调用 `data_query`
- 功能成功回退，不影响原有能力

Prompt 观察:

- 动态能力感知关闭后，`dynamic_capability_awareness_enabled = false`
- system prompt 长度由 `2481` 字符下降到 `1812` 字符

结论: 通过

### Scenario 5: Concise Mode

运行态配置:

```text
enable_dynamic_capability_awareness = true
capability_description_style = concise
```

验证结果:

- system prompt 中仍包含 `[CAPABILITIES]`
- 知识库描述由详细模式:
  - `测试知识库: 用于测试知识库全流程的示例知识库 (2 documents)`
- 变为简洁模式:
  - `测试知识库`
- 真实聊天接口仍正常调用 `data_query`

Prompt 观察:

- 详细模式 system prompt 长度: `2481`
- 简洁模式 system prompt 长度: `2449`
- 能力块长度由 `668` 字符下降到 `636` 字符

结论: 通过

## Runtime Prompt Verification

基于真实数据库和运行态装配链路，直接检查 `ConversationContextEngine.assemble()` 输出，确认:

- 开启时存在 `[CAPABILITIES]`
- 分类包含:
  - `skills`
  - `knowledge_bases`
- 关闭时 `[CAPABILITIES]` 消失
- 简洁模式下能力块内容缩短

## Performance Notes

### Prompt Size

同一问题、同一 agent 下的 system prompt 对比:

| Mode | System Prompt Chars | Capability Block Chars |
|------|---------------------|------------------------|
| disabled | 1812 | 0 |
| detailed | 2481 | 668 |
| concise | 2449 | 636 |

观察:

- 详细模式相对关闭模式增加 `669` 字符
- 简洁模式相对详细模式减少 `32` 字符

### API Call Samples

同一问题 `帮我查询有多少个用户` 的真实接口样本:

| Mode | Elapsed (ms) | Total Tokens | Tool Use |
|------|---------------|--------------|----------|
| disabled | 37626 | 16192 | data_query |
| detailed | 48457 | 16419 | data_query |
| concise | 28972 | 12109 | data_query |

观察:

- token 增量在 `disabled -> detailed` 这组样本中约 `+1.4%`
- 延迟样本波动较大，暂不足以得出稳定结论
- 真实延迟受上游 LLM 波动影响明显，建议后续用多轮均值再做正式结论

### Small-Sample Performance Rerun

对同一问题再次进行了每种模式 `2` 轮小样本复测。

| Mode | Avg Elapsed (ms) | Avg Total Tokens | Avg Engine Duration (ms) | Avg Tool Count |
|------|------------------|------------------|---------------------------|----------------|
| disabled | 32700.5 | 12236.5 | 32632.0 | 2.5 |
| detailed | 29131.5 | 10565.0 | 29068.0 | 2.0 |
| concise | 37109.0 | 12455.0 | 37044.5 | 2.5 |

观察:

- 小样本下 `detailed` 模式反而比 `disabled` 更稳定，说明当前延迟受模型随机性和工具轮次影响更大
- `concise` 模式并未稳定优于 `detailed`，同样说明响应时间不能仅由 prompt 长度解释
- 目前可以确认“能力感知没有带来明显灾难性性能退化”，但仍不能据此给出严格 SLA 结论
- 如果要形成正式发布指标，建议至少补 `10` 轮以上同条件复测，并固定 agent / query / knowledge base / interaction_mode

## Findings

### Positive Findings

- 动态能力感知已成功注入到真实运行态 system prompt
- 技能能力感知明显提升了模型主动调用 `data_query` 的稳定性
- 知识库能力感知在知识问答场景下工作正常
- 组合能力场景在路由修复后已可稳定完成
- 配置开关和简洁模式均生效

### Issues Found

1. 管理端 API 删除知识库绑定后，HTTP 列表结果一度表现出与数据库直查不一致的现象，建议后续排查缓存或读取路径

## Recommendation

建议在灰度发布前重点补两项:

1. 做多轮性能均值测试，收敛延迟与 token 波动
2. 排查知识库绑定列表接口与数据库直查的偶发不一致

## Final Status

- 核心能力感知功能: 可用
- 配置切换能力: 可用
- 真实环境基础闭环: 已验证
- 组合能力场景: 已修复并复测通过
- 当前剩余关注点: 性能评估结论收敛、知识库绑定列表接口一致性排查
> **历史说明（2026-04）**：本报告围绕已退役的 `data_query` / `data_intelligence` 能力采集，仅保留为历史验证记录。
