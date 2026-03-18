# CRUD 与 CLI 全面审计提示词

> 将本提示词提供给另一个 AI，用于对 NovusAI SaaS 项目中的 CRUD 代码和 CLI 进行全面审计。

---

## 一、审计目标

请对当前项目的 **CRUD 体系** 和 **CLI 体系** 进行全面审计，覆盖后端、前端、Codegen 生成逻辑、CLI 命令及其实现。审计应基于实际代码阅读，不做推测；输出结构化报告，列出问题、影响等级及修复建议。

---

## 二、审计范围

### 2.1 CRUD 体系

| 层级 | 路径 | 关注点 |
|------|------|--------|
| 后端 Model | `backend/app/models/` | 继承关系、`__filterable__`/`__sortable__`/`__selectable__`/`__ai_policy__`、`__delete_deps__`、外键约束 |
| 后端 Schema | `backend/app/schemas/` | 基类继承、Create/Update/Response、字段校验、序列化 |
| 后端 Repository | `backend/app/repositories/` | 基类继承、查询协议（filter/sort/page）、软删除、租户隔离 |
| 后端 Service | `backend/app/services/` | 业务逻辑、钩子、批量操作、事务边界 |
| 后端 Controller | `backend/app/api/` | 权限装饰器、动作声明、路由注册、异常处理 |
| 前端 data.ts | `frontend/apps/web-antd/src/views/*/data.ts` | `useColumns`、`useGridFormSchema`、`useFormSchema`、辅助函数使用 |
| 前端 list/index | `frontend/apps/web-antd/src/views/*/index.vue` | `useCrudPage`/`useCrudList` 使用、权限、导出/导入 |
| 前端 form | `frontend/apps/web-antd/src/views/*/modules/form.vue` | `useCrudDrawer`、表单校验、提交逻辑 |
| API 层 | `frontend/apps/web-antd/src/api/` | 与后端端点对应、参数格式、响应类型 |

### 2.2 Codegen 系统

| 组件 | 路径 | 关注点 |
|------|------|--------|
| 配置解析 | `backend/app/codegen/config_parser.py` | 校验、constants 合法值、endpoints、relations |
| 模板 | `backend/app/codegen/templates/` | Jinja2 模板正确性、条件分支、命名约定 |
| 生成器 | `backend/app/codegen/generator.py` | 上下文构建、文件写入、冲突处理 |
| 回滚 | `backend/app/codegen/rollback.py` | 回滚逻辑、manifest 一致性 |
| 服务 | `backend/app/services/system/codegen_service.py` | preview/generate/rollback、版本管理 |
| 前端构建器 | `frontend/apps/web-antd/src/views/admin/system/codegen/` | WYSIWYG、配置存储、预览与生成一致性 |

### 2.3 CLI 体系

| 命令组 | 入口 | 关注点 |
|--------|------|--------|
| 主 CLI | `backend/app/cli.py` | click 子命令、参数校验、错误处理、输出格式 |
| novusai run | `cli.py` → uvicorn | host/port/reload/workers、环境变量 |
| novusai celery | `cli.py` → celery | worker/beat/dev/flower/purge、队列、Windows 模式 |
| novusai db | `cli.py` → alembic | upgrade/revision/current/heads/history/stamp/merge、插件迁移路径 |
| novusai plugin | `cli.py` → plugin_cli | create/validate/pack/list/cleanup、参数传递 |
| novusai license | `cli.py` | generate/verify/keygen、密钥安全 |
| novusai codegen | `cli.py` | generate/preview/validate/rollback/versions/restore/list/show/import/export/delete/duplicate、db tables/columns/import、init/history/download |
| novusai check | `cli.py` | all/db/redis/celery、健康检查 |
| novusai info | `cli.py` | 版本、环境、配置摘要 |
| 插件 CLI | `backend/scripts/plugin_cli.py` | create/validate/pack、模板、参数 |

---

## 三、审计维度与检查项

### 3.1 正确性

- [ ] CRUD 各层职责清晰，无越权（Controller 不写业务逻辑、Service 不直接拼 SQL）
- [ ] 查询协议（filter/sort/page）前后端一致，参数命名（snake_case）正确
- [ ] 分页：`query.size` 与 `query.page_size` 使用正确
- [ ] 租户隔离：`TenantModel`/`TenantRepository`/`TenantService` 正确注入 `tenant_id`
- [ ] 软删除：`is_deleted` 过滤、恢复逻辑正确
- [ ] 外键级联：`__delete_deps__` 配置与实际依赖一致
- [ ] Codegen 生成代码与手写 CRUD 模式一致
- [ ] CLI 各命令参数组合合理，互斥选项检查（如 `--resource` 与 `--id` 二选一）

### 3.2 一致性

- [ ] 命名：Model/Schema/Repository/Service/Controller 命名一致（如 `Notice`/`NoticeCreate`/`NoticeRepository`）
- [ ] 路由前缀、资源路径与菜单配置一致
- [ ] 前端 API 路径与后端路由一致
- [ ] i18n key 使用 `$t()`/`t()`，无硬编码
- [ ] Codegen 模板与手写代码风格一致（缩进、导入顺序、注释规范）

### 3.3 安全性

- [ ] Controller 所有端点有 `@action_*` 权限装饰
- [ ] 敏感操作（删除、批量操作）有权限校验
- [ ] CLI 中 `license keygen` 等涉及密钥的命令无敏感信息泄露
- [ ] 输入校验：Schema 校验、CLI 参数校验、防注入

### 3.4 错误处理

- [ ] Service 抛出的业务异常（`NotFoundException`/`BusinessException`）被正确捕获并返回统一格式
- [ ] CLI 错误信息清晰，`sys.exit(1)` 使用正确
- [ ] 前端 `catch (err: unknown)`，`err instanceof Error` 判断
- [ ] Codegen 生成失败时回滚或明确报错

### 3.5 可维护性

- [ ] 无重复代码，公共逻辑抽取到 composable/service
- [ ] 无魔法字符串，使用常量/枚举
- [ ] 注释中英双语（若有必要）
- [ ] CLI 帮助信息完整（`--help` 输出清晰）

### 3.6 边界与兼容

- [ ] 空列表、空分页、零条记录时的 UI/API 行为
- [ ] 大批量操作（导入、批量删除）的超时与限流
- [ ] Windows vs Linux：CLI 路径、换行符、celery pool
- [ ] Codegen 生成文件与现有文件冲突时的策略（覆盖/跳过/合并）

---

## 四、输出格式要求

请按以下结构输出审计报告：

```markdown
# CRUD 与 CLI 全面审计报告

## 1. 执行摘要
- 审计时间、范围
- 发现的问题总数（按严重程度分类）
- 优先修复建议

## 2. CRUD 体系审计
### 2.1 后端
- 问题列表（每个问题：文件:行号、描述、影响、建议）
### 2.2 前端
- 同上
### 2.3 Codegen
- 同上

## 3. CLI 体系审计
### 3.1 主 CLI (app/cli.py)
- 问题列表
### 3.2 插件 CLI (scripts/plugin_cli.py)
- 问题列表
### 3.3 其他 CLI 相关
- 同上

## 4. 跨模块一致性问题
- 前后端契约、命名、配置一致性

## 5. 附录
- 审计方法（文件列表、阅读顺序）
- 未覆盖区域及原因
```

---

## 五、参考文件

审计时可参考以下项目文档以理解规范：

- `.cursor/skills/novusai-saas/SKILL.md` — 全栈开发规范
- `.cursor/skills/novusai-saas/references/backend-crud.md` — 后端 CRUD 步骤
- `.cursor/skills/novusai-saas/references/frontend-crud.md` — 前端 CRUD 模式
- `.cursor/skills/novusai-saas/references/platform-infrastructure.md` — 平台基础设施
- `docs/guides/backend-development.md` — 后端开发指南
- `backend/tests/codegen/` — Codegen 测试用例（可作为正确性基准）

---

## 六、审计方法建议

1. **自底向上**：Model → Schema → Repository → Service → Controller → API → 前端
2. **抽样 + 全量**：选取 2–3 个完整 CRUD 模块做深度审计，其余做模式一致性检查
3. **CLI 逐命令**：按 `novusai --help` 列出的子命令逐一审计
4. **Codegen 端到端**：从配置 YAML → 解析 → 模板渲染 → 生成文件，验证链路正确性
5. **测试驱动**：运行 `pytest backend/tests/` 和 `pytest backend/tests/codegen/`，将失败用例纳入问题列表
