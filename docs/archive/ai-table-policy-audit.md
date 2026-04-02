# AI 表策略整改方案 + Codegen 综合审计报告

审计日期：2026-03-18（全面复核：2026-03-19）

## 一、已完成项 ✅

### P0-核心：__ai_policy__ 声明式机制
| 项目 | 状态 | 说明 |
|------|------|------|
| sync_service 只扫描有声明的 Model | ✅ | 遍历 `Base.registry.mappers`，仅处理 `__ai_policy__` |
| `_build_default_policy_from_declaration()` | ✅ | 已实现，支持 dict 与 True 简写 |
| 移除 _BLOCKED_TABLES / _is_log_table | ✅ | 已移除，改用白名单 |
| __abstract__ 继承误跳修复 | ✅ | 使用 `cls.__dict__.get("__abstract__", False)` 避免误跳过子类 |
| 10 个 Model 添加 __ai_policy__ | ✅ | tenants, tenant_plans, tenant_users, ai_providers, ai_models, agents, agent_conversations, knowledge_bases, ai_call_logs, ai_usage_stats |

### P0-前端：index.vue
| 项目 | 状态 | 说明 |
|------|------|------|
| 移除 Card 包裹 | ✅ | 直接 `Page` + `Grid` |
| 同步按钮改 toolbar-tools | ✅ | 在 `#toolbar-tools` 中 |
| CRUD 按钮 Tailwind | ✅ | `transition-all hover:scale-105` + 颜色类 |
| i18n name | ✅ | `admin.ai.tablePolicy.name` = "表策略" |
| pageDesc 引导文案 | ✅ | 已含配置流程说明 |

### P0-表单：data.ts + form.vue
| 项目 | 状态 | 说明 |
|------|------|------|
| keywords 标签输入 | ✅ | Select mode: 'tags' |
| column_descriptions 列描述编辑器 | ✅ | 每列可编辑描述 |
| transform 补全 | ✅ | 含 keywords、column_descriptions |
| 列加载失败提示 | ✅ | `message.warning(columnLoadFailed)` |

### P1-后端修复
| 项目 | 状态 | 说明 |
|------|------|------|
| agent_acces → agent_access | ✅ | `_derive_permission_code` 中已正确 |
| SchemaProvider tenant_id | ✅ | `get_table_descriptions` 和 `get_crud_allowed_tables` 支持 `tenant_id` |
| TableSchema.to_dict() 含 permission_code | ✅ | schema_provider 中已包含 |

### P1-文档
| 项目 | 状态 | 说明 |
|------|------|------|
| backend-crud.md Step 1 补充 __ai_policy__ | ✅ | 含完整/简写示例与属性说明 |
| ai-table-policy-spec.md 新建 | ✅ | 设计理念、声明方式、同步机制、安全准则 |
| SKILL.md 关键注意 | ✅ | "如需此表对 AI 可见...必须声明 __ai_policy__" |

### P1-技能包
| 项目 | 状态 | 说明 |
|------|------|------|
| 迁移更新技能包/技能描述 | ✅ | `20260320_update_data_mgmt_pkg_desc.py` |
| 前端未声明策略警告 | ✅ | 表名列旁 `lucide:alert-triangle` |
| 技能 form di_table_policy_ids tablePoliciesHelp | ✅ | "仅显示声明了 __ai_policy__ 的表..." |
| 同步 API 返回 declared_tables | ✅ | sync 返回 + GET /declared-tables |

### P2-增强
| 项目 | 状态 | 说明 |
|------|------|------|
| 展开行显示列信息 | ✅ | blocked/readonly/described 摘要 + 「查看使用此策略的技能」 |
| 关联跳转按钮 | ✅ | `goToSkillsWithPolicy(row.id)` |
| pageDesc 引导文案 | ✅ | 与 P0 重复，已覆盖 |

---

## 二、未完成 / 部分完成项 ⚠️

### 1. P2：codegen 集成 __ai_policy__ 选项【未完成】
**方案 0H / P2-enhance todo 要求**：
- ExpertModal 中增加「AI 表策略」选项
- 开关：是否生成 `__ai_policy__` 声明
- 若开启可配置 label、keywords、CRUD 权限
- `model.py.j2` 条件输出 `__ai_policy__`

**当前状态**（已核验）：
- `model.py.j2` 无 `__ai_policy__` 块
- ExpertModal、useConfigFeatures 无 ai_policy 相关配置
- 全项目 grep 无匹配

**建议**：在 ExpertModal「模型与数据」Tab 增加 `ai_policy` 配置；在 model 模板中根据配置输出 `__ai_policy__`。

---

### 2. 关联跳转：路径与过滤【部分完成】
**当前**：
- 有「查看使用此策略的技能」按钮
- 跳转到 `path: '/admin/ai/skills'` + `query: { table_policy_id }`

**问题**：
- 后端仅注册 `path="/ai/skill-packages"` + `component="ai/skill-packages/index"`，无 `/ai/skills` 页面路由
- 技能 UI 在 skill-packages 的右侧面板，`/admin/ai/skills` 很可能 404
- skill-packages 未读取 `route.query.table_policy_id` 做过滤/高亮

**建议**：
- 将 `goToSkillsWithPolicy` 的 path 改为 `'/admin/ai/skill-packages'`
- 在 skill-packages 的 `onMounted`/`watch(route)` 中读取 `table_policy_id`，筛选或高亮使用该策略的技能包/技能

---

### 3. 展开行：完整列名+类型【部分完成】
**方案 4A**：展开行展示「列名列表（带类型标签）」

**当前**：仅展示 blocked/readonly/described 摘要 + 「查看使用此策略的技能」，未逐列展示「列名 + 类型」。

**建议**：若需完全符合方案，可增加列详情表格；现状已能满足大部分管理需求。

---

## 三、Codegen WYSIWYG 审计跟进

| 项 | codegen-wysiwyg-audit.md | 当前状态 |
|----|---------------------------|----------|
| getComponent 未导入导致分组详情报错 | P0 严重 | ✅ 已修复：`WysiwygDetailView.vue` L15 `import { getComponent } from './field-utils'` |
| 分组模式硬编码（分组 N、关联名、示例值） | P1 | ⚠️ 部分：`sampleValue` 已用 $t，`selectRelation` 已用，`分组 ${idx+1}` 等仍硬编码 |
| DetailFieldValue 富文本占位 i18n | P1 | ⚠️ `（富文本内容）` 仍硬编码 |
| sample_file.pdf 占位 | P2 | 可接受（mock），或抽成 i18n |
| href="javascript:void(0)" | P2 | 分组模式内联仍存在，平铺已改 role="link" |
| preview-builders any 类型 | P2 | 未修复 |
| 分组模式复用 DetailFieldValue | P2 | 未重构，仍有大量内联重复 |

---

## 四、未在核心 scope 内的项

| 项 | 方案位置 | 备注 |
|----|----------|------|
| recycleBin 支持 | 问题 8 | 表策略为 sync 创建，通常不做回收站 |
| 批量启用/禁用 | 功能 13 | 未实现 |
| 测试 SQL 查询 | 功能 15 | 未实现 |
| 展开行 trigger: 'row' | 4A | 已用 expandConfig，VxeTable 需验证是否支持 row 触发展开 |

---

## 五、总结

| 类别 | 数量 |
|------|------|
| 已完成 | 28 项（AI 表策略） + 1 项（Codegen getComponent） |
| 未完成 | 1 项（codegen __ai_policy__ 集成） |
| 部分完成 | 2 项（关联跳转、展开行列详情） + Codegen 硬编码/类型等 |

**核心整改已落地**：声明式机制、UI/UX、表单、文档、技能包更新均按方案实现。

**待补**：
1. **P2 codegen**：在 ExpertModal 和 `model.py.j2` 中集成 `__ai_policy__`
2. **关联跳转**： path 改为 `/admin/ai/skill-packages`，并实现 `table_policy_id` 过滤/高亮
