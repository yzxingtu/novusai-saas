# Ruff Lint Cleanup - Full Backend Codebase

## Purpose

清理 backend/app/ 下所有 163 条 ruff 违规，使 `ruff check app/` 零告警通过。

## Current State

`ruff check app/` 报告 163 条违规：
- 50x UP032: Use f-string instead of `format` call (auto-fixable)
- 32x UP037: Remove quotes from type annotation (auto-fixable)
- 22x I001: Import block un-sorted (auto-fixable)
- 9x E402: Module level import not at top of file
- 8x F541: f-string without placeholders (auto-fixable)
- 5x SIM105: suppressible-exception
- 4x SIM101: duplicate-isinstance-call
- 3x ARG002: unused-method-argument
- 3x B007: unused-loop-control-variable
- 3x B009: get-attr-with-constant (auto-fixable)
- 3x C416: unnecessary-comprehension
- 3x F401: unused-import (auto-fixable)
- 3x F601: multi-value-repeated-key-literal
- 3x F841: unused-variable
- 2x F811: redefined-while-unused
- 2x SIM109: compare-with-tuple
- 1x each: B039, C408, F402, SIM103

最多违规的文件：
- app/cli.py (37+12 条)
- app/models/org/tenant_org_node.py (10 条)
- app/models/org/admin_org_node.py (10 条)
- app/core/database.py (8 条)

## Goals

1. 运行 `ruff check --fix app/` 修复所有 auto-fixable 违规
2. 手动修复剩余 non-fixable 违规
3. 运行 `ruff format app/` 统一格式
4. 确保所有现有测试仍然通过
5. 最终 `ruff check app/` 零告警

## Implementation Plan

### Phase 1: Auto-fix
1. `ruff check --fix app/`
2. `ruff format app/`
3. 验证 diff 是否正确

### Phase 2: Manual fixes
1. E402: 分析 module-level import 顺序问题，按需调整
2. SIM105: 将 try/except/pass 改为 contextlib.suppress
3. SIM101: 合并重复 isinstance 调用
4. ARG002: 添加 _ 前缀或删除未使用参数
5. B007: 将未使用循环变量改为 _
6. C416: 简化不必要的列表推导
7. F601: 修复重复字典键
8. F841: 删除未使用变量
9. F811: 修复重复定义
10. SIM109: 用元组替代多次比较
11. 其他单个违规逐一修复

### Phase 3: Validation
1. `ruff check app/` → 0 violations
2. `pytest tests/ -x -q` → all tests pass
3. 确认无功能性变更

## Acceptance Criteria

- [ ] `ruff check app/` 输出 0 条违规
- [ ] 所有现有测试通过
- [ ] 无功能性变更（纯 lint 修复）
