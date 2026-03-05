# M590 详细里程碑（V2）- 插件依赖清空重装 + 全量启停与功能回归

## 1. 目标与边界

- 目标 1：删除插件相关依赖（Python + npm），验证“插件启用流程可自动回装依赖”。
- 目标 2：覆盖全部插件的生命周期操作（至少启用/禁用/修复），并验证状态一致性。
- 目标 3：覆盖插件核心业务能力，确认关键页面/API 可用且无阻断错误。
- 目标 4：覆盖插件系统关键入口：`marketplace 安装`、`repair`、`uninstall`、`菜单挂载变更`。
- 边界约束：对象存储真实密钥仅保证 `qiniu-kodo`，其余存储驱动做“生命周期 + 配置可见性 + API 非 500”验证。

## 2. 插件清单与测试分组

| 插件 | 类型 | 基线状态 | 主要验证维度 |
|---|---|---|---|
| aliyun-oss | 存储驱动 | installed | 生命周期、驱动挂载、配置可见性 |
| amazon-s3 | 存储驱动 | disabled | 生命周期、驱动挂载、配置可见性 |
| tencent-cos | 存储驱动 | disabled | 生命周期、驱动挂载、配置可见性 |
| qiniu-kodo | 存储驱动 | enabled | 生命周期、驱动挂载、真实读写链路 |
| storage-migration | 管理页 + 任务 | enabled | 菜单挂载、影响分析、多语言、任务流 |
| netdisk | 页面 + API + task + skill | enabled | 文件流/分享/配额/管理统计 |
| weather-widget | API + skill | enabled | 天气 API、地理编码、前后端展示 |
| novusdoc | 文档编辑器 | enabled | 文档 CRUD、搜索、标签、导出、AI 接口 |
| novusdoc-pro | 协作增强 | enabled | 评论、版本、分享、成员、模板、导出、降级模式 |
| novus-crud-code | 低代码管理 | enabled | 项目/Schema/记录 CRUD、入口页面、AI 聊天接口 |

## 3. 生命周期全量回归矩阵（每个插件）

统一执行序列（每个插件至少一次）：

1. `disable`（若当前 enabled）
2. 校验 DB 状态变更 + `/admin/plugins/slots`/菜单变更（适用前端插件）
3. `enable`（触发依赖安装）
4. 校验 DB 状态 + 扩展点加载 + 依赖满足
5. `repair`（enabled 或 error 状态执行）
6. 校验 `repair` 结果与健康状态

额外入口覆盖：

1. `marketplace install`：选一个无业务数据依赖插件做安装链路校验（预览安装 + 确认安装）。
2. `uninstall`：选一个无关键业务数据插件执行卸载，再执行安装/启用恢复。
3. `menu 挂载变更`：对 `storage-migration`、`novusdoc`、`novus-crud-code`做“启用出现/禁用消失”对比验证。

## 4. T2-T5 详细执行任务

## T2 清空插件依赖（Python + npm）

1. 生成“启用中插件列表 + 依赖映射 + 回滚快照”。
2. 按依赖反向顺序禁用插件（先 `novusdoc-pro` 再 `novusdoc`）。
3. 卸载 Python 依赖集合：
   `Pillow aiofiles alibabacloud-oss-v2 anyio bcrypt boto3 cos-python-sdk-v5 httpx qiniu redis`
4. 卸载 npm 依赖集合（基线 27 项，含 `@tiptap/*`、`@vue-flow/*`、`vxe-table`、`yjs` 等）。
5. 复核：`pip show` / `pip freeze` / `pnpm ls --depth 0`，标注“未卸载原因（被系统依赖保护）”。
6. 输出证据：
   - `dependency_remove_python.log`
   - `dependency_remove_npm.log`
   - `dependency_remove_verify.json`

## T3 重新启用插件并验证自动安装

1. 按拓扑启用顺序执行：
   `aliyun-oss -> amazon-s3 -> netdisk -> novus-crud-code -> novusdoc -> qiniu-kodo -> storage-migration -> tencent-cos -> weather-widget -> novusdoc-pro`
2. 每次启用记录：
   - API 返回体
   - 进度日志关键节点（迁移、pip、npm、扩展注册、hook）
   - 失败时根因与卡点
3. 启用完成后复核：
   - Python 依赖满足（含 marker 逻辑：`novusdoc-pro` 的 `y-py` 在 Windows+Py3.12 场景可跳过）
   - npm 依赖满足
   - 插件最终状态与预期一致
4. 菜单热更新验证（不重启前端）：
   - 启用后菜单出现
   - 禁用后菜单消失
   - 再启用后菜单恢复

## T4 插件功能逐项回归（插件级）

### 4.1 存储驱动插件（aliyun-oss / amazon-s3 / tencent-cos / qiniu-kodo）

1. 生命周期：enable/disable/repair 全通过。
2. 驱动挂载：在存储驱动列表与 `storage-migration` 源/目标下拉中可见。
3. 配置可见性：驱动参数 schema 正常渲染，无空白/报错。
4. `qiniu-kodo` 真值链路：
   - 上传文件
   - 下载/预览
   - 删除
   - 在 netdisk 与存储迁移中交叉验证。

### 4.2 storage-migration

1. 页面加载无 JS 报错（mounted/render）。
2. 影响分析：`GET impact-analysis` 返回完整统计。
3. 驱动多语言：源/目标驱动名使用 i18n key 转换后的展示，不显示裸 key。
4. 任务链路：创建任务 -> 列表可见 -> 详情可查 -> pause/resume/cancel/retry/rollback/source-files 至少覆盖主路径。
5. 菜单行为：启用后菜单出现，禁用后菜单移除。

### 4.3 netdisk

1. 租户文件 API：目录列表、创建文件夹、重命名、删除、回收站恢复。
2. 上传链路：整文件上传 + 下载。
3. 分享链路：创建分享、查看分享列表、撤销分享。
4. 管理端链路：配额列表/更新、统计 API 正常。

### 4.4 weather-widget

1. API：`config/current/forecast/geocoding` 返回成功或可解释业务错误（非 500）。
2. 页面组件：首页天气组件正常渲染，无样式错乱。
3. 城市切换：城市检索后当前天气/预报跟随变更。

### 4.5 novusdoc

1. 页面入口：`/admin/plugins/novusdoc/docs`、`/tenant/plugins/novusdoc/docs` 正常打开。
2. 文档 CRUD：新建、编辑、删除、搜索、标签管理。
3. 导出：html/markdown。
4. AI 接口：至少覆盖 2 个能力（continue + summarize），确认接口路径和鉴权正常。

### 4.6 novusdoc-pro

1. 前置依赖校验：`novusdoc` 启用后方可启用 `novusdoc-pro`。
2. 功能 API：评论、版本、分享、成员、模板、导出。
3. 协作降级验证：在 `y-py` marker 跳过场景下，插件可启用且非协作核心功能可用。
4. 菜单/入口：不破坏 novusdoc 主页面渲染。

### 4.7 novus-crud-code

1. 页面入口：项目列表、项目详情、Schema 设计、数据表单页均可打开。
2. API：项目 CRUD、Schema CRUD、记录 CRUD、关系 CRUD。
3. AI 聊天接口：返回成功或受模型配置限制的可解释错误（非 500）。

## T5 报告与闭环

1. 输出总报告（通过项/失败项/阻断项/外部依赖限制项）。
2. 失败项必须包含：复现步骤、根因、修复建议、是否已修复。
3. 产物清单：
   - `lifecycle_regression_matrix.json`
   - `plugin_functional_regression_report.md`
   - `marketplace_repair_uninstall_report.md`
4. MCP 任务状态同步：T2/T3/T4/T5 分别在完成后立即更新 `completed + notes`。

## 5. 证据目录约定

- `docs/reports/m590/results/t2_*`
- `docs/reports/m590/results/t3_*`
- `docs/reports/m590/results/t4_*`
- `docs/reports/m590/results/t5_*`

每个文件必须包含：

- 执行时间（UTC+8）
- 请求路径/命令
- 返回码
- 结论（pass/fail/block）

