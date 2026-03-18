# 属性面板配置项在 WYSIWYG 预览中的生效审计

> 审计日期：2025-03  
> 范围：FieldPropertyPanel 可配置属性在三个预览视图（表单、列表、详情）中的生效情况  
> 基于上一轮修复后的复审计

---

## 一、已实现项（上一轮修复）

| 属性 | 表单 | 列表 | 详情 | 实现方式 |
|------|------|------|------|----------|
| placeholder | ✅ | -- | -- | getFieldPlaceholder(f, fallback) 用于 Input/Select/Cascader/DictSelect/CronPicker 等 |
| help_text | ✅ | -- | -- | 字段控件下方渲染 `<span v-if="f.help_text">` |
| default | ✅ | -- | -- | watch 初始化 formValues 时优先使用 f.default；RichText 转为 TipTap doc |
| min_value / max_value | ✅ | -- | -- | InputNumber 绑定 `:min`、`:max` |
| queryType | ✅ | -- | -- | 从 form.queryType 或 query_type 读取（修复原 bug） |
| display_name_en | ✅ | ✅ | ✅ | getFieldLabel(f) 按 locale 选择 display_name_en / display_name |
| enum_values（详情） | -- | -- | ✅ | DetailFieldValue 用 getEnumSampleLabel 取首个枚举项 label |
| max_length | ✅ | -- | -- | Input/TextArea 绑定 `:maxlength` |
| max_count | ✅ | -- | -- | ImageUpload/FilePicker 占位区显示「最多 N 个」 |
| relation_display | -- | -- | ✅ | DetailFieldValue 关联分支显示 `(relation_display \| name)` |
| comment | ✅ | ✅ | ✅ | 字段标签旁用 Tooltip 展示（表单、列表卡片、详情） |

---

## 二、本次审计新发现问题

### P1 - 需修复

#### 1. default 值「滞后生效」

**现象**：用户先添加字段，再在属性面板设置默认值，表单预览不回填。

**原因**：`watch(formItemsWithDividers, ...)` 中仅当 `!(fn in formValues)` 时执行初始化；字段已存在后，修改 default 不会触发 formValues 更新。

```ts
// 当前逻辑
if (fn && !(fn in formValues)) {
  if (hasDefault) formValues[fn] = def;
  else ...
}
```

**建议**：在 watch 中增加对 default 的同步：当 `hasDefault` 且当前 `formValues[fn]` 为“空”初值（undefined、空 doc、空串等）时，用 `f.default` 更新。

---

#### 2. RichText placeholder 未绑定

**现象**：属性面板配置的 placeholder 在富文本编辑器中未生效，始终为组件内置占位（如「输入内容...」）。

**原因**：RichTextEditor 支持 `placeholder`，但 WysiwygFormView 未传入：

```vue
<!-- 当前 -->
<RichTextEditor v-model="..." :default-value="RICH_TEXT_DEFAULT_DOC" ... />
```

**建议**：增加 `:placeholder="getFieldPlaceholder(f, 'common.editorPlaceholder')"` 或等效占位符。

---

#### 3. DatePicker / TimePicker / RangePicker 未绑定 placeholder

**现象**：日期、时间、范围选择器的占位符无法通过属性面板配置。

**建议**：为 DatePicker、TimePicker、DatePicker.RangePicker 绑定 `:placeholder="getFieldPlaceholder(f, ...)"`，并补充对应 i18n key。

---

### P2 - 可选优化

#### 4. 列表表头 comment Tooltip

**现状**：列表表格模式的列标题来自 preview-builders，未使用 comment 作为 Tooltip。

**建议**：在 buildGridColumns 中为列配置自定义 header 渲染，当 `f.comment` 存在时用 Tooltip 包裹 title。

---

#### 5. list_visible 在详情视图未生效

**现状**：useConfigFeatures 的 `detailFields` 未按 `list_visible` 过滤；详情视图展示所有非 divider 字段。

**说明**：属性面板中「列表」勾选控制列表展示，「详情」是否受其控制存在歧义。若需求为「列表不显示则在详情也不显示」，需在 detailFields 逻辑中加入 `list_visible` 过滤。

---

#### 6. 搜索区 filterable 的存储路径

**现状**：WysiwygListView 使用 `f.filterable === true` 筛选搜索字段。

**确认**：FieldPropertyPanel 的「可筛选」复选框更新 `filterable` 于顶层字段，路径正确，无问题。

---

### P3 - 低优 / 设计取舍

| 项目 | 说明 |
|------|------|
| min_length | 校验规则，预览不做校验，可接受 |
| pattern / pattern_regex | 同上 |
| editable | 新建表单场景不区分编辑/只读 |
| required 提交校验 | 预览提交非真实业务，当前仅显示星号即可 |
| 表格列 header comment | 实现成本较高，可延后 |

---

## 三、枚举下拉「依然无法下拉」排查要点

若用户配置了「组件=Input + 枚举渲染=下拉框 + 枚举值」仍显示 Input，可依次排查：

1. **数据路径**：`form.component` / `form_component` 与 `form.enumRender` / `enum_render`、`enum_values` 是否按预期写入 store。
2. **类型**：只有 `type === 'Enum'` 时属性面板才展示枚举配置；若为 String，需先改为 Enum。
3. **enum_values 格式**：应为 `[{ value, label_zh?, label_en? }, ...]`；若结构异常，getComponent 中 `ev.length > 0` 可能为 false。
4. **组件名大小写**：TEXT_LIKE_COMPONENTS 已包含 `input`/`Input`，通常无问题。
5. ** computed 依赖**：`formItemsWithDividers` 依赖 `store.configJson.fields`，修改属性后应触发重算，`_comp` 会更新；若未更新，需检查 store 的响应性。

---

## 四、属性生效情况总览

| 属性 | 表单 | 列表 | 详情 | 备注 |
|------|------|------|------|------|
| name | ✅ 过滤/键 | ✅ 列 field | ✅ 键 | - |
| display_name | ✅ getFieldLabel | ✅ getFieldLabel | ✅ getFieldLabel | - |
| display_name_en | ✅ getFieldLabel | ✅ getFieldLabel | ✅ getFieldLabel | 按 locale |
| placeholder | ✅ 大部分 | - | - | 缺 RichText/DatePicker/TimePicker/RangePicker |
| help_text | ✅ | - | - | - |
| comment | ✅ Tooltip | ✅ 卡片 Tooltip | ✅ Tooltip | 缺表格列 header |
| default | ⚠️ 仅首初 | - | - | 后改 default 不更新 |
| required | ✅ 星号 | - | - | 无提交校验 |
| insertable | ✅ 过滤 | - | - | - |
| editable | - | - | - | 预览不区分 |
| list_visible | - | ✅ 列显隐 | - | 详情未用 |
| filterable | - | ✅ 搜索区 | - | - |
| sortable | - | ✅ 列 | - | - |
| queryType | - | ✅ | - | 已修复读取 |
| form.component | ✅ getComponent | - | - | - |
| enum_render | ✅ getComponent | - | - | Input→Select 覆盖 |
| enum_values | ✅ Select options | ✅ Tag/Cell | ✅ getEnumSampleLabel | - |
| min_value / max_value | ✅ InputNumber | - | - | - |
| max_length | ✅ Input/TextArea | - | - | - |
| max_count | ✅ Upload 文案 | - | - | - |
| relation_display | - | - | ✅ | - |
| dict_code | ✅ DictSelect | ✅ Tag | ✅ 分支 | 预览不拉字典 API |

---

## 五、建议修复优先级

| 优先级 | 项目 | 工作量 |
|--------|------|--------|
| P1 | default 滞后生效（watch 同步 default） | 小 |
| P1 | RichText placeholder 绑定 | 小 |
| P1 | DatePicker/TimePicker/RangePicker placeholder | 小 |
| P2 | 表格列 header comment Tooltip | 中 |
| P2 | 详情 list_visible 过滤（若需求明确） | 小 |
