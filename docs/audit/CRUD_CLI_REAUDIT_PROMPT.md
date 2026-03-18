# CRUD 与 CLI 二次审计提示词（零遗漏版）

> 将本提示词提供给另一个 AI，对 NovusAI SaaS 项目进行**二次审计**。上次审计发现的问题已修复，本次审计必须**逐一验证修复结果**，并**全量扫描确保无新增遗漏**。要求：**不能出一点问题**。

---

## 一、审计目标

1. **验证修复**：逐项确认 `docs/audit/CRUD_CLI_AUDIT_REPORT.md` 中列出的 6 个问题已正确修复，无残留或引入新缺陷。
2. **全量复核**：按审计清单逐项检查，确保无遗漏、无推测、每项均有明确结论。
3. **运行验证**：执行 `pytest backend/tests/codegen -v` 及 `pytest backend/tests -v`（或抽样），报告通过/失败数量。
4. **输出报告**：结构化报告，问题必须含**文件:行号**，修复建议必须可执行。

---

## 二、强制验证清单（上次审计问题）

以下 6 项**必须逐条验证**，每项给出「已修复 / 未修复 / 部分修复」及佐证（文件路径 + 关键代码片段）：

| 序号 | 原问题 | 验证文件 | 验证要点 |
|------|--------|----------|----------|
| 1 | CodegenConfig 缺失 `__delete_deps__` | `backend/app/models/system/codegen_config.py` | 存在 `__delete_deps__ = [DeletionDep("CodegenConfigVersion", "config_id", DeletionStrategy.CASCADE_DELETE, ...)]` |
| 2 | codegen list_configs 分页用 getattr | `backend/app/api/admin/codegen.py` | 使用 `page=spec.page or 1`、`page_size=spec.size or 20`，无 `getattr(..., "page_size", ...)` |
| 3 | PresetSelectModal 中文字符串 | `frontend/.../codegen/modules/PresetSelectModal.vue` | 模板使用 `$t(card.labelKey)` 或 `$t(card.desc)`，无硬编码中文 |
| 4 | WysiwygFormView 中文字符串 | `frontend/.../codegen/modules/WysiwygFormView.vue` | getDictMockOptions、getMockRelationOptions、getMockTreeOptions、getMockCascaderOptions 使用 `$t(...)` |
| 5 | codegen generate 互斥/优先级 | `backend/app/cli.py` | docstring 或 --stdin help 含「stdin > config > id/resource」或等价说明 |
| 6 | license keygen 安全提示 | `backend/app/cli.py` | keygen 的 docstring 含「仅用于开发环境」或「dev only」或等价提示 |

**额外验证**：`deletion.model.codegen_config_version` 和 `common.dependency.model.codegen_config_version` 已存在于后端 `messages.json` 及前端 `common.json`。

---

## 三、全量审计范围（必须覆盖）

### 3.1 后端 Model 全量

- 遍历 `backend/app/models/` 下所有含 `relationship` 或 `ForeignKey` 的模型
- 检查：有子表 FK 引用的父模型是否声明 `__delete_deps__`
- 检查：`__filterable__`/`__sortable__` 与查询用法一致
- **输出**：列出所有 Model 文件及 `__delete_deps__` 声明状态（有/无/不适用）

### 3.2 后端分页参数全量

- grep 搜索 `page_size=` 和 `page=` 在 `backend/app/api/` 下的用法
- 规范：必须使用 `query.size` 或 `spec.size`，禁用 `query.page_size` 或 `getattr(..., "page_size", ...)`
- **输出**：每个分页端点的 `page_size` 来源（正确/错误/需确认）

### 3.3 后端权限与路由

- 所有 `@router.get/post/put/delete` 必须有对应的 `@action_*` 装饰
- 所有 `@permission_resource` 必须有 `parent_resource`
- **输出**：异常端点列表（无权限/无 parent_resource）

### 3.4 前端 i18n 全量

- 在 `frontend/apps/web-antd/src/views/admin/system/codegen/` 下 grep 中文字符串（`[\u4e00-\u9fff]+`）
- 排除：注释、已经 `$t(...)` 包裹的 key、`.json`  locale 文件本身
- **输出**：残留硬编码中文的文件:行号及内容

### 3.5 Codegen 模板与生成一致性

- 对比 `backend/app/codegen/templates/frontend/data_table.ts.j2` 与手写 `frontend/.../views/*/data.ts` 的 `nameField` 推导逻辑
- 对比 `index_table.vue.j2` 与 `index_card.vue.j2` 的 `nameField`
- **输出**：是否一致，若不一致则列为问题

### 3.6 CLI 逐命令

- 对 `novusai codegen` 的每个子命令：参数是否完整、互斥是否检查、错误路径是否 `sys.exit(1)`
- 对 `novusai license keygen`：是否有安全提示
- **输出**：每个命令的结论（通过/问题及描述）

---

## 四、禁止行为

- **禁止推测**：未读到的代码不得写「可能」「或许」
- **禁止遗漏**：强制验证清单 6 项必须全部给出结论
- **禁止模糊**：问题必须带文件路径和行号（或可定位的代码块）
- **禁止跳过测试**：必须执行 `pytest backend/tests/codegen -v` 并报告结果

---

## 五、输出格式（严格遵循）

```markdown
# CRUD 与 CLI 二次审计报告

## 0. 强制验证清单结果

| 序号 | 原问题 | 结论 | 佐证 |
|------|--------|------|------|
| 1 | CodegenConfig __delete_deps__ | 已修复/未修复 | 文件:行号 或 关键代码 |
| 2 | codegen list_configs 分页 | ... | ... |
| ... | ... | ... | ... |

## 1. 测试结果

- `pytest backend/tests/codegen -v`：通过/失败，X 个用例
- `pytest backend/tests -v`（或抽样）：通过/失败，X 个用例

## 2. 全量审计结果

### 2.1 Model __delete_deps__ 全量
（表格：文件 | 有/无/不适用 | 说明）

### 2.2 分页参数全量
（表格：文件:行号 | page_size 来源 | 正确/错误）

### 2.3 权限与 parent_resource
（异常列表或「无异常」）

### 2.4 前端 codegen 硬编码中文
（文件:行号 | 内容 | 建议）

### 2.5 Codegen 模板一致性
（结论 + 差异说明）

### 2.6 CLI 逐命令
（命令 | 结论 | 问题描述）

## 3. 新发现问题（若有）

（格式：文件:行号 | 描述 | 影响 | 建议）

## 4. 审计方法

- 阅读的文件列表
- grep 使用的模式
- 测试命令及输出摘要
```

---

## 六、参考文件

- 上次审计报告：`docs/audit/CRUD_CLI_AUDIT_REPORT.md`
- 项目规范：`.cursor/skills/novusai-saas/SKILL.md`、`references/backend-crud.md`、`references/frontend-crud.md`
- Codegen 测试：`backend/tests/codegen/`

---

## 七、执行顺序建议

1. 运行 `pytest backend/tests/codegen -v`，记录结果
2. 逐项完成「强制验证清单」6 条，记录佐证
3. 执行全量 grep（`__delete_deps__`、`page_size`、`parent_resource`、中文字符）
4. 阅读关键文件补全结论
5. 按输出格式整理报告
