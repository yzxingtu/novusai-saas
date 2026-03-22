# 代码生成器 Web + CLI 一体化整改方案（给 Kimi）

## 1. 文档目的

这份方案不是单纯做“UI 美化”，也不是只修一两个局部 bug。

本次目标是把以下四条线一次性收口：

1. 管理端代码生成器列表页、创建页、编辑页的信息架构与交互体验。
2. Web 端与后端在“草稿、校验、生成、回滚、删除”语义上的不一致。
3. 代码生成 CLI 与 HTTP/API 能力之间的契约漂移、参数漂移、JSON 输出漂移。
4. 危险操作、版本恢复、预设模板、预览反馈、测试矩阵等长期维护问题。

结论先说：当前代码生成器的主要问题不是“配色旧”，而是“工作流语义不严谨 + 危险操作没有护栏 + 前后端/CLI 契约漂移 + 页面信息层级过载”。

因此，最优做法不是先换样式，而是按下面的批次统一整改：

1. 先修语义正确性与危险操作。
2. 再统一 API/CLI 契约。
3. 最后重构列表页与构建器 UI。

---

## 2. 本次审计范围

### 2.1 Web 端

- `frontend/apps/web-antd/src/views/admin/system/codegen/index.vue`
- `frontend/apps/web-antd/src/views/admin/system/codegen/data.ts`
- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/PresetSelectModal.vue`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/ComponentPalette.vue`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/CodePreviewModal.vue`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/FileTreePanel.vue`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/CodePreviewPanel.vue`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/ExpertModal.vue`
- `frontend/apps/web-antd/src/router/routes/admin/index.ts`

### 2.2 后端 / API / Service

- `backend/app/api/admin/codegen.py`
- `backend/app/services/system/codegen_service.py`
- `backend/app/codegen/config_parser.py`
- `backend/app/schemas/codegen.py`
- `backend/app/models/system/codegen_config.py`

### 2.3 CLI

- `backend/app/cli.py`
- `backend/tests/codegen/test_cli_smoke.py`
- `backend/app/codegen/templates/presets/*.yaml`

---

## 3. 审计结论

下面按严重程度排序。前 6 项属于必须先处理的语义或安全问题，后面的项才是体验和现代化问题。

### P0-1. “保存草稿”名不副实，实际上仍然执行完整校验

现状：

- `builder.vue` 的保存逻辑在落库前始终调用 `postCodegenValidateApi({ config_json: json })`，并且校验失败就中断保存。
- `/admin/codegen/validate` 只接受 `config_json`，没有任何“草稿模式”参数。
- `CodegenService.validate()` 固定调用 `parser.validate(parsed)`。
- 但 `ConfigParser.validate()` 明明已经支持 `require_fields=False`，注释里也明确写了“草稿保存时为 False，生成前校验时为 True”。

直接后果：

1. 前端按钮写的是“保存草稿”，行为却是“必须完整通过生成前校验才能保存”。
2. 用户无法逐步搭结构，必须把字段、资源、模块等一次配全。
3. Web、HTTP、CLI 对“draft”语义全都没有真正兑现。

证据：

- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue:302`
- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue:831`
- `backend/app/api/admin/codegen.py:464`
- `backend/app/services/system/codegen_service.py:293`
- `backend/app/codegen/config_parser.py:260`
- `backend/app/codegen/config_parser.py:264`
- `backend/app/codegen/config_parser.py:271`

### P0-2. 删除配置过于危险，已生成配置也能被直接删除

现状：

- 列表页永远显示删除操作。
- 管理端删除 API 直接执行 `service.delete(id)`。
- CLI `codegen delete` 也只是二次确认，然后直接删配置记录。
- `CodegenConfig` 模型里已经有 `generated_files`、`last_generated_at`、`manifest_present` 等状态，但删除动作没有基于这些状态做任何保护。

直接后果：

1. 已生成或已应用的配置仍可被直接删除。
2. 数据库配置记录消失后，manifest、版本历史、文件系统状态仍可能残留，后续回滚/追踪失真。
3. Web 和 CLI 都存在同样风险。

证据：

- `frontend/apps/web-antd/src/views/admin/system/codegen/index.vue:101`
- `frontend/apps/web-antd/src/views/admin/system/codegen/data.ts:171`
- `backend/app/api/admin/codegen.py:192`
- `backend/app/cli.py:1385`
- `backend/app/models/system/codegen_config.py:86`

### P0-3. Web、API、CLI 对“预设模板”采用了三套不同模型

现状：

- 后端 `/presets` 是动态扫描 `backend/app/codegen/templates/presets/*.yaml`。
- 预设目录里当前实际有：`simple`、`tree`、`dual_scope`、`workflow`、`sub_form_embedded`、`sub_form_standard`、`sub_form_erp`。
- 前端 `PresetSelectModal.vue` 却把卡片列表写死为 5 张，不会自动展示新增模板。
- CLI `codegen init -t ...` 也只支持 4 个固定选项。
- CLI `generate --template-type master-sub` 还错误映射到 `dual_scope`，与目录现状不一致。

直接后果：

1. 新增 preset 文件后，API 能看到，UI 和 CLI 看不到。
2. `master-sub` 语义与 `dual_scope` 语义明显不等价，容易误导执行者。
3. 模板体系不能作为正式平台能力维护，只能靠人工同步三处代码。

证据：

- `backend/app/api/admin/codegen.py:334`
- `backend/app/cli.py:725`
- `backend/app/cli.py:1532`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/PresetSelectModal.vue:34`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/PresetSelectModal.vue:96`
- `backend/app/codegen/templates/presets/`

### P0-4. ExpertModal 与 builder 默认 endpoint 的 data_mode 语义漂移

现状：

- builder 创建 tenant endpoint 时默认写入 `tenant_isolated`。
- `constants.py` 里合法值也包含 `tenant_isolated`。
- 但 ExpertModal 的 `dataModeOptions` 只有 `independent` 和 `cross_tenant`，缺少 `tenant_isolated`。

直接后果：

1. 页面初始化出来的配置值，在专家模式里没有对应选项。
2. 用户打开专家模式后可能被迫把合法值改成另一个值。
3. 前端可视化配置与后端允许值集合不一致。

证据：

- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue:192`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/ExpertModal.vue:187`
- `backend/app/codegen/constants.py:13`

### P0-5. Preview 已经产出 conflicts / warnings，但 UI 几乎没有承载

现状：

- `CodegenService.preview()` 返回 `summary`、`warnings`、`conflicts`。
- `CodePreviewModal` 也把 `summary` 和 `conflicts` 缓存在 store。
- 但 `FileTreePanel` 只显示文件数与 create/modify 计数。
- `CodePreviewPanel` 只显示文件内容或 previewError。
- warnings/conflicts 没有独立信息区，也没有阻断式提示。

直接后果：

1. 用户看到了预览，但看不到真正应该先处理的风险。
2. 与“先审查 diff 再生成”的工作流目标相违背。
3. 预览面板退化成“文件查看器”，而不是“生成风险检查器”。

证据：

- `backend/app/services/system/codegen_service.py:318`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/CodePreviewModal.vue:62`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/FileTreePanel.vue:113`
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/CodePreviewPanel.vue:135`

### P0-6. CLI 输出契约不稳定，不适合脚本化接入

现状：

- `generate --json` 返回 `{ success, files_created, files_modified, errors, ... }`
- `preview --json` 直接返回 preview 原始结果。
- `validate --json` 直接返回 validation 原始结果。
- `list --json` 返回 `{ items }`
- `versions --json` 返回 `{ versions }`
- `show --json` 返回原始 config 对象，不带 success/data 外层
- `import --json` 只返回 `{ id }`
- `duplicate --json` 只返回 `{ id }`
- `delete --json` 返回 `{ success, deleted_id }`
- `export`、`init`、`db import`、`download` 根本没有 `--json`

直接后果：

1. CLI 不能作为稳定的机器接口使用。
2. 自动化脚本必须针对每个命令写不同解析器。
3. Web/API 和 CLI 难以共享统一 contract test。

证据：

- `backend/app/cli.py:680`
- `backend/app/cli.py:916`
- `backend/app/cli.py:997`
- `backend/app/cli.py:1187`
- `backend/app/cli.py:1298`
- `backend/app/cli.py:1337`
- `backend/app/cli.py:1452`
- `backend/app/cli.py:1577`

### P1-7. CLI 的配置来源优先级不统一

现状：

- `generate` 支持 `--stdin > --config > --id/--resource`
- `validate` 支持 `--stdin` 和 `--config`
- `preview` 不支持 `--stdin`
- `download` 只支持 `--id` 或 `--config`，不支持 `--resource`，也不支持 `--stdin`

直接后果：

1. 同一个配置从 stdin 可 generate，不可 preview/download。
2. 使用 resource 管理配置时，download 还要再转成 id 或文件。
3. 命令学习成本升高，CLI 变得不可预测。

证据：

- `backend/app/cli.py:671`
- `backend/app/cli.py:910`
- `backend/app/cli.py:996`
- `backend/app/cli.py:1577`

### P1-8. duplicate 语义不稳，重复复制同一配置可能撞唯一约束

现状：

- `CodegenService.duplicate()` 直接把 `resource` 改成 `${source.resource}_copy`。
- 没有继续探测 `_copy_2`、`_copy_3` 之类的可用资源名。

直接后果：

1. 同一个配置复制第二次时，很容易撞 `resource` 唯一约束。
2. Web 的“复制”按钮和 CLI `duplicate` 都会受影响。

证据：

- `backend/app/services/system/codegen_service.py:250`

### P1-9. 列表页只显示“数据库字段”，没有体现 codegen 的真正状态

现状：

- 列表还是标准 CRUD 表格。
- 主要列是 `name/resource/module/status/generation_count/last_generated_at/last_error`。
- 有 `manifest_present`，但没有被提升成关键视觉状态。
- 行操作是图标式 CellOperation，密度高，可读性差。

直接后果：

1. 用户无法快速区分“草稿 / 已生成 / 已应用 / 可回滚 / 有错误 / manifest 丢失”。
2. 真正重要的状态信号藏在 tooltip 或行操作逻辑里。
3. 页面“看起来不好看”的根本原因，其实是信息架构缺失。

证据：

- `backend/app/api/admin/codegen.py:115`
- `frontend/apps/web-antd/src/views/admin/system/codegen/data.ts:26`
- `frontend/apps/web-antd/src/views/admin/system/codegen/data.ts:134`

### P1-10. Builder 页面不是“现代化不足”，而是“过早暴露所有控制项”

现状：

- 顶部一排放了资源、模块、双语名称、复数名、撤销重做、预览、更多菜单、保存、生成。
- 中间三栏同时放 palette、WYSIWYG、属性编辑。
- 底部再放 scope checkbox、前端模式、字段数、数据库导入、专家模式、预览。
- 专家模式里又有大量能力开关。

直接后果：

1. 信息层级极其拥挤。
2. 基本配置、高级配置、生成前检查三类任务没有分区。
3. 页面给人的“不现代”感，本质是“用户不知道先做什么、当前状态是什么、下一步是什么”。

证据：

- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue:753`
- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue:843`
- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue:861`

### P1-11. validationErrors 只是数量徽标，没有形成可执行的错误清单

现状：

- 错误只记录到 `validationErrors`。
- 生成按钮旁边显示一个 badge 数量。
- 保存失败/生成失败时主要靠 toast。

直接后果：

1. 用户知道“有错”，但不知道错在哪一段结构。
2. 没有按 path/field 跳转到对应字段或面板。
3. 深层配置场景下几乎不可用。

证据：

- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue:77`
- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue:304`
- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue:833`

### P2-12. Palette 点击加入使用 debounce，存在吞点击风险

现状：

- `ComponentPalette.vue` 用 `useDebounceFn` 包裹 emit。

直接后果：

1. 用户快速连点多个控件时，可能只落一个字段。
2. 这是明显的“输入丢失”问题，不应该出现在构建器里。

证据：

- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/ComponentPalette.vue:114`

### P2-13. 新建页/编辑页路由虽然分开，但实际页面标题与工作流状态仍不够干净

现状：

- 路由层已区分 `AdminSystemCodegenNew` 和 `AdminSystemCodegenEdit`。
- 但 builder 组件内部仍是单页承载两个工作流，顶部状态表达不明确，页面视觉上容易让人觉得“编辑和新建混在一起”。

结论：

- 这不是单纯路由 bug。
- 真问题是 builder 内部缺少清晰的“当前模式头部”和“阶段引导”。

证据：

- `frontend/apps/web-antd/src/router/routes/admin/index.ts:117`
- `frontend/apps/web-antd/src/router/routes/admin/index.ts:130`
- `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue:737`

---

## 4. 总体整改原则

### 4.1 先语义，后视觉

先把“草稿、校验、删除、回滚、生成、模板、CLI”这些语义统一，再改 UI。否则只是把错误流程包一层新皮。

### 4.2 Web、API、CLI 共用同一套业务契约

不要让前端、HTTP、CLI 各自拼规则。凡是以下能力，都必须收束到 service 层统一表达：

- 校验模式
- 预设发现
- 资源解析
- 输出结果结构
- 危险操作护栏

### 4.3 代码生成器不是普通 CRUD 页

列表页不能只复用通用 CRUD 表格思维。它本质上是“配置资产 + 生成状态 + 文件系统状态 + 迁移状态”的管理台。

### 4.4 构建器必须渐进披露

新手默认只看到：

1. 基本信息
2. 字段结构
3. 预览与生成

只有确实需要时，再进入高级配置。

### 4.5 任何危险操作都必须有“可解释护栏”

删除、回滚、恢复版本、覆盖生成，都不能只有一个确认弹窗。必须明确告知：

- 当前状态
- 会影响什么
- 为什么允许或不允许
- 下一步应该做什么

---

## 5. 执行范围与非目标

### 5.1 本次必须完成

1. 草稿/校验/生成语义收口。
2. 删除/回滚/版本恢复安全护栏。
3. CLI 与 Web/API 的 preset / source / json contract 统一。
4. 列表页重做信息架构。
5. builder 页面重做布局与错误反馈机制。
6. preview 面板补 conflicts/warnings/summary 承载。
7. 测试矩阵补齐。

### 5.2 本次明确不做

1. 不重写 code generator 内核模板引擎。
2. 不修改普通 CRUD adapter 的全局行为。
3. 不把代码生成器开放到非 DEBUG 模式。
4. 不把所有页面改成全新设计系统，只在 codegen 局部重构。

---

## 6. 后端语义整改方案

### 6.1 把 validate 明确拆成两种模式

#### 目标

实现真正的两套校验语义：

1. `draft` 校验：允许字段未完成，允许部分结构未补齐，只校验格式合法性和最关键主键字段。
2. `generate` 校验：必须完整通过，才允许生成。

#### 方案

1. 在 `CodegenValidateBodySchema` 新增 `mode` 字段：
   - `draft`
   - `generate`
2. 在 `CodegenService.validate()` 新增参数：
   - `mode: Literal["draft", "generate"] = "generate"`
3. 内部调用 `parser.validate(parsed, require_fields=(mode == "generate"))`
4. Web builder 保存按钮改调用 `mode: "draft"`
5. generate 前校验继续走 `mode: "generate"`
6. CLI `validate` 新增：
   - `--mode draft|generate`
   - 默认 `generate`

#### 验收

1. 一个只有 `resource/module/display_name`、但还没配 fields 的配置，可以“保存草稿”。
2. 同一配置不能直接 generate。
3. UI 上按钮文案与行为一致。

### 6.2 删除改成受保护的归档语义，不再允许直接硬删已生成配置

#### 目标

删除规则必须区分三类：

1. 纯草稿且从未生成：允许直接删除。
2. 已生成/已应用且仍有 manifest 或 generated_files：默认禁止直接删除。
3. 已回滚且无 manifest：允许删除，但要保留版本审计说明。

#### 方案

1. 在 service 层新增 `can_delete_config()` 或 `assert_safe_delete_config()`
2. 判断维度至少包含：
   - `status`
   - `manifest_present`
   - `generated_files`
   - `last_generated_at`
3. `/configs/{id}` 删除接口改成：
   - 不安全时返回 409 + 结构化 reason/code/message
4. CLI `codegen delete` 同步复用这套判断
5. 前端列表页删除按钮改为：
   - 对不可删项显示 disabled + tooltip
   - 若要“清理已回滚配置”，显示明确文案

#### 建议的 reason code

- `draft_only_safe`
- `manifest_present_blocked`
- `generated_state_blocked`
- `must_rollback_first`

### 6.3 duplicate 需要稳定命名策略

#### 目标

复制同一配置多次时不再撞唯一约束。

#### 方案

1. `resource` 改成依次尝试：
   - `resource_copy`
   - `resource_copy_2`
   - `resource_copy_3`
2. `name` 同步递增，避免页面里多条“副本”完全同名
3. Web 和 CLI 不再各自兜底，统一走 service

### 6.4 preset 元数据升级为正式后端能力

#### 目标

不要再让前端和 CLI 各自猜 preset。

#### 方案

1. `/presets` 不只返回名字，改为返回结构化元数据：
   - `name`
   - `category`
   - `label_zh`
   - `label_en`
   - `description_zh`
   - `description_en`
   - `tags`
   - `recommended_for`
2. 元数据来源：
   - 优先从 preset yaml 头部 meta 段读取
   - 没有 meta 时按文件名兜底
3. 前端 Preset Gallery 和 CLI `presets list` 共用这份元数据

### 6.5 preview / generate / rollback 结果结构要稳定

#### 目标

给 Web 和 CLI 一套统一 envelope，而不是每个命令自定义输出形状。

#### 建议结构

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {}
}
```

其中：

- `preview.data` 放 `files/summary/warnings/conflicts`
- `validate.data` 放 `valid/errors/warnings/mode`
- `generate.data` 放 `files_created/files_modified/conflicts/errors/...`
- `rollback.data` 放 `files_deleted/files_modified/errors/...`

#### 注意

HTTP 端可保留现有响应外层 `success(data=...)` 形式，但 service 内部和 CLI 层应尽量用同一数据结构，避免重复拼装。

---

## 7. CLI 整改方案

### 7.1 统一配置来源优先级

所有“读取配置”的命令统一采用：

`--stdin > --config > --id > --resource`

#### 必须补齐的命令

1. `preview` 增加 `--stdin`
2. `download` 增加 `--stdin`、`--resource`
3. `show` 可选支持 `--resource`
4. `export` 保留 `--id|--resource` 即可，但错误输出要与其它命令一致

### 7.2 CLI JSON 输出一律统一 envelope

#### 当前必须修的命令

1. `show --json`
2. `import --json`
3. `duplicate --json`
4. `versions --json`
5. `list --json`
6. `download` 增加 `--json` 时至少返回元数据而不是混合 stdout 文本

#### 建议规范

```json
{
  "success": true,
  "data": {
    "...": "..."
  },
  "error": null
}
```

错误时：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "config_not_found",
    "message": "Config not found"
  }
}
```

### 7.3 CLI 需要正式支持 preset 发现，不再硬编码

#### 新命令建议

1. `novusai codegen presets list`
2. `novusai codegen presets show --name xxx`
3. `novusai codegen init --template xxx`

#### 改法

1. `init` 的 choice 不再硬编码
2. 改成运行时扫描 preset 目录或直接复用后端 preset loader
3. 废弃 `generate --template-type master-sub`

#### 废弃策略

1. 当前先保留 `--template-type` 但打印 deprecated warning
2. `master-sub` 直接移除或映射到真正存在的新 preset
3. 文档与帮助文本同步更新

### 7.4 CLI delete / rollback 必须复用 Web 的安全策略

CLI 不是内部后门，不能比 Web 更危险。

#### 方案

1. `codegen delete` 调用统一 service guard
2. 已生成配置删不掉时，CLI 应该输出：
   - 当前状态
   - 阻断原因
   - 建议先执行什么命令

建议文案：

```text
Config cannot be deleted because manifest entry still exists.
Run `novusai codegen rollback --id <id>` first.
```

### 7.5 CLI contract test 要从 smoke 升级成 matrix

当前 `test_cli_smoke.py` 只覆盖了一部分 not found 和 generate JSON 冒烟，还不够。

必须新增：

1. `validate --mode draft|generate`
2. `preview --stdin`
3. `download --resource`
4. `init` 动态 preset 发现
5. 各命令 `--json` 结构一致性
6. delete 安全阻断
7. duplicate 多次复制命名稳定性

---

## 8. 管理端列表页整改方案

### 8.1 列表页目标

列表页不是普通 CRUD list，而是 codegen 工作台。它至少要回答这几个问题：

1. 哪些配置只是草稿？
2. 哪些已经生成文件？
3. 哪些已经跑过迁移？
4. 哪些可以回滚？
5. 哪些存在错误？
6. 哪些 manifest 丢了？

### 8.2 推荐布局

保留 table 为主，但顶部增加状态摘要卡，下面的 table 改成 codegen 专用列。

#### 顶部摘要卡

至少 5 张：

1. 草稿数
2. 已生成数
3. 已应用数
4. 可回滚数
5. 异常数

#### 表格主列建议

1. 配置
   - `name`
   - `display_name`
   - `resource`
   - `module`
2. 生命周期
   - `status`
   - `manifest_present`
   - `generation_count`
3. 最近动作
   - `last_generated_at`
   - `last_error`
4. 操作
   - 编辑
   - 生成
   - 回滚
   - 下载 ZIP
   - 复制
   - 删除

### 8.3 交互细节

1. `manifest_present` 不能藏在逻辑里，要显示成明确 tag：
   - `Manifest OK`
   - `No Manifest`
2. 删除按钮对不可删项 disabled，不要等点进弹窗才知道
3. 行内操作不要全是图标，至少“Generate / Rollback / More”要有文字
4. `last_error` 不应直接一长串 text，可做“错误摘要 + hover / drawer 查看”

### 8.4 视觉方向

不是换一个花哨皮肤，而是做得更像“资产管理 + 生成流水线台账”：

1. 顶部摘要卡使用明确状态色
2. 表格行加轻量状态条/角标
3. 操作按钮采用主次分层，不要 6 个等权图标塞一排

---

## 9. Builder 页面整改方案

### 9.1 目标

把“单页塞满所有控制项”的模式改成“分层工作流”。

### 9.2 新的信息架构

推荐拆成 4 个稳定区域：

1. 顶部工作流头部
2. 左侧结构区
3. 中央可视化区
4. 右侧检查与属性区

#### A. 顶部工作流头部

只放最关键内容：

1. 页面标题
   - 新建配置
   - 编辑配置
2. 当前状态 tag
   - Draft / Generated / Applied / Rolled Back
3. 主要 CTA
   - 保存草稿
   - 预览
   - 生成
4. 次级入口
   - 更多菜单

不再把 `resource/module/display_name/display_name_en/resource_plural` 全塞在最上面一行。

#### B. 左侧结构区

整合为：

1. 基本信息卡
2. 字段结构卡
3. 页面范围/端侧卡

#### C. 中央可视化区

保留所见即所得，但要加“空状态引导”：

1. 还没有字段时，显示推荐起手模板
2. 支持从 preset 一键填充基本结构

#### D. 右侧检查与属性区

右侧改成双状态：

1. 选中字段时显示属性编辑
2. 未选中字段时显示“配置检查面板”
   - 草稿校验结果
   - 生成前校验结果
   - warnings
   - conflicts

### 9.3 ExpertModal 的定位调整

ExpertModal 不该再承担“补足核心配置”的职责。

它只应该容纳：

1. 关系配置
2. 工作流
3. 树形结构
4. detail group
5. clone / batch / menu / operation options

同时修复 `data_mode` 选项集合，与常量保持一致。

### 9.4 保存与生成动作的文案/行为

#### 保存

按钮保留“保存草稿”，但必须真的走 draft 校验。

#### 生成

生成前流程改成：

1. 先跑 generate 校验
2. 生成确认弹窗展示：
   - resource
   - 将写入的文件数
   - conflicts 数
   - 是否自动迁移
3. 生成完成后弹结果抽屉，而不是只靠 toast

### 9.5 错误反馈机制

validation errors 改为“错误列表面板”：

每条错误至少包含：

1. message
2. path
3. field
4. “定位”按钮

如果能定位到字段，就自动选中字段并滚动到属性面板。

---

## 10. Preview / Code Review 面板整改方案

### 10.1 目标

把它从“文件查看器”升级成“生成前审查器”。

### 10.2 顶部摘要区

在 modal 顶部新增摘要条：

1. 新建文件数
2. 修改文件数
3. 后端文件数
4. 前端文件数
5. 总行数
6. conflicts 数
7. warnings 数

### 10.3 左侧文件树增强

文件树要支持：

1. 仅看 conflicts
2. 仅看 modified
3. 按 backend/frontend 过滤

### 10.4 右侧内容区增强

1. 文件顶部显示风险标签：
   - `Conflict`
   - `Warning`
   - `Create`
   - `Modify`
2. 当 preview 有全局 warnings/conflicts 时，右侧默认先展示“问题摘要”tab，而不是直接落到第一份文件

### 10.5 生成按钮前置校验

如果 preview 已有 conflicts：

1. 默认不能直接 generate
2. 或者至少在 generate confirm 中明确提示并要求二次确认

---

## 11. Preset 体系整改方案

### 11.1 Web 端

`PresetSelectModal` 改为真正的 Preset Gallery：

1. 卡片数据来自后端动态元数据
2. 支持 category/tag/filter
3. 支持“空白配置”作为特殊第一项
4. 支持搜索 preset name / label / description

### 11.2 CLI

新增：

1. `novusai codegen presets list`
2. `novusai codegen presets show --name`

### 11.3 预设文件规范

每个 preset yaml 顶部增加 meta：

```yaml
meta:
  label_zh: 子表单（标准）
  label_en: Sub Form Standard
  description_zh: 适用于一主多从标准子表单场景
  description_en: For standard master-detail sub form scenarios
  category: sub_form
  tags: [master_detail, sub_form]
```

---

## 12. 测试方案

### 12.1 后端单测

至少新增：

1. `validate(mode=draft)` 允许无 fields
2. `validate(mode=generate)` 无 fields 报错
3. delete guard:
   - draft 可删
   - generated + manifest 不可删
   - rolled_back + no manifest 可删
4. duplicate 多次复制资源名递增
5. preset loader 能识别新增 preset meta

### 12.2 CLI 测试

至少新增：

1. 所有 `--json` 命令结构一致性
2. `preview --stdin`
3. `download --resource`
4. `init` / `presets list` 动态发现
5. delete 阻断信息
6. validate draft/generate 双模式

### 12.3 前端单测 / 组件测试

至少新增：

1. Preset Gallery 动态渲染
2. 保存草稿使用 `mode=draft`
3. 生成使用 `mode=generate`
4. validation error list 点击定位
5. preview warnings/conflicts 展示
6. 不可删状态下删除按钮 disabled

### 12.4 浏览器验收

在用户已启动的环境中至少走一遍：

1. `/admin/system/codegen`
2. `/admin/system/codegen/new`
3. `/admin/system/codegen/:id/edit`

验收脚本重点：

1. 草稿可保存但不可生成
2. generate 前能看到 conflict/warning
3. 已生成配置不允许直接删除
4. 可从 preset gallery 看到动态新模板
5. CLI 和 Web 对同一配置状态一致

---

## 13. 推荐实施顺序

### Phase 1. 语义与安全

1. validate 双模式
2. delete guard
3. duplicate 唯一命名
4. ExpertModal data_mode 修正

### Phase 2. 契约统一

1. preset 元数据与发现机制统一
2. CLI source priority 统一
3. CLI JSON envelope 统一
4. preview/generate/rollback 结果结构收口

### Phase 3. UI 重构

1. 列表页状态工作台化
2. Builder 页面重做布局
3. Preview 面板增强
4. 错误面板与定位能力

### Phase 4. 验收与文档

1. 补测试矩阵
2. 更新 CLI 帮助文档
3. 更新 codegen 使用说明

---

## 14. 具体执行清单

下面这份清单可以直接当 Kimi 的任务拆分。

### A. 后端 / API

1. 修改 `backend/app/schemas/codegen.py`
   - 给 `CodegenValidateBodySchema` 增加 `mode`
2. 修改 `backend/app/services/system/codegen_service.py`
   - `validate()` 支持 `mode`
   - 增加删除安全判断
   - 修复 duplicate 命名
   - 抽 preset loader
3. 修改 `backend/app/api/admin/codegen.py`
   - `/validate` 支持 mode
   - `/configs/{id}` 删除前校验
   - `/presets` 返回结构化元数据

### B. CLI

1. 修改 `backend/app/cli.py`
   - `validate --mode`
   - `preview --stdin`
   - `download --stdin --resource`
   - `presets list/show`
   - `init` 动态模板发现
   - JSON envelope 统一
   - 删除走安全护栏
2. 修改 `backend/tests/codegen/test_cli_smoke.py`
   - 扩成 contract tests

### C. 前端列表页

1. 修改 `frontend/apps/web-antd/src/views/admin/system/codegen/index.vue`
2. 修改 `frontend/apps/web-antd/src/views/admin/system/codegen/data.ts`
3. 如有必要新增局部组件：
   - `CodegenStatusOverview.vue`
   - `CodegenRowActions.vue`

### D. 前端 Builder

1. 修改 `frontend/apps/web-antd/src/views/admin/system/codegen/builder.vue`
2. 修改 `frontend/apps/web-antd/src/views/admin/system/codegen/modules/ExpertModal.vue`
3. 修改 `frontend/apps/web-antd/src/views/admin/system/codegen/modules/PresetSelectModal.vue`
4. 修改 `frontend/apps/web-antd/src/views/admin/system/codegen/modules/ComponentPalette.vue`
5. 新增：
   - `CodegenValidationPanel.vue`
   - `CodegenBuilderHeader.vue`

### E. Preview 面板

1. 修改 `frontend/apps/web-antd/src/views/admin/system/codegen/modules/CodePreviewModal.vue`
2. 修改 `frontend/apps/web-antd/src/views/admin/system/codegen/modules/FileTreePanel.vue`
3. 修改 `frontend/apps/web-antd/src/views/admin/system/codegen/modules/CodePreviewPanel.vue`
4. 如有必要新增：
   - `CodegenPreviewSummaryBar.vue`
   - `CodegenPreviewIssueList.vue`

---

## 15. 完成定义

只有同时满足以下条件，才算本方案完成：

1. “保存草稿”真的允许半成品配置保存。
2. “生成”只能在完整校验通过后执行。
3. 已生成/已应用配置不能被 Web 或 CLI 直接删除。
4. preset 新增一个 yaml 文件后，Web 和 CLI 都能自动发现。
5. CLI `--json` 输出结构统一。
6. preview 可以直接看到 conflicts 和 warnings。
7. 列表页能一眼看出哪些配置可回滚、哪些异常、哪些只是草稿。
8. builder 页面主流程明显更清晰，不再靠 toast + badge 勉强使用。
9. 对应单测 / CLI 测试 / 浏览器验收全部补上。

---

## 16. 给 Kimi 的执行要求

1. 不要先做视觉换皮，先按 Phase 1 和 Phase 2 修语义与契约。
2. 不要新起前后端服务，直接基于现有代码修改。
3. 不要发散到 codegen 内核重写，本次只收口 Web/API/CLI/工作流。
4. 不要引入新的全局状态管理方案，继续沿用当前 store / service / controller 体系。
5. 所有新增文案必须走 i18n。
6. 所有危险动作必须有明确 reason code 和前端可解释提示。

如果要进一步压缩实施风险，建议按下列 PR 切分：

1. `codegen-semantic-safety`
2. `codegen-cli-contract-unification`
3. `codegen-admin-ui-rework`

