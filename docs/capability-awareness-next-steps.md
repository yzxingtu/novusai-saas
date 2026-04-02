# LLM 动态能力感知 - 下一步任务（Trellis 流程）

## 当前状态

✅ **已完成**：
- 阶段一：核心能力描述构建器（description_builder.py）
- 阶段二：上下文引擎集成（engine.py, agent_kb_binding_service.py）
- 阶段三：工具感知优化（base.py）
- 单元测试和集成测试（36 条测试通过）
- 代码质量检查（ruff check 通过）
- 覆盖率验证（约 98%）

⚠️ **待处理**：
- 端到端测试（真实环境验证）
- 性能评估（Token 消耗、响应延迟）
- 代码提交（工作区有未提交改动需要处理）
- 文档更新
- 灰度发布准备

---

## 下一步任务规划（Trellis 流程）

### 里程碑 1：验证与优化（优先级：高）

#### 任务 1.1：工作区清理与代码提交准备
**目标**：处理工作区的未提交改动，准备干净的提交

**步骤**：
1. 运行 `git status` 查看所有未提交的改动
2. 将改动分类：
   - 本次功能相关的改动
   - 其他无关的改动（可能是之前的工作）
3. 决策：
   - 选项 A：先提交其他无关改动，再提交本次功能
   - 选项 B：使用 `git stash` 暂存无关改动，只提交本次功能
   - 选项 C：创建新分支，在新分支上提交本次功能
4. 执行选定的策略

**验收标准**：
- [ ] 工作区状态清晰
- [ ] 本次功能的改动已隔离
- [ ] 准备好进行增量提交

**预计时间**：30 分钟

**负责人**：开发者

---

#### 任务 1.2：增量代码提交
**目标**：将本次功能的改动拆分为多个有意义的提交

**提交计划**：

**Commit 1: 核心能力描述构建器**
```bash
git add backend/app/ai/capabilities/__init__.py
git add backend/app/ai/capabilities/description_builder.py
git add backend/tests/unit/ai/capabilities/test_description_builder.py
git commit -m "feat(ai): add CapabilityDescriptionBuilder for dynamic capability awareness

- Implement CapabilityDescription dataclass
- Implement CapabilityDescriptionBuilder with methods:
  - build_skill_descriptions: convert skills to natural language
  - build_knowledge_base_descriptions: convert KB bindings to descriptions
  - build_page_context_description: describe page context
  - build_memory_description: describe memory capabilities
  - format_as_system_prompt_block: format as system prompt
- Add comprehensive unit tests (98% coverage)
- Support detailed/concise styles and max items limit

Refs: docs/llm-dynamic-capability-awareness-solution.md"
```

**Commit 2: 租户配置扩展**
```bash
git add backend/app/configs/definitions/tenant/ai.py
git add backend/app/configs/definitions/tenant/capability_awareness_config.py
git add backend/app/locales/en/messages.json
git add backend/app/locales/zh_CN/messages.json
git add backend/tests/unit/configs/test_capability_awareness_config.py
git commit -m "feat(config): add tenant-level capability awareness configuration

- Add enable_dynamic_capability_awareness flag (default: true)
- Add capability_description_style (detailed/concise)
- Add max_capability_items_per_category limit
- Add i18n messages for config descriptions
- Add unit tests for config validation

Refs: docs/llm-dynamic-capability-awareness-solution.md"
```

**Commit 3: 知识库服务扩展**
```bash
git add backend/app/services/ai/agent_kb_binding_service.py
git add backend/tests/services/test_agent_kb_binding_service.py
git commit -m "feat(ai): add KB metadata query for capability descriptions

- Add get_agent_kb_bindings_with_metadata method
- Query KB name, description, document count
- Support platform KB merging
- Add integration tests

Refs: docs/llm-dynamic-capability-awareness-solution.md"
```

**Commit 4: 上下文引擎集成**
```bash
git add backend/app/ai/context/engine.py
git add backend/tests/integration/ai/test_context_engine_capabilities.py
git commit -m "feat(ai): integrate capability awareness into context engine

- Inject capability descriptions into system prompt
- Build descriptions for skills, KBs, page context, memory
- Respect tenant configuration (enable/disable, style)
- Add [CAPABILITIES] block to system prompt
- Add comprehensive integration tests

Refs: docs/llm-dynamic-capability-awareness-solution.md"
```

**Commit 5: 工具感知优化**
```bash
git add backend/app/ai/engine/base.py
git add backend/tests/services/test_conversation_engine_prepare_execution.py
git commit -m "refactor(ai): optimize tool awareness to avoid duplication

- Add skip_capability_summary parameter to _inject_tool_awareness
- Skip capability list when already injected by context engine
- Maintain backward compatibility
- Add tests for both modes

Refs: docs/llm-dynamic-capability-awareness-solution.md"
```

**Commit 6: 文档更新**
```bash
git add docs/llm-dynamic-capability-awareness-solution.md
git add docs/capability-awareness-integration-example.py
git add docs/capability-awareness-implementation-checklist.md
git add docs/capability-awareness-quick-overview.md
git add docs/ai-implementation-prompt.md
git commit -m "docs: add LLM dynamic capability awareness documentation

- Add complete solution design document
- Add integration examples
- Add implementation checklist
- Add quick overview and AI prompt

Refs: docs/llm-dynamic-capability-awareness-solution.md"
```

**验收标准**：
- [ ] 所有提交都有清晰的 commit message
- [ ] 每个提交都是独立的、可编译的
- [ ] 提交历史清晰易读

**预计时间**：1 小时

**负责人**：开发者

---

#### 任务 1.3：端到端测试（真实环境）
**目标**：在开发环境中验证功能是否正常工作

**测试场景**：

**场景 1：技能能力感知**
1. 创建测试 Agent，绑定 `data_query` 技能
2. 发起对话："帮我查询有多少个用户"
3. 检查日志，确认 system prompt 包含技能描述
4. 验证 LLM 是否主动调用 `data_query` 工具
5. 记录结果

**场景 2：知识库能力感知**
1. 创建测试 Agent，绑定知识库（如"产品文档库"）
2. 发起对话："产品的主要功能有哪些？"
3. 检查日志，确认 system prompt 包含知识库描述
4. 验证 LLM 是否主动查询知识库
5. 记录结果

**场景 3：组合能力感知**
1. 创建测试 Agent，同时绑定技能和知识库
2. 发起对话："查询最近一周创建的用户，并告诉我产品的使用指南"
3. 验证 LLM 是否同时使用技能和知识库
4. 记录结果

**场景 4：配置关闭测试**
1. 在租户配置中设置 `enable_dynamic_capability_awareness = False`
2. 发起对话
3. 验证 system prompt 中没有 [CAPABILITIES] 块
4. 验证功能回退到原有行为
5. 记录结果

**场景 5：简洁模式测试**
1. 设置 `capability_description_style = "concise"`
2. 发起对话
3. 验证能力描述更简洁
4. 记录 Token 消耗差异

**验收标准**：
- [ ] 所有场景测试通过
- [ ] LLM 能正确理解并使用能力
- [ ] 配置开关生效
- [ ] 没有破坏现有功能

**预计时间**：2 小时

**负责人**：开发者 + 测试

---

#### 任务 1.4：性能评估
**目标**：评估功能对性能的影响

**评估指标**：

**1. Token 消耗**
- 测试场景：相同的对话，分别在启用/禁用能力感知时进行
- 记录：
  - System prompt 长度（字符数）
  - 总 Token 消耗（input + output）
  - 增加量和增加比例
- 目标：Token 消耗增加 < 10%

**2. 响应延迟**
- 测试场景：相同的对话，分别在启用/禁用能力感知时进行
- 记录：
  - 首 Token 延迟（TTFT）
  - 总响应时间
  - 增加量和增加比例
- 目标：响应延迟增加 < 5%

**3. 能力描述长度**
- 统计不同场景下的能力描述长度：
  - 只有技能（1 个、5 个、10 个）
  - 只有知识库（1 个、5 个、10 个）
  - 技能 + 知识库
- 验证 `max_capability_items_per_category` 是否生效

**测试方法**：
```python
# 伪代码
import time

# 测试 Token 消耗
def test_token_consumption():
    # 禁用能力感知
    response_without = chat(agent, "帮我查询用户数量", capability_awareness=False)
    tokens_without = response_without.usage.total_tokens
    
    # 启用能力感知
    response_with = chat(agent, "帮我查询用户数量", capability_awareness=True)
    tokens_with = response_with.usage.total_tokens
    
    increase = (tokens_with - tokens_without) / tokens_without * 100
    print(f"Token 增加: {increase:.2f}%")
    assert increase < 10, "Token 消耗增加超过 10%"

# 测试响应延迟
def test_response_latency():
    # 禁用能力感知
    start = time.time()
    response_without = chat(agent, "帮我查询用户数量", capability_awareness=False)
    latency_without = time.time() - start
    
    # 启用能力感知
    start = time.time()
    response_with = chat(agent, "帮我查询用户数量", capability_awareness=True)
    latency_with = time.time() - start
    
    increase = (latency_with - latency_without) / latency_without * 100
    print(f"延迟增加: {increase:.2f}%")
    assert increase < 5, "响应延迟增加超过 5%"
```

**验收标准**：
- [ ] Token 消耗增加 < 10%
- [ ] 响应延迟增加 < 5%
- [ ] 能力描述长度在合理范围内
- [ ] 性能数据已记录并分析

**预计时间**：2 小时

**负责人**：开发者 + 性能工程师

---

#### 任务 1.5：效果验证
**目标**：验证功能是否达到预期效果

**验证指标**：

**1. 工具调用率**
- 准备 20 个测试问题（需要调用工具才能回答）
- 分别在启用/禁用能力感知时测试
- 统计工具调用次数
- 目标：工具调用率提升 > 30%

**2. "无法执行"回复率**
- 准备 20 个测试问题
- 统计 LLM 回复中包含"无法"、"不能"等否定词的次数
- 目标："无法执行"回复率下降 > 40%

**3. 知识库命中率**
- 准备 20 个需要查询知识库的问题
- 统计 RAG 检索被实际使用的次数
- 目标：知识库命中率提升 > 20%

**测试问题示例**：
```
# 需要调用工具的问题
1. 帮我查询有多少个用户
2. 创建一个新用户，名字叫张三
3. 更新用户 ID 123 的邮箱
4. 删除用户 ID 456
5. 查询最近一周创建的用户

# 需要查询知识库的问题
1. 产品的主要功能有哪些？
2. 如何配置 API 密钥？
3. 数据库备份策略是什么？
4. 系统支持哪些支付方式？
5. 如何处理用户投诉？
```

**验收标准**：
- [ ] 工具调用率提升 > 30%
- [ ] "无法执行"回复率下降 > 40%
- [ ] 知识库命中率提升 > 20%
- [ ] 效果数据已记录并分析

**预计时间**：3 小时

**负责人**：测试 + 产品

---

### 里程碑 2：优化与完善（优先级：中）

#### 任务 2.1：性能优化（如果需要）
**目标**：如果性能评估发现问题，进行优化

**可能的优化方向**：
1. **实现缓存**：
   - 使用 Redis 缓存能力描述
   - Key 格式：`capability_desc:agent:{agent_id}:v{version}`
   - 当技能或知识库绑定变更时，清除缓存

2. **优化查询**：
   - 批量查询知识库元数据
   - 添加数据库索引

3. **减少描述长度**：
   - 调整 `max_capability_items_per_category` 默认值
   - 优化描述格式，去除冗余信息

**验收标准**：
- [ ] 性能指标达到目标
- [ ] 优化不影响功能

**预计时间**：2-4 小时（视情况而定）

**负责人**：开发者

---

#### 任务 2.2：监控指标接入
**目标**：添加监控指标，持续跟踪效果

**指标定义**：
1. `ai.capability_awareness.enabled`：能力感知启用率
2. `ai.capability_awareness.token_increase`：Token 增加量
3. `ai.tool_call.rate`：工具调用率
4. `ai.negative_response.rate`："无法执行"回复率
5. `ai.knowledge_base.hit_rate`：知识库命中率

**实现方式**：
- 在 `ConversationContextEngine.assemble()` 中记录指标
- 在 `BaseEngine.execute()` 中记录工具调用
- 使用项目现有的监控系统（如 Prometheus）

**验收标准**：
- [ ] 监控指标已定义
- [ ] 监控指标已接入
- [ ] 可以在监控面板查看数据

**预计时间**：2 小时

**负责人**：开发者 + 运维

---

#### 任务 2.3：文档完善
**目标**：补充用户文档和运维文档

**文档清单**：

**1. 用户指南**（`docs/user-guide-capability-awareness.md`）
- 什么是动态能力感知
- 如何启用/禁用
- 如何配置（详细/简洁模式）
- 常见问题

**2. 运维指南**（`docs/ops-guide-capability-awareness.md`）
- 如何监控
- 如何排查问题
- 如何优化性能
- 回滚方案

**3. API 文档**（如果有新增 API）
- 端点说明
- 请求/响应格式
- 示例

**验收标准**：
- [ ] 文档已编写
- [ ] 文档已审核
- [ ] 文档已发布

**预计时间**：2 小时

**负责人**：技术写作 + 开发者

---

### 里程碑 3：发布准备（优先级：高）

#### 任务 3.1：灰度发布计划
**目标**：制定灰度发布策略

**发布阶段**：

**阶段 1：内部测试（1 天）**
- 范围：开发和测试团队
- 目标：发现明显问题
- 监控：密切关注所有指标

**阶段 2：小范围灰度（3 天）**
- 范围：10% 租户（选择活跃度较低的租户）
- 目标：验证稳定性
- 监控：每天检查指标

**阶段 3：中等范围灰度（3 天）**
- 范围：30% 租户
- 目标：验证效果
- 监控：收集用户反馈

**阶段 4：大范围灰度（3 天）**
- 范围：50% 租户
- 目标：最终验证
- 监控：准备全量发布

**阶段 5：全量发布**
- 范围：100% 租户
- 目标：正式上线
- 监控：持续监控 1 周

**回滚策略**：
- 如果发现严重问题，立即设置 `enable_dynamic_capability_awareness = False`
- 如果配置回滚无效，回滚代码
- 准备回滚脚本和操作手册

**验收标准**：
- [ ] 灰度发布计划已制定
- [ ] 回滚策略已准备
- [ ] 相关人员已知晓

**预计时间**：1 小时（制定计划）

**负责人**：产品 + 运维

---

#### 任务 3.2：发布前检查清单
**目标**：确保所有准备工作已完成

**检查清单**：
- [ ] 所有代码已提交并合并到主分支
- [ ] 所有测试通过（单元测试、集成测试、端到端测试）
- [ ] 性能评估通过
- [ ] 效果验证通过
- [ ] 文档已完善
- [ ] 监控指标已接入
- [ ] 灰度发布计划已制定
- [ ] 回滚方案已准备
- [ ] 相关团队已培训
- [ ] 发布公告已准备

**验收标准**：
- [ ] 所有检查项都已完成

**预计时间**：30 分钟

**负责人**：项目经理

---

#### 任务 3.3：执行灰度发布
**目标**：按计划执行灰度发布

**执行步骤**：
1. 内部测试（1 天）
2. 10% 灰度（3 天）
3. 30% 灰度（3 天）
4. 50% 灰度（3 天）
5. 100% 全量（持续监控）

**每个阶段的工作**：
- 更新配置，启用对应比例的租户
- 监控指标
- 收集反馈
- 修复问题（如果有）
- 决定是否继续下一阶段

**验收标准**：
- [ ] 灰度发布顺利完成
- [ ] 没有严重问题
- [ ] 用户反馈良好

**预计时间**：10 天

**负责人**：运维 + 产品

---

## 总体时间表

| 里程碑 | 任务 | 预计时间 | 依赖 |
|--------|------|----------|------|
| 里程碑 1 | 任务 1.1：工作区清理 | 0.5 小时 | - |
| 里程碑 1 | 任务 1.2：增量提交 | 1 小时 | 1.1 |
| 里程碑 1 | 任务 1.3：端到端测试 | 2 小时 | 1.2 |
| 里程碑 1 | 任务 1.4：性能评估 | 2 小时 | 1.3 |
| 里程碑 1 | 任务 1.5：效果验证 | 3 小时 | 1.3 |
| 里程碑 2 | 任务 2.1：性能优化 | 2-4 小时 | 1.4 |
| 里程碑 2 | 任务 2.2：监控接入 | 2 小时 | 1.5 |
| 里程碑 2 | 任务 2.3：文档完善 | 2 小时 | - |
| 里程碑 3 | 任务 3.1：灰度计划 | 1 小时 | 1.5, 2.2 |
| 里程碑 3 | 任务 3.2：发布检查 | 0.5 小时 | 所有前置任务 |
| 里程碑 3 | 任务 3.3：灰度发布 | 10 天 | 3.2 |

**总计**：约 2-3 天开发 + 10 天灰度发布

---

## 风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| 端到端测试发现问题 | 高 | 中 | 修复问题，重新测试 |
| 性能不达标 | 中 | 低 | 执行任务 2.1 优化 |
| 效果不达预期 | 高 | 低 | 分析原因，调整策略 |
| 灰度发布出现问题 | 高 | 低 | 立即回滚，修复后重新发布 |
| 工作区冲突 | 中 | 中 | 使用分支隔离，谨慎合并 |

---

## 下一步行动

**立即执行**：
1. 开始任务 1.1：工作区清理与代码提交准备
2. 与团队确认灰度发布计划
3. 准备端到端测试环境

**本周完成**：
- 里程碑 1 的所有任务
- 里程碑 2 的任务 2.2 和 2.3

**下周开始**：
- 里程碑 3：灰度发布

---

## 联系人

- **项目负责人**：待定
- **开发负责人**：待定
- **测试负责人**：待定
- **运维负责人**：待定
- **产品负责人**：待定
