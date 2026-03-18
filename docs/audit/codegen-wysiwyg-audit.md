# 代码生成器全面审计报告

> 审计日期：2025-03-18（全面更新）  
> 范围：前端 codegen 全模块、后端 codegen API/服务/生成器、store、i18n  
> 更新：2025-03 期间完成 P2/P3 全项

---

## 一、已修复项（2025-03 期间）

| 项目 | 状态 |
|------|------|
| WysiwygDetailView 分组模式缺少 getComponent 导入 | ✅ 已补充 `import { getComponent } from './field-utils'` |
| RichText 空文档 tiptap 报错 | ✅ 使用 `{ type: 'paragraph' }` 替代空 text 节点 |
| WysiwygListView proxy/commitProxy 递归更新 | ✅ 使用 gridRemountKey + 静态 data 避免 |
| Rate 组件导入 | ✅ 已导入 |
| EnumValuesEditor computed 导入 | ✅ 已补充 |
| common.name i18n | ✅ 已添加 |
| 分组 groupTitle / 示例值 / richTextContent | ✅ 已用 $t() |
| href="javascript:void(0)" | ✅ DetailFieldValue 改为 role="link" |
| ColorPicker 硬编码 #6366f1 | ✅ DetailFieldValue 使用 var(--primary) |
| **关联表下拉假数据** | ✅ 新增 GET /db/tables/{name}/rows，WysiwygFormView 用 ApiSelect+API 拉真实数据 |
| **关联表显示字段切换不刷新** | ✅ ApiSelect 增加 `:key` 依赖 `relation_display`，切换 display_field 时重新加载 |
| **placeholderCascaderOptions i18n 报错** | ✅ 移除含 `{}` 的 JSON 示例，改为描述性占位文案 |
| **P2 分组模式复用 DetailFieldValue** | ✅ WysiwygDetailView 分组/平铺均使用 `<DetailFieldValue>` |
| **P2 preview-builders any 替换** | ✅ 已用 `VxeColumn` 类型 |
| **P2 删除 LiveFormPreview** | ✅ 已移除，field-utils 无引用 |
| **P3 卡片模式操作链接** | ✅ 已改为 `<span role="link">` + Tooltip + `cardPreviewOnly` |
| **P3 sample_file.pdf** | ✅ 已用 `preview.sampleFileName` i18n |
| **P3 getMockCellValue 硬编码** | ✅ 已用 `preview.sampleA/B/C` i18n（preview-builders.ts + field-utils.ts） |

---

## 二、前端：WYSIWYG 核心模块

### 2.1 文件清单

| 文件 | 职责 | 依赖 |
|------|------|------|
| `WysiwygCenter.vue` | 三视图切换、拖拽落点、字段管理入口 | FieldCardList, Wysiwyg*View |
| `WysiwygListView.vue` | 列表/卡片预览，CrudGrid 或卡片布局 | preview-builders, useConfigFeatures |
| `WysiwygFormView.vue` | 新建表单预览，可编辑可提交 | ApiSelect, getCodegenDbTableRowsApi |
| `WysiwygDetailView.vue` | 详情预览，分组/平铺 | DetailFieldValue, field-utils |
| `DetailFieldValue.vue` | 单字段值渲染（抽取组件） | field-utils |
| `preview-builders.ts` | 构建 Grid columns、mock 行 | field-utils |
| `field-utils.ts` | getComponent、shouldHideInList 等 | infer |
| `useConfigFeatures.ts` | 响应式特征（detailGroups、formColumns 等） | store |

### 2.2 待修复 / 优化（剩余）

无。

---

## 三、前端：其他 codegen 模块

### 3.1 LiveFormPreview.vue

**状态**：✅ 已移除，项目中无引用。

### 3.2 关系与数据流

- **store**：`useCodegenBuilderStore`，configJson、selectedFieldKey、wysiwygViewMode、showFieldManager
- **API**：`getCodegenDbTablesApi`、`getCodegenDbColumnsApi`、`getCodegenDbTableRowsApi`（新增）
- **关联下拉**：有 `relation_table` 时用 ApiSelect + `getCodegenDbTableRowsApi`；无则 fallback mock

---

## 四、后端：Codegen 服务与 API

### 4.1 端点一览

| 分类 | 端点 | 说明 |
|------|------|------|
| 配置 CRUD | GET/POST/PUT/DELETE /configs | 列表、详情、创建、更新、删除 |
| 版本 | GET /configs/{id}/versions | 版本列表、详情、恢复 |
| 元数据 | /types, /components, /models, /presets, /options | 类型、组件、模型、预设、选项 |
| DB 反射 | GET /db/tables | 表列表 |
| DB 反射 | GET /db/tables/{name}/columns | 表列 |
| DB 反射 | GET /db/tables/{name}/rows | **表行（关联下拉预览）** |
| DB 反射 | POST /db/import | 从表导入 |
| 核心 | POST /validate, /preview, /generate | 校验、预览、生成 |
| 其他 | GET /download/{id}, /history, DELETE /rollback | 下载、历史、回滚 |

### 4.2 安全与合规

| 项目 | 状态 |
|------|------|
| DEBUG 守卫 | ✅ 所有端点 `_require_debug()` |
| 表名列名白名单 | ✅ `get_table_rows` 校验表名、列名 |
| SQL 注入 | ✅ 参数化 `text()` + 白名单 |
| 软删除过滤 | ✅ 有 `is_deleted` 时自动 `WHERE is_deleted = false` |
| limit 上限 | ✅ 500 |

### 4.3 DbIntrospector 新增

```python
def get_table_rows(
    table_name, value_field, display_field,
    limit=200, search=None
) -> list[dict[str, Any]]
```

- 返回 `[{"value": ..., "label": ...}, ...]`
- 表名、列名白名单校验
- 自动过滤 `is_deleted`

---

## 五、i18n 覆盖

### 5.1 已存在键（admin.system.codegen）

| 路径 | 用途 |
|------|------|
| `preview.pleaseInput` | 请输入 |
| `preview.pleaseSelect` | 请选择 |
| `preview.selectRelation` | 请选择关联 |
| `preview.richTextContent` | （富文本内容） |
| `preview.sampleValue` | 示例值 |
| `preview.groupTitle` | 分组 {idx} |
| `preview.noEnumHint` | 请在右侧属性面板配置枚举选项 |
| `wysiwyg.formTitle` | 新建 {name} |
| `wysiwyg.detailTitle` | {name} 详情 |
| `wysiwyg.emptyHint` / `dragHint` | 空状态提示 |

### 5.2 可选补充（已实现）

| 键 | 用途 | 状态 |
|----|------|------|
| `preview.sampleFileName` | 文件 mock 占位（如 sample_file.pdf） | ✅ 已添加 |
| `wysiwyg.cardPreviewOnly` | 卡片模式「仅预览」提示 | ✅ 已添加 |

---

## 六、代码生成器全模块架构

### 6.1 前端页面

| 路由 | 组件 | 职责 |
|------|------|------|
| `/admin/system/codegen` | `index.vue` | 配置列表、DB 导入、预设选择 |
| `/admin/system/codegen/:id/edit` | `builder.vue` | 三栏可视化构建器（配置编辑） |
| `/admin/system/codegen/new` | `builder.vue` | 同上，新建模式 |

### 6.2 模块分类

| 分类 | 文件 | 说明 |
|------|------|------|
| **页面** | index.vue, builder.vue | 入口 |
| **数据** | data.ts | 列定义、搜索 schema |
| **WYSIWYG** | WysiwygCenter, Wysiwyg*View, DetailFieldValue | 预览三视图 |
| **编辑** | FieldPropertyPanel, FieldCard/List, ComponentPalette | 字段编辑 |
| **弹窗** | CodePreviewModal, DbTableImportModal, PresetSelectModal, ExpertModal | 各类弹窗 |
| **高级** | RelationsEditor, DetailGroupEditor, WorkflowEditor, CustomActionsEditor, CompositeUniqueEditor | 高级配置 |
| **工具** | field-utils, infer, preview-builders, useConfigFeatures | 工具函数 |

### 6.3 Store

- **useCodegenBuilderStore**：主 store，configJson、selectedFieldKey、previewCache 等
- **useCodegenWizardStore**：`@deprecated`，别名指向 useCodegenBuilderStore


## 七、后端生成器概况

| 组件 | 职责 |
|------|------|
| `config_parser.py` | YAML/JSON 解析 → ParsedConfig |
| `generator.py` | Jinja2 模板渲染，按 step 生成 |
| `db_introspector.py` | 表/列/行反射，白名单校验 |
| `file_writer.py` | 原子写入、冲突检测 |
| `rollback.py` | 回滚逻辑 |
| `zip_exporter.py` | 预览 ZIP 打包 |
| `manifest.py` | 生成历史记录 |
| `type_registry.py` | 类型映射 |
| templates/* | Jinja2 模板 |

---

## 八、修复优先级建议（最终）

| 优先级 | 项目 | 状态 |
|--------|------|------|
| P0 | 无 | 严重缺陷已修复 |
| P1 | 无 | 高优项已处理 |
| P2 | 分组模式复用 DetailFieldValue | ✅ 已完成 |
| P2 | preview-builders 的 any 替换 | ✅ 已完成 |
| P2 | 删除 LiveFormPreview | ✅ 已完成 |
| P3 | 卡片模式操作链接 href → span/tooltip | ✅ 已完成 |
| P3 | sample_file.pdf 常量或 i18n | ✅ 已完成 |
| P3 | getMockCellValue 硬编码 | 低优，可保留 |

---

## 九、审计结论

- **已修复**：getComponent、RichText、proxy 循环、Rate、枚举、i18n 硬编码、ColorPicker、**关联表真实数据**、关联显示字段切换、cascader i18n、P2/P3 全项（分组 DetailFieldValue、类型优化、LiveFormPreview、卡片链接、sampleFileName）。
- **当前状态**：核心 WYSIWYG 流程可用，关联下拉已拉取真实 DB 数据；整体架构清晰，后端安全合规。P2/P3 优化项已全部完成。
- **剩余**：仅 P3 getMockCellValue 中「示例 A/B/C」硬编码，影响极小，可保留。
