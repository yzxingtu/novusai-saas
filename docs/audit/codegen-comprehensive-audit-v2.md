# CRUD 代码生成器全面审计报告 V2

**审计日期**：2026-03-17  
**审计方法**：基于 Git 未提交文件 + 实际代码阅读，不做推测  
**审计范围**：`backend/app/codegen/`、`backend/app/api/admin/codegen.py`、`frontend/apps/web-antd/src/views/admin/system/codegen/`、相关 Store/API/Router

---

## 一、未提交文件清单（CRUD 代码）

根据 `git status`，以下为 CRUD 代码生成器相关未提交文件：

### 后端
- `backend/app/api/admin/codegen.py`
- `backend/app/codegen/`：config_parser, db_introspector, file_writer, generator, manifest, migration_helper, options, rollback, type_registry, zip_exporter, auto_fix
- `backend/app/codegen/templates/`：presets (simple/tree/dual_scope/workflow), backend/*.j2, frontend/*.j2
- `backend/app/enums/codegen.py`
- `backend/app/models/system/codegen_config.py`, `codegen_config_version.py`
- `backend/app/repositories/system/codegen_config_repository.py`, `codegen_config_version_repository.py`
- `backend/app/schemas/codegen.py`
- `backend/app/services/system/codegen_service.py`
- `backend/migrations/versions/20260317_*.py`
- `backend/tests/codegen/`

### 前端
- `frontend/apps/web-antd/src/api/admin/codegen.ts`
- `frontend/apps/web-antd/src/store/admin/codegen-builder.ts`
- `frontend/apps/web-antd/src/views/admin/system/codegen/`：index.vue, builder.vue, data.ts, list.vue（若存在）
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/`：ComponentPalette, FieldCardList, FieldCard, FieldPropertyPanel, LiveFormPreview, CodePreviewModal, FileTreePanel, CodePreviewPanel, ExpertModal, DbTableImportModal, PresetSelectModal, CompositeUniqueEditor, CustomActionsEditor, DetailGroupEditor, WorkflowEditor, EnumValuesEditor, infer.ts

---

## 二、前端实际结构（与旧审计差异）

### 2.1 页面形态

**实际使用**：三栏可视化构建器（builder.vue），**无** wizard.vue 或 Step 分步向导。

| 路由 | 组件 | 说明 |
|------|------|------|
| `/admin/system/codegen` | index.vue | 配置列表页 |
| `/admin/system/codegen/new` | builder.vue | 新建构建器 |
| `/admin/system/codegen/:id/edit` | builder.vue | 编辑构建器 |

**旧审计文档**（codegen-comprehensive-audit.md）提到的「wizard.vue」「6 步向导」「StepBasicInfo/StepFieldEditor」等，在当前代码库中**不存在**，系过时描述。

### 2.2 构建器三栏布局

1. **左侧**：ComponentPalette（组件面板，拖拽/点击添加）
2. **中间**：FieldCardList（字段列表，拖拽排序）
3. **右侧**：FieldPropertyPanel（属性编辑）+ LiveFormPreview（表单/表格/详情实时预览）

### 2.3 Store

- 实际 Store：`codegen-builder.ts`，导出为 `useCodegenBuilderStore`
- 兼容别名：`useCodegenWizardStore` 指向同一 Store（见 codegen-builder.ts 末行）

---

## 三、配置透传问题（已核实）

### 3.1 recycle_bin 硬编码

**位置**：`backend/app/codegen/templates/frontend/index_table.vue.j2` 第 75 行

```jinja2
recycleBin: true,
```

**config_parser**：`config_parser.py` 第 157 行对 `frontend.recycle_bin` 有默认值 `False`，但**生成的 index_table.vue.j2 从未读取**，始终写死 `recycleBin: true`。

**结论**：生成的列表页永远启用回收站，无法通过配置关闭。

### 3.2 export 未从配置读取

**useCrudPage**：默认 `toolbar = { export: true }`（use-crud-page.ts 第 79 行）。

**index_table.vue.j2**：未传入 `toolbar`，因此使用默认配置，导出始终启用。

**config_parser**：`frontend.export` 默认 `False`（第 158 行），但模板未使用。

**结论**：`frontend.export` 配置存在但无效，生成页面导出功能恒为开启。

### 3.3 后端回收站路由

**controller_admin.py.j2** 第 73-78 行：`register_admin_recycle_bin_routes` **无条件调用**，无 `if frontend.recycle_bin` 等条件分支。

**结论**：后端始终注册回收站路由，与前端的 `recycleBin` 配置无关联。

---

## 四、Relations 支持情况（已核实）

### 4.1 配置与生成

- `config_parser`：解析 `relations` 并传入 `ParsedConfig`
- `generator`：`build_context` 包含 `relations`
- 模板：model.py.j2、schema.py.j2、repository.py.j2、data_table.ts.j2、detail.vue.j2、i18n_zh.json.j2、i18n_en.json.j2、_api_types.j2 中均有 `relations` 相关 Jinja 逻辑

### 4.2 前端编辑

**ExpertModal.vue**：12 个 Collapse 面板为 model、endpoint、menu、features、defaultSort、tree、unique、workflow、customActions、detailGroups、clone、deleteDeps。

**无 Relations 编辑面板**。 relations 仅能通过：
- 手动编辑 YAML 后导入，或
- 由 ForeignKey 字段推断（infer.ts、FieldPropertyPanel 中 relation_table 等）

**结论**：Relations 在后端/模板中完整支持，但构建器 UI 中无可视化编辑入口。

---

## 五、双端生成逻辑（已核实）

### 5.1 端点与 scope

- `generator.py`：根据 `parsed.endpoints` 分别生成 admin / tenant 端文件
- admin 端：`api/admin/{resource}.ts`、`views/admin/{module}/{resource}/`
- tenant 端：`api/tenant/{resource}.ts`、`views/tenant/{module}/{resource}/`

### 5.2 endpoints 来源

- **构建器**：builder.vue 底部有 Admin/Tenant 勾选，但为 disabled 展示用；实际 endpoints 来自 ExpertModal 的 endpoint 面板，或预设 YAML
- **presets**：simple 仅 admin；dual_scope 含 admin + tenant；tree、workflow 为 tenant

---

## 六、类型与组件（已核实）

### 6.1 type_registry 支持类型

`type_registry.py` 中 `_TYPE_MAP` 包含：
String, Text, Integer, BigInteger, Float, Boolean, DateTime, Date, JSON, Enum, Decimal, UUID, ForeignKey, ImageUpload, RichText, FilePicker, CronPicker, IconPicker, CodeEditor, Images, File, Files

共约 20 种类型，均有 `python_type`、`sqlalchemy_type`、`ts_type`、`default_form_component`、`default_search_type`、`default_cell_render`、`default_filter_op`。

### 6.2 ComponentPalette 实际组件

来自 `ComponentPalette.vue` 与 `/admin/codegen/components` API（从 type_registry 推导）：
input, textarea, number, password, select, switch, date, TimePicker, ImageUpload, FilePicker, ApiSelect, RichText, IconPicker, CodeEditor, ColorPicker, divider

**缺少**：TreeSelect、Cascader/CityPicker、UserSelect、DeptSelect 等（与 BuildAdmin 24 种组件对比存在缺口）。

---

## 七、API 与安全（已核实）

### 7.1 端点数量

`codegen.py` 实际注册端点：24 个（与注释一致）。

### 7.2 Preset 路径遍历

**当前实现**（codegen.py 第 305-312 行）：
- 使用 `re.match(r"^[a-zA-Z0-9_-]+$", name)` 校验 `name`
- 使用 `path.is_relative_to(presets_dir.resolve())` 二次校验
- **已修复**（与旧审计结论一致）

### 7.3 DB 反射白名单

- `get_table_columns`：`name not in service.get_table_names()` 时 404
- `import_from_table`：`table_name not in service.get_table_names()` 时 400
- **已实现表名白名单校验**

---

## 八、其他已核实项

### 8.1 版本历史

- CodegenConfigVersion 模型、仓储、服务逻辑完整
- builder.vue 支持版本列表、预览、恢复
- 恢复直接更新 config_json，不创建新版本

### 8.2 DB 导入

- DbTableImportModal：选表 → 选列 → 导入
- 合并 infer 规则与列注释
- import_from_table 返回 `{ resource, module, fields }`，不包含 display_name 等，由前端补全

### 8.3 回滚

- manifest 记录 create/append/merge_json
- CodegenRollback 支持按 resource 或 config_id 回滚
- 支持 force、dry_run

### 8.4 预览与 ZIP

- preview API 返回 files、summary、conflicts
- preview/download 返回 ZIP
- CodePreviewModal：FileTreePanel + CodePreviewPanel（Monaco Diff）

---

## 九、缺口与待办（基于代码）

| 类别 | 问题 | 位置 | 优先级 |
|------|------|------|--------|
| 配置透传 | recycle_bin 硬编码 true | index_table.vue.j2:75 | P0 |
| 配置透传 | frontend.export 未使用 | index_table.vue.j2 | P0 |
| 配置透传 | 后端 recycle_bin 路由恒注册 | controller_admin/tenant.py.j2 | P1 |
| UI 缺失 | 无 Relations 编辑面板 | ExpertModal.vue | P0 |
| 类型缺口 | 无 TreeSelect/Cascader/UserSelect/DeptSelect | type_registry, ComponentPalette | P1 |
| 文档 | 审计文档描述 wizard/Step，实际为 builder | codegen-comprehensive-audit.md | P2 |

---

## 十、文件索引

| 职责 | 路径 |
|------|------|
| API | backend/app/api/admin/codegen.py |
| 服务 | backend/app/services/system/codegen_service.py |
| 配置解析 | backend/app/codegen/config_parser.py |
| 类型映射 | backend/app/codegen/type_registry.py |
| 生成器 | backend/app/codegen/generator.py |
| 列表模板 | backend/app/codegen/templates/frontend/index_table.vue.j2 |
| 数据配置模板 | backend/app/codegen/templates/frontend/data_table.ts.j2 |
| Controller 模板 | backend/app/codegen/templates/backend/controller_admin.py.j2 |
| 构建器 | frontend/.../codegen/builder.vue |
| 专家模式 | frontend/.../codegen/modules/ExpertModal.vue |
| Store | frontend/.../store/admin/codegen-builder.ts |

---

---

## 十一、本次会话修复项（2026-03-17）

| 问题 | 修复 |
|------|------|
| 空 Alert（showRecommend 无内容） | 使用 computed `recommendMessage`，仅在非空时渲染 Alert；改用 `:message` prop 确保内容正确传入 |
| Input value=boolean Vue 警告 | 新增 `strVal()` 将非 string 转为 `''`，对 placeholder、help_text、name、display_name 等 Input 统一使用 |
| CRUD 菜单/权限无多语言 | 后端 `menu.json` 增加 `menu.admin.codegen`；`messages.json` 增加 `action.codegen.*`（list/detail/create/update/delete 等 19 项）中英文案 |
| 属性面板 display_name 等为空 | 此前已修复：`ensureFieldsDisplayNames` 在 loadConfig 时补全；infer 增加 `inferFieldDisplayNames` |
| 属性/表单预览边界不清 | 此前已修复：builder 增加「属性」「表单预览」标题栏 |

---

## 十二、多轮细节审计与修复（2026-03-17）

基于多轮代码审计，对 codegen 进行细节优化与修复，实施项如下。

### 12.1 P0 问题（已修复）

| 问题 | 修复 |
|------|------|
| 重复字段名（前端无校验） | FieldCardList: `addFromPalette`/`onDrop`/`addEmptyField` 通过 `ensureUniqueName` 自动后缀；FieldPropertyPanel `onNameChange` 冲突时 `message.warning` 拒绝 |
| 重复字段名（后端无校验） | config_parser `validate` 增加 `duplicate_field_name`，收集重复 name 返回 ValidationError |
| ID 列缺失 | data_table.ts.j2 在 return 后插入 id 列（width 80, sortable）；i18n 已有 `id` |
| created_at 无 sortable | data_table.ts.j2 对 `f.name == 'created_at'` 的列增加 `sortable: true` |
| Palette/infer 合并覆盖 TreeSelect/Cascader | createFieldFromPalette 对 TreeSelect/Cascader/UserSelect/DeptSelect 保留 palette 的 type 和 component |
| DB 导入完全覆盖 | DbTableImportModal 增加「合并 / 覆盖」选项；builder onDbImported 合并时同名字段更新、新字段追加 |
| 导入字段未去重 | DbTableImportModal enhancedFields 前按 name 去重；BASE_FIELDS 去重 |
| model.py.j2 M2M 缺 Table 导入 | sqlalchemy 导入中增加 `Table` |
| statusSelect 缺 field | data_table.ts.j2 改为 `statusSelect({ field: '{{ f.name }}', label: ... })` |
| date_range 用 raw RangePicker | 改用 `searchDateRange({ field, label, showTime })`；import 增加 searchDateRange |
| ForeignKey ApiSelect fieldName | 改为 `filter[{{ f.name }}][eq]` 或 `[in]`（multiple 时） |

### 12.2 P1 问题（已修复）

| 问题 | 修复 |
|------|------|
| FieldPropertyPanel Input 非 string | default、db_default、divider_title、relation_display、relation_value_field 等统一使用 strVal |
| Cascader JSON 非法无提示 | onCascaderOptionsChange catch 中增加 `message.warning` |
| FieldCardList addEmptyField 空名 | 改为生成 `field_${Date.now()}` 并经 ensureUniqueName |
| computed setter 未 ensureFieldKeys | fields setter 中调用 `ensureFieldKeys(v)` |
| 拖拽 onEnd 直接突变 | 改为 `arr.map((f, i) => ({ ...f, sort_order: i }))` 返回新数组 |
| ExpertModal 子编辑器 fieldOptions 含 divider | DetailGroupEditor、CompositeUniqueEditor、RelationsEditor 过滤 `__divider__` 和 `divider` |
| config_parser 无保留字/非法字符 | 增加 RESERVED_NAMES、FIELD_NAME_PATTERN、MODULE_RESOURCE_PATTERN；module/resource 格式校验 |
| 构建器无系统字段说明 | FieldCardList 顶部增加 `systemFieldsHint` 提示 |

### 12.3 P2 问题（已修复）

| 问题 | 修复 |
|------|------|
| LiveFormPreview 缺 ApiTreeSelect/Cascader/TimePicker | 增加对应预览分支 |
| ForeignKey ApiSelect 搜索 fieldName | 改为 `filter[{{ f.name }}][eq]` 或 `[in]` |

### 12.4 新增 i18n 键

- 前端：`admin.system.codegen.property.duplicateFieldName`、`invalidCascaderJson`、`fieldConfig.systemFieldsHint`；`dbImport.importMode`、`modeReplace`、`modeMerge`
- 后端：`codegen.validation.duplicate_field_name`、`invalid_module_format`、`invalid_resource_format`、`reserved_field_name`、`invalid_field_name`

---

## 十三、后续审计修复（2026-03-17）

### 13.1 delete_deps 字段与结构

| 问题 | 修复 |
|------|------|
| ExpertModal 使用 `model.__delete_deps__` 存 `string[]`，model.py.j2 期望 `delete_deps` 且结构为 `{model, fk_field, strategy}[]` | generator.py `build_context` 增加转换逻辑，将 `__delete_deps__` 转为 `delete_deps` 对象数组后传给模板 |

### 13.2 加载与覆盖时字段规范化

| 问题 | 修复 |
|------|------|
| setConfigJson 直接覆盖 configJson，未做字段去重、未补全 __key | setConfigJson 内调用 `ensureFieldsHaveKey(json)`，与 loadConfig/saveConfig 一致 |
| dedupeFieldsByName 命名语义 | 首个同名字段保留原名，后续加 _2、_3；逻辑已正确实现 |

---

## 十四、批次 4–5 修复项（2026-03-17）

严格遵循 plan 与 NovusAI SaaS skill/rules，完成以下收尾项。

### 14.1 i18n 补全

| 位置 | 新增键 |
|------|--------|
| zh-CN/admin/system.json | codegen.preview.diff、codegen.preview.groupTitle |
| en-US/admin/system.json | codegen.preview.diff、codegen.preview.groupTitle |

### 14.2 infer.ts 增强

- `SYSTEM_FIELDS` 补 `is_deleted`
- 新增 uuid/code/slug/sn 规则：`type: String, filterable: true, queryType: ilike, listVisible: true`
- `parseCommentEnum`：支持引号包裹 `"x"=y`、无引号 `key=label`、空 part 跳过；正则边界修正

### 14.3 Store 重命名

- 12 个组件已全部使用 `useCodegenBuilderStore`（无 `useCodegenWizardStore` 残留）

### 14.4 CodePreviewPanel / FileTreePanel

- CodePreviewPanel：`'Diff'` 改为 `$t('admin.system.codegen.preview.diff')`
- CodePreviewPanel：`content` 使用 `?? ''` 防止 undefined
- FileTreePanel：`type` 未定义或非 create/modify/append 的叶节点使用 `lucide:file` 代替 `lucide:folder`
- FileTreePanel：onSelect `info.node` 类型增加 `type?: string`

### 14.5 LiveFormPreview

- groupTitle 已使用 i18n（此前完成）
- 表格示例数据：2–3 行 `tableSampleRows`，按字段类型生成示例（id/boolean/number/date/image/file 等）

### 14.6 已完成计划项（本批次）

- p1-template-enhance：data_table op_options、type_registry Image/File/Files、maxCount:1
- p1-infer-enhance：uuid/code/slug/sn、parseCommentEnum、is_deleted
- p2-store-rename：全部 useCodegenBuilderStore
- p2-code-preview：Diff i18n + content 守卫 + FileTreePanel 类型覆盖
- p2-preview-enhance：groupTitle i18n + 表格示例数据

### 14.7 批次 4–5 收尾项（2026-03-17）

| 项目 | 修复 |
|------|------|
| p2-generator-context | `generator.py` `build_context` 补 `admin_only_eps`、`tenant_only_eps`、`has_admin_only`、`has_tenant_only` |
| p2-api-security | validate/preview 使用 `CodegenValidateBodySchema`、`CodegenPreviewBodySchema`；preview_download 错误脱敏（含路径或 Traceback 时返回 `preview_download_error_sanitized`） |
| p2-i18n-complete | 补全 action/unique/workflow 等生成模板所需键，及 builder UI 新增键 |

### 14.8 审计结论更新

- **旧结论清理**：`codegen-comprehensive-audit.md` 中提到的 wizard/Step 分步向导已明确标注为过时（§2.1）。当前实际形态为 builder 三栏布局。
- **缺口表（§九）**：P0/P1 项已在多轮修复中完成；P2 项（Relations 编辑面板、TreeSelect 等）保留为后续增强。

---

## 十五、深度审计（2026-03-17）

基于多维度审计（安全、错误处理、性能、数据一致性、模板、LiveFormPreview、测试、UX、i18n、代码质量），补充如下发现。

### 15.1 配置透传（已修正）

**此前审计**：§3 指出 `recycle_bin` 硬编码 `true`、`export` 未使用。

**当前状态**：`index_table.vue.j2` 已从 `_fe.get('recycle_bin', False)`、`_fe.get('export', False)` 读取；`config_parser._expand_defaults` 设置默认值。**已修复**。

### 15.2 安全

| 问题 | 位置 | 严重度 | 建议 |
|------|------|--------|------|
| 路径遍历 | codegen.py get_preset | ✅ 已防护 | `re.match` + `is_relative_to` |
| DB 表名白名单 | get_table_columns / import_from_table | ✅ 已防护 | |
| 错误脱敏 | preview_download_zip | ✅ 已实施 | |
| validate 异常泄露 | codegen_service.py L189-190 | 中 | `str(e)` 可能暴露堆栈，建议统一错误码与用户文案 |
| config_json 无大小限制 | schemas/codegen.py | 中 | 易 DoS，建议 Pydantic 自定义 validator 限制深度或体积 |
| FileWriter 路径 | file_writer._normalize_path | 低 | 建议增加 `is_relative_to(project_root)` 二次校验 |

### 15.3 错误处理

| 问题 | 严重度 | 建议 |
|------|--------|------|
| 预览失败返回结构不一致 | 中 | validate 异常时 `errors[].message` 与正常时 `code`/`path` 格式不同，前端需兼容 |
| 保存前未校验 | 中 | onSave 未调用 postCodegenValidateApi，可保存 fields 为空的配置 |
| 前端 catch 仅 message.error | 低 | 未区分网络/校验/解析错误，建议按类型提示 |

### 15.4 性能

| 问题 | 严重度 | 建议 |
|------|--------|------|
| 预览 API 无防抖 | 中 | CodePreviewModal 打开即请求，多次快速操作可能产生多余请求 |
| 大 config_json 渲染 | 中 | 字段多时 FieldCardList 大量 DOM，可考虑虚拟滚动 |
| localStorage 持久化 | 中 | `configJson` 大时可能占满（约 5MB），建议限制或改 sessionStorage |
| Undo/Redo 深拷贝 | 低 | `JSON.parse(JSON.stringify(...))` 大对象开销大 |

### 15.5 数据一致性

| 问题 | 严重度 | 建议 |
|------|--------|------|
| loadConfig 清空历史栈 | 中 | 版本恢复后无法 Undo，需在 UI 说明 |
| 并发保存无乐观锁 | 中 | 多窗口同时编辑可能覆盖，建议 updated_at 或版本校验 |
| PreviewResult conflicts 类型 | 低 | 后端 `list[dict]` 与前端 `Array<Record>` 可对齐 |

### 15.6 模板与 LiveFormPreview

| 问题 | 位置 | 严重度 | 建议 |
|------|------|--------|------|
| LiveFormPreview 缺 CronPicker | LiveFormPreview.vue | 中 | type_registry 有 CronPicker，预览无分支，会落到 default Input；需增加 CronPicker 分支 |
| DictSelect / CodeEditor | LiveFormPreview.vue | ✅ 已支持 | |
| step=test 前后端不统一 | generator / API Schema | 低 | step 类型未含 "test" |
| type_registry 无 DictSelect 显式注册 | type_registry.py | 低 | dict_code 通过 data_table 分支处理，逻辑正确 |

### 15.7 测试覆盖

| 已有 | 缺失 |
|------|------|
| config_parser, db_introspector, file_writer, generator_snapshots, rollback, type_registry | codegen_service preview/generate/validate 集成测试；codegen API E2E；前端 builder 组件/E2E |
| | Snapshot 可补充 sub_form、workflow preset |

### 15.8 可访问性与 UX

| 项 | 状态 |
|----|------|
| 加载态 | ✅ Spin、isSaving、isGenerating |
| 空状态 | ✅ 表单/表格/详情空提示 |
| 键盘/焦点 | 待评估：拖拽为主，模态框焦点 |
| 错误展示 | validationErrors 需确认 UI 位置 |

### 15.9 代码质量

| 问题 | 建议 |
|------|------|
| _PROJECT_ROOT 重复定义 | 抽到公共常量 |
| MAX_HISTORY=50 魔法数字 | 可配置或加注释 |
| useCodegenWizardStore deprecated | 迁移完成后移除 |
| expertItemCount 逻辑冗长 | 拆成小函数 |
| FileWriter __all__ 用 replace | 可能误伤，考虑 AST 解析 |

### 15.10 深度审计优先级汇总

| 优先级 | 项 | 状态 |
|--------|-----|------|
| **P0** | config_json 无大小限制（DoS）；保存前未校验 | ✅ 已修复（2026-03-17） |
| **P1** | LiveFormPreview 补 CronPicker；validate 异常脱敏；预览 API 防抖；localStorage 大配置；loadConfig 历史栈说明 | ✅ 已修复 |
| **P1** | 并发保存乐观锁 | 未实现（需设计） |
| **P2** | FileWriter 路径校验；_PROJECT_ROOT 抽常量 | ✅ 已修复 |
| **P2** | 前端错误分类；类型对齐；测试补充；代码质量 | 待后续 |

### 15.11 本次修复项（2026-03-17）

| 项 | 修复 |
|----|------|
| config_json DoS | schemas/codegen.py 增加 _validate_config_json_size，限制 2MB/深度 30；CodegenConfigCreate/Update、Validate/PreviewBody 均校验 |
| 保存前校验 | builder.vue onSave 前调用 postCodegenValidateApi，失败则阻止保存并展示 validationErrors |
| CronPicker | LiveFormPreview getComponent 增加 CronPicker 分支，模板已支持 |
| validate 脱敏 | codegen_service.validate 捕获异常时，含 traceback/path 等则返回 codegen.validation.parse_error |
| 预览防抖 | CodePreviewModal 使用 useDebounceFn(fetchPreview, 200) |
| localStorage | codegen-builder 自定义 storage，configJson > 400KB 时不持久化 |
| 版本恢复提示 | 恢复后 message.info 提示「恢复后撤销历史已清空」 |
| _normalize_path | file_writer 增加 is_relative_to(project_root) 校验 |
| _PROJECT_ROOT | 抽取到 app/codegen/constants.py CODEGEN_PROJECT_ROOT |

---

**报告结束**
