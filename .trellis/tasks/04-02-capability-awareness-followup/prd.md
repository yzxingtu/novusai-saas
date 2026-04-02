# Capability Awareness Validation And Follow-up

## Purpose

收敛 LLM 动态能力感知功能上线前的剩余工作，确保真实环境验证、性能观察、问题清单与后续优化路径都被记录在 Trellis 工作流中。

## Current State

已完成:

- 动态能力感知核心代码实现
- 单元测试、集成测试与 Ruff 校验
- 本地运行态 prompt 注入验证
- 真实接口基础验证

已确认:

- 技能能力感知可在真实对话中触发 `data_query`
- 知识库能力感知可在真实对话中使用已绑定知识库
- 配置关闭与简洁模式均生效

待跟进:

- 组合能力场景下的 planner / tool routing 偏差
- 更系统化的性能评估
- 发布前监控与灰度准备

## Findings

### Finding 1: `AITablePolicyOverride` 不是单纯残留导入

审计报告将其标记为残留代码，但当前代码扫描显示它仍被以下路径真实使用:

- `backend/app/ai/data_intelligence/schema_provider.py`
- `backend/app/ai/tools/executors/crud_executor.py`
- `backend/app/repositories/ai/table_policy_override_repository.py`
- `backend/app/models/ai/table_policy.py`

因此现阶段不应直接删除相关 `__init__.py` 导出，除非同步完成整条覆盖策略链的退役。

### Finding 2: 组合能力请求存在误路由 (已修复)

真实接口验证表明:

- “数据 + 知识库”混合请求在自然表述下可能误判为 `web_research`
- 某些请求会异常调用 `get_page_context`
- 明确要求”不要联网”时，模型可以正确走 `data_query + KB`

**状态**: 已修复并验证通过

### Finding 3: 对话 618 流式响应中断问题

测试能力感知功能时发现的上游 API 故障处理问题:

- 对话 618 只有用户输入，没有 AI 回复
- 日志显示 Responses API 返回 502，fallback 到 chat.completions
- Fallback 后流式响应中断，未被正确处理
- 调用日志 1071 是内部记忆提取调用，不是主对话调用

**根因**: Responses API fallback 逻辑不完整，流式响应异常未捕获

**影响**: 当上游 API 故障时，用户看不到任何响应或错误提示

**状态**: 已诊断，待修复 (见 `.trellis/tasks/04-02-conversation-618-diagnosis/`)

## Goals

### Goal 1: 完成真实环境验证闭环

- 保留并整理真实验证结果
- 输出可追踪的 E2E 报告

### Goal 2: 明确上线前阻塞项

- 区分“能力感知功能缺陷”和“现有 planner/router 偏差”
- 避免误删仍在使用的旧模型/仓储

### Goal 3: 为下一步优化建立落地路径

- 后续优先修复组合能力路由问题
- 再推进性能评估与发布准备

## Acceptance Criteria

- [x] Trellis 任务已创建
- [x] 本任务 PRD 已补齐
- [x] 真实环境验证结果已落文档
- [x] `AITablePolicyOverride` 使用现状已重新确认
- [x] 组合能力场景优化方案已实施并验证
- [ ] 对话 618 流式响应中断问题已修复
- [ ] 性能评估形成稳定结论
- [ ] 灰度发布前检查项补齐

## Output

- E2E 报告:
  - `docs/capability-awareness-e2e-report-20260402.md`
- 审计报告:
  - `docs/capability-awareness-audit-report.md` (初始审计，部分结论已修正)
  - `docs/capability-awareness-final-audit-20260402.md` (最终审计，包含组合路由修复验收)
- 修复方案:
  - `docs/capability-awareness-combined-routing-fix.md` (组合能力路由修复方案)

## Status

**当前状态**: 组合能力路由修复已完成并验证

**已完成**:
- ✅ 核心能力感知功能实现
- ✅ 组合能力路由修复
- ✅ 单元测试 (22 passed)
- ✅ 集成测试 (5 passed)
- ✅ 真实环境端到端验证
- ✅ 代码质量检查 (Ruff passed)

**待完成**:
- ⏳ 性能评估收敛 (需要更大样本)
- ⏳ 知识库绑定接口一致性排查
- ⏳ 灰度发布准备

## Next Steps

建议按以下顺序推进:

1. **对话 618 流式响应中断修复** (优先级: 高, 预计 5-8 小时)
   - 修复 Responses API fallback 逻辑
   - 增强调用日志记录
   - 增强错误处理和用户反馈
   - 详见: `.trellis/tasks/04-02-conversation-618-diagnosis/`

2. **性能评估收敛** (优先级: 中, 预计 2-3 小时)
   - 编写性能测试脚本
   - 执行至少 10 轮复测
   - 形成稳定结论

3. **知识库绑定接口排查** (优先级: 中, 预计 1-2 小时)
   - 复现并修复偶发不一致问题

4. **灰度发布准备** (优先级: 高, 预计 2-3 小时)
   - 制定发布计划
   - 准备监控和回滚方案

