# LLM 动态能力感知方案 - 实施检查清单

## 阶段一：核心能力描述构建器（优先级：高）

### 1.1 创建模块结构
- [x] 创建 `backend/app/ai/capabilities/__init__.py`
- [x] 创建 `backend/app/ai/capabilities/description_builder.py`
- [ ] 验证模块可以正常导入

### 1.2 实现 CapabilityDescriptionBuilder
- [x] 实现 `CapabilityDescription` 数据类
- [x] 实现 `CapabilityDescriptionBuilder` 类
- [x] 实现 `build_skill_descriptions()` 方法
- [x] 实现 `build_knowledge_base_descriptions()` 方法
- [x] 实现 `build_page_context_description()` 方法
- [x] 实现 `build_memory_description()` 方法
- [x] 实现 `format_as_system_prompt_block()` 方法
- [x] 实现辅助方法（`_determine_skill_family`, `_format_skill_family_title`, `_build_single_skill_description`）

### 1.3 单元测试
- [x] 创建 `backend/tests/unit/ai/capabilities/test_description_builder.py`
- [ ] 运行测试：`pytest backend/tests/unit/ai/capabilities/test_description_builder.py -v`
- [ ] 确保所有测试通过
- [ ] 检查代码覆盖率（目标：>90%）

### 1.4 代码审查
- [ ] 检查代码风格（运行 `ruff check backend/app/ai/capabilities/`）
- [ ] 检查类型注解（运行 `mypy backend/app/ai/capabilities/`）
- [ ] 代码审查：确保符合项目规范

---

## 阶段二：上下文引擎集成（优先级：高）

### 2.1 添加配置项
- [ ] 修改 `backend/app/configs/definitions/tenant/ai.py`
  - [ ] 添加 `enable_dynamic_capability_awareness: bool = True`
  - [ ] 添加 `capability_description_style: str = "detailed"`
  - [ ] 添加 `max_capability_items_per_category: int = 20`
- [ ] 运行数据库迁移（如果配置存储在数据库中）
- [ ] 验证配置可以正常读取

### 2.2 扩展 AgentKBBindingService
- [ ] 修改 `backend/app/services/ai/agent_kb_binding_service.py`
  - [ ] 添加 `get_agent_kb_bindings_with_metadata()` 方法
  - [ ] 实现知识库元数据查询（名称、描述、文档数量）
- [ ] 测试方法是否正常工作

### 2.3 修改 ConversationContextEngine
- [ ] 修改 `backend/app/ai/context/engine.py`
  - [ ] 导入 `CapabilityDescriptionBuilder`
  - [ ] 在 `assemble()` 方法中添加能力描述构建逻辑
  - [ ] 读取租户 AI 配置
  - [ ] 构建技能描述
  - [ ] 构建知识库描述
  - [ ] 构建页面上下文描述
  - [ ] 构建记忆能力描述
  - [ ] 格式化并注入到 `system_prompt_additions`
- [ ] 确保不影响现有功能

### 2.4 集成测试
- [ ] 创建 `backend/tests/integration/ai/test_context_engine_capabilities.py`
- [ ] 测试场景：
  - [ ] 只有技能，无知识库
  - [ ] 只有知识库，无技能
  - [ ] 技能 + 知识库
  - [ ] 技能 + 知识库 + 页面上下文
  - [ ] 技能 + 知识库 + 记忆
  - [ ] 配置关闭时，不注入能力描述
- [ ] 运行测试：`pytest backend/tests/integration/ai/test_context_engine_capabilities.py -v`
- [ ] 确保所有测试通过

### 2.5 端到端测试
- [ ] 启动开发环境
- [ ] 创建测试 Agent，绑定技能和知识库
- [ ] 发起对话，检查 system prompt 是否包含能力描述
- [ ] 验证 LLM 是否能正确理解并使用能力
- [ ] 测试不同配置选项（detailed / concise）

---

## 阶段三：工具感知优化（优先级：中）

### 3.1 修改 BaseEngine._inject_tool_awareness()
- [ ] 修改 `backend/app/ai/engine/base.py`
  - [ ] 添加 `skip_capability_summary: bool = False` 参数
  - [ ] 实现条件逻辑：
    - [ ] 如果 `skip_capability_summary=True`，只注入工具使用规则
    - [ ] 如果 `skip_capability_summary=False`，保持原有逻辑（向后兼容）
- [ ] 确保不破坏现有功能

### 3.2 调整调用点
- [ ] 在 `BaseEngine._prepare_execution()` 中：
  - [ ] 读取租户 AI 配置
  - [ ] 传入 `skip_capability_summary=ai_config.enable_dynamic_capability_awareness`
- [ ] 在其他调用点（如果有）做相同调整

### 3.3 测试
- [ ] 测试 `skip_capability_summary=True` 时，不重复注入能力列表
- [ ] 测试 `skip_capability_summary=False` 时，保持原有行为
- [ ] 确保向后兼容

---

## 阶段四：前端展示优化（优先级：低）

### 4.1 API 端点
- [ ] 创建 API 端点：`GET /api/tenant/agents/{agent_id}/capabilities`
  - [ ] 返回 Agent 的技能列表
  - [ ] 返回 Agent 的知识库列表
  - [ ] 返回能力描述（可选）
- [ ] 添加权限检查
- [ ] 编写 API 文档

### 4.2 前端 UI
- [ ] 在对话界面添加"当前能力"展示区域
  - [ ] 显示技能列表
  - [ ] 显示知识库列表
  - [ ] 可折叠/展开
- [ ] 添加能力变更提示
  - [ ] 当管理员修改技能或知识库绑定时，提示用户刷新对话

### 4.3 测试
- [ ] 测试 API 端点
- [ ] 测试前端 UI 显示
- [ ] 测试能力变更提示

---

## 阶段五：监控与优化（优先级：中）

### 5.1 添加监控指标
- [ ] 工具调用率统计
  - [ ] 记录每次对话的工具调用次数
  - [ ] 对比修改前后的数据
- [ ] "无法执行"回复率统计
  - [ ] 使用正则表达式检测否定回复
  - [ ] 记录到日志或数据库
- [ ] 知识库命中率统计
  - [ ] 记录 RAG 检索次数
  - [ ] 记录实际使用次数
- [ ] 用户满意度统计
  - [ ] 添加对话评分功能
  - [ ] 统计平均分

### 5.2 性能优化
- [ ] 实现能力描述缓存
  - [ ] 使用 Redis 缓存
  - [ ] Key 格式：`capability_desc:agent:{agent_id}:v{version}`
  - [ ] 当技能或知识库绑定变更时，清除缓存
- [ ] 优化知识库元数据查询
  - [ ] 添加数据库索引
  - [ ] 使用批量查询
- [ ] 监控 Token 消耗
  - [ ] 记录 system prompt 长度
  - [ ] 记录总 Token 消耗
  - [ ] 对比修改前后的数据

### 5.3 A/B 测试
- [ ] 设计 A/B 测试方案
  - [ ] A 组：启用动态能力感知
  - [ ] B 组：不启用（对照组）
- [ ] 收集数据（至少 1 周）
- [ ] 分析结果
- [ ] 决定是否全量上线

---

## 阶段六：文档与培训（优先级：低）

### 6.1 技术文档
- [x] 编写方案设计文档（`docs/llm-dynamic-capability-awareness-solution.md`）
- [x] 编写集成示例（`docs/capability-awareness-integration-example.py`）
- [ ] 编写 API 文档
- [ ] 更新架构图

### 6.2 用户文档
- [ ] 编写用户指南：如何配置动态能力感知
- [ ] 编写最佳实践：如何优化能力描述
- [ ] 编写故障排查指南

### 6.3 培训
- [ ] 培训开发团队
- [ ] 培训测试团队
- [ ] 培训运维团队

---

## 验收标准

### 功能验收
- [ ] LLM 能够在 system prompt 中看到技能列表
- [ ] LLM 能够在 system prompt 中看到知识库列表
- [ ] LLM 能够主动调用技能工具
- [ ] LLM 能够主动查询知识库
- [ ] 配置开关生效（可以启用/禁用）
- [ ] 不影响现有功能

### 性能验收
- [ ] Token 消耗增加 < 10%
- [ ] 响应延迟增加 < 5%
- [ ] 缓存命中率 > 80%

### 质量验收
- [ ] 单元测试覆盖率 > 90%
- [ ] 集成测试通过率 100%
- [ ] 代码审查通过
- [ ] 无严重 Bug

### 效果验收
- [ ] 工具调用率提升 > 30%
- [ ] "无法执行"回复率下降 > 40%
- [ ] 知识库命中率提升 > 20%
- [ ] 用户满意度提升 > 15%

---

## 回滚计划

如果出现问题，按以下步骤回滚：

1. **立即回滚**（< 5 分钟）
   - [ ] 在租户 AI 配置中设置 `enable_dynamic_capability_awareness = False`
   - [ ] 重启服务（如果需要）
   - [ ] 验证系统恢复正常

2. **代码回滚**（如果配置回滚无效）
   - [ ] 回滚 Git 提交
   - [ ] 重新部署
   - [ ] 验证系统恢复正常

3. **数据回滚**（如果有数据库变更）
   - [ ] 回滚数据库迁移
   - [ ] 恢复备份数据
   - [ ] 验证数据完整性

---

## 上线计划

### 灰度发布
1. **第一阶段**（10% 流量，1 天）
   - [ ] 选择 10% 租户启用
   - [ ] 监控指标
   - [ ] 收集反馈

2. **第二阶段**（30% 流量，3 天）
   - [ ] 扩大到 30% 租户
   - [ ] 继续监控
   - [ ] 修复问题

3. **第三阶段**（50% 流量，3 天）
   - [ ] 扩大到 50% 租户
   - [ ] 验证效果
   - [ ] 优化性能

4. **全量上线**（100% 流量）
   - [ ] 全量启用
   - [ ] 持续监控 1 周
   - [ ] 总结经验

---

## 后续优化方向

### 短期优化（1-2 周）
- [ ] 智能能力推荐：根据用户问题，动态推荐最相关的能力
- [ ] 能力使用统计：统计每个技能和知识库的实际使用频率
- [ ] 多语言支持：根据用户语言偏好，生成对应语言的能力描述

### 中期优化（1-2 月）
- [ ] 能力分组：将相关技能分组，提供更清晰的能力结构
- [ ] 能力推荐引擎：基于历史数据，推荐最有用的技能和知识库
- [ ] 能力热度排序：优先展示高频使用的能力

### 长期优化（3-6 月）
- [ ] 自适应能力描述：根据 LLM 的理解能力，动态调整描述详细程度
- [ ] 能力学习：根据 LLM 的使用反馈，优化能力描述
- [ ] 能力市场：允许用户分享和交换技能配置

---

## 负责人与时间表

| 阶段 | 负责人 | 预计时间 | 状态 |
|------|--------|----------|------|
| 阶段一：核心能力描述构建器 | 待定 | 2 天 | 进行中 |
| 阶段二：上下文引擎集成 | 待定 | 3 天 | 未开始 |
| 阶段三：工具感知优化 | 待定 | 1 天 | 未开始 |
| 阶段四：前端展示优化 | 待定 | 2 天 | 未开始 |
| 阶段五：监控与优化 | 待定 | 3 天 | 未开始 |
| 阶段六：文档与培训 | 待定 | 2 天 | 未开始 |
| **总计** | - | **13 天** | - |

---

## 风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| Token 消耗过大 | 高 | 中 | 限制每个类别的最大项数；使用简洁模式 |
| 性能下降 | 中 | 低 | 实现缓存；优化查询 |
| LLM 理解错误 | 高 | 低 | 优化描述格式；添加示例 |
| 配置复杂 | 低 | 中 | 提供默认配置；简化选项 |
| 向后兼容问题 | 高 | 低 | 保留原有逻辑；添加开关 |

---

## 联系人

- **技术负责人**：待定
- **产品负责人**：待定
- **测试负责人**：待定
- **运维负责人**：待定

---

## 附录

### 相关文档
- [方案设计文档](./llm-dynamic-capability-awareness-solution.md)
- [集成示例代码](./capability-awareness-integration-example.py)
- [单元测试代码](../backend/tests/unit/ai/capabilities/test_description_builder.py)

### 相关代码
- `backend/app/ai/capabilities/description_builder.py` - 能力描述构建器
- `backend/app/ai/context/engine.py` - 上下文引擎
- `backend/app/ai/engine/base.py` - 执行引擎基类
- `backend/app/services/ai/agent_kb_binding_service.py` - 知识库绑定服务

### 相关配置
- `backend/app/configs/definitions/tenant/ai.py` - AI 配置定义
