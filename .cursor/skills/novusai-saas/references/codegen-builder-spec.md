# Codegen Visual Builder 规范

> 本文档覆盖代码生成器的可视化构建器，不讨论 CLI/YAML 基础用法。
> 适用范围：`/admin/system/codegen/new`、`/admin/system/codegen/:id/edit`、`builder.vue`、`useCodegenBuilderStore`、WYSIWYG 预览与属性面板。

---

## 一、现状说明

当前真实实现不是旧版“6 步向导”，而是三栏可视化 Builder：

```
左栏: ComponentPalette
中栏: WysiwygCenter（list/form/detail 预览）
右栏: FieldPropertyPanel + 代码预览/专家模式/DB 导入等辅助面板
```

对应路由：

| 路由 | 页面 |
|------|------|
| `/admin/system/codegen` | 配置列表页 |
| `/admin/system/codegen/new` | 新建 Builder |
| `/admin/system/codegen/:id/edit` | 编辑 Builder |

因此：

- 不要再把 Builder 写成 step wizard
- 文档、评审、二次开发都应以 `builder.vue` 为真实入口

---

## 二、核心文件

| 文件 | 职责 |
|------|------|
| `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue` | 三栏总装页面 |
| `frontend/apps/web-antd/src/store/admin/codegen-builder.ts` | Builder 状态、历史、持久化、预览缓存 |
| `.../modules/ComponentPalette.vue` | 左栏组件面板 |
| `.../modules/WysiwygCenter.vue` | 中栏预览总控 |
| `.../modules/WysiwygListView.vue` | 列表预览 |
| `.../modules/WysiwygFormView.vue` | 表单预览 |
| `.../modules/WysiwygDetailView.vue` | 详情预览 |
| `.../modules/FieldPropertyPanel.vue` | 字段属性编辑面板 |
| `.../modules/ExpertModal.vue` | 高级配置/YAML/端点设置 |
| `.../modules/DbTableImportModal.vue` | 从 DB 表导入字段 |
| `.../modules/CodePreviewModal.vue` | 代码预览 |

---

## 三、Store 契约

统一状态入口：`useCodegenBuilderStore`

核心字段：

- `configId`
- `configJson`
- `historyStack` / `redoStack`
- `previewCache`
- `validationWarnings`
- `isDirty`
- `selectedFieldKey`
- `wysiwygViewMode`
- `showFieldManager`

关键规则：

- 更新配置必须优先走 `store.updateConfig()` 或 `store.setConfigJson()`
- 不要在组件里直接深层 mutate `configJson`
- 预览缓存失效、历史栈推进、dirty 标记都依赖 store 封装

### 持久化限制

Builder store 会把配置持久化到 localStorage，但 `configJson` 超过约 400KB 时会跳过持久化，避免占满浏览器配额。

因此：

- 不能假设“大配置一定会被本地恢复”
- 大表导入后应尽快保存到后端配置

### 历史旧名

`useCodegenWizardStore` 旧别名已删除，当前统一使用 `useCodegenBuilderStore`。新增代码和文档都不要再引用旧名。

---

## 四、Builder 页面编排

`builder.vue` 负责：

1. 根据路由判断新建/编辑模式
2. 加载 codegen options、配置详情、版本历史
3. 控制保存、校验、生成、恢复版本、导入 YAML、导入 DB
4. 协调三栏交互

主要行为：

- `onPaletteAdd()` 向当前配置追加字段
- `onSave()` 保存配置到数据库
- `postCodegenValidateApi()` 先校验，再允许保存/生成
- `postCodegenGenerateApi()` 触发真正生成
- `downloadCodegenPreviewZipApi()` 下载预览 ZIP

---

## 五、字段编辑规则

### 新增字段

默认从 Palette 或 DB 导入进入，不建议手写裸字段对象。

原因：

- `field-utils.ts` 会补 `__key`
- 会做 display name/comment 推断
- 会根据名称和类型自动推断组件、关联表、默认表单行为

### 选中字段

右侧 `FieldPropertyPanel.vue` 基于 `selectedFieldKey` 工作。

属性面板职责：

- 加载 codegen type/component/db table 选项
- 编辑字段 `type` / `form.component` / `enum_values` / relation 配置
- 在名称变化时触发 `inferFieldConfigForMerge()`
- 保证同名字段不重复

规则：

- 字段属性编辑统一走属性面板
- 不要在别的组件里复制一份字段推断逻辑

---

## 六、WYSIWYG 预览规则

中栏统一由 `WysiwygCenter.vue` 控制，支持：

- `list`
- `form`
- `detail`

其职责不是保存真实渲染状态，而是基于当前 `configJson` 进行近实时预览。

规则：

- 预览只负责反馈配置效果，不等于最终生成代码
- 列/表单/详情效果的样式与布局调整，应优先改预览构建器和 `useConfigFeatures()`，不要分散到多个页面

---

## 七、专家模式与 DB 导入

### ExpertModal

用于编辑较高自由度配置，例如：

- 端点
- 高级 YAML/JSON
- 工作流
- 自定义 action
- 详情页分组

### DbTableImportModal

用于从真实数据库表反射字段并合并到当前配置。

开发规则：

- 不要把 DB 导入当作“全量覆盖唯一来源”
- 合并逻辑应尽量保留已有字段定制
- 导入后仍需通过属性面板校验生成字段是否符合业务语义

---

## 八、版本、预览、生成

Builder 不只是本地编辑器，还连接后端配置版本体系：

- 配置版本列表/预览/恢复
- 生成前校验
- 预览 ZIP 下载
- 真正生成代码

规则：

- 先 `validate`，再 `save` / `generate`
- 版本恢复后应重新检查 `isDirty` 和预览状态
- 生成成功不等于代码一定可直接提交，仍需 review 权限、隔离、删除依赖、i18n

---

## 九、不要再沿用的旧说法

以下表述已过时，不应再出现在 `.cursor` 文档中：

- “6 步向导”
- “wizard.vue 是主入口”
- “Step 1/2/3/4/5/6 页面切换”

当前真实入口只有：

- 列表页 `index.vue`
- Builder 页 `builder.vue`

---

## 十、检查清单

- [ ] 文档是否把 Builder 描述为三栏页面，而不是旧向导
- [ ] 是否统一通过 `useCodegenBuilderStore`
- [ ] 字段变更是否通过 `updateConfig()` / 属性面板流转
- [ ] 保存/生成前是否调用校验 API
- [ ] 是否正确区分预览、保存、生成、版本恢复
- [ ] 是否确认仓内已无 `useCodegenWizardStore` 旧名残留
