# NovusAI SaaS 全面审计报告（第二轮 · 细化版）

**审计基准日期**：2026-03-31  
**范围**：后端 `backend/app`、插件与脚本、CI、Dockerfile、前端 `web-antd` 关键 XSS 面。  
**说明**：本报告按计划在 `docs/acceptance/` 落地；**未修改** Cursor 计划文件本身。

---

> **退役说明（2026-04）**：`data_intelligence` 能力链路（`readonly_executor.py`、`sql_safety.py` 等模块及 `SkillTypeEnum.DATA_INTELLIGENCE`）已退役，不再被构建或调用。文中提到的相关文件/路径仅保留为历史审计记录，项目中已删除该功能。

## 0. 审计完成标准（DoD）

| 维度 | 证据形式 | 风险标注 | 产出 |
|------|----------|----------|------|
| 错误处理 | `rg` 命中文件 + 行上下文 | 泄露/完整性/可用性 + 利用前提 | 附录 A + 建议 |
| 动态 SQL | `text(f"...")` 全量表 | 注入/越权 | 附录 B |
| 多租户/IDOR | 路由 + Service 抽样 | 跨租户读取 | 第 3 节 |
| CORS/浏览器 | `main.py` 片段 | CSRF/凭证泄露 | 第 4 节 |
| 危险执行面 | 执行器与测试引用 | RCE/供应链 | 第 5 节 |
| 前端 XSS | `v-html` 文件 + 数据流 | 存储/反射 XSS | 附录 C |
| CI/类型 | `ci.yml` vs `pyproject.toml` | 配置漂移 | 附录 D |
| 运维探针 | 中间件 + 测试 | 误切流量 | 第 9 节 |

---

## 1. 后端：异常吞没与可观测性

### 1.1 结论摘要

- **`except Exception` + `pass`** 仍广泛存在（见附录 A）。其中 **RAG [`processor.py`](backend/app/ai/rag/processor.py)**、**插件 lifecycle**、**SSL 任务**、**ws_config** 等需按「热路径 / 一次一告警」分级处理，不宜一次性改为 `warning`。
- **`bare except`**：在 `backend/app` 内本次检索 **未命中** 裸 `except:`（好事）。
- **`asyncio.CancelledError`**：计划在 `gather`/`create_task` 密集处（如 [`retriever.py`](backend/app/ai/rag/retriever.py)）做 **专项代码审阅**（本轮以报告登记为主）。
- **本次已改**：[`http_executor.py`](backend/app/ai/tools/executors/http_executor.py) 中 JSONPath 提取失败由 `pass` 改为 `logger.debug`（低噪、可诊断）。

### 1.2 trace_id

- 中间件 [`TraceIdMiddleware`](backend/app/middleware/trace.py) 与日志格式 `[trace_id=]` 已在多模块使用；建议在 **后台 `create_task` 写审计**（如 [`operation_log_service.py`](backend/app/services/system/operation_log_service.py)）失败路径补充 **显式 trace 传播**（P2）。

---

## 2. 数据层：动态 SQL 与迁移

### 2.1 结论（附录 B）

- **[`plugins/backup.py`](backend/app/plugins/backup.py)** / **[`lifecycle.py`](backend/app/plugins/lifecycle.py)**：`table_name` / `tbl` 来自 `information_schema` 或残留表集合，并经过 **`_is_safe_plugin_table` / `_is_safe_plugin_table_name`** 过滤后再进入 `text(f'...')` — **设计合理**，残留风险在于 **过滤函数是否覆盖全部畸形名**（建议单元测试覆盖边界）。
- **[`core/database.py`](backend/app/core/database.py)**：`DATABASE_NAME` 来自配置 — **非请求输入**。
- **[`readonly_executor.py`](backend/app/ai/data_intelligence/readonly_executor.py)**：`statement_timeout` 由 `timeout_seconds * 1000` 拼接 — 需保证 **`timeout_seconds` 为受控整数**（配置/服务层，非用户原始字符串）；建议在类型与校验处标注（P2）。

### 2.2 Ruff 与迁移

- [`pyproject.toml`](backend/pyproject.toml) `ruff exclude` 含 **`migrations/versions`**：CI `ruff check app/` **不覆盖**生成迁移；须依赖 **[统一迁移验证](unified-scope-migration-verification.md)** 与人工 review（**P1 流程**，非单点代码修复）。

---

## 3. 多租户、鉴权与 IDOR（抽样）

### 3.1 抽样示例（正向模式）

- **[`tenant/execution_decisions.py`](backend/app/api/tenant/execution_decisions.py)**：`ExecutionDecisionService(db, tenant_admin.tenant_id)` + `get_by_id(decision_id)` — **租户 ID 从认证上下文注入**，符合「按 ID 取详情」安全模式。

### 3.2 审计建议（P1）

- 对 **`/admin/*`** 中带 `tenant_id` 查询参数的接口，核对 **是否禁止跨租户枚举**（仅平台角色可访问时是否仍有业务约束）。
- 对 **`/api/user/*`**，核对 **终端用户**仅能访问本企业资源（与 [`user-endpoint`](.cursor/skills/user-endpoint/SKILL.md) 一致）。
- 输出 **「高风险路由表」**：无 `@action_*` / 无 `tenant_id` 过滤的 **人工清单**（需后续迭代专门跑一轮）。

---

## 4. CORS / Cookie / CSRF

### 4.1 当前行为（证据）

[`backend/app/main.py`](backend/app/main.py)（约 507–516 行）：

- `CORSMiddleware`：`allow_origins=["*"]`，`allow_credentials=True`，`allow_methods=["*"]`，`allow_headers=["*"]`。
- 注释说明：多租户子域名与自定义域名导致 **静态白名单不可行**。

### 4.2 风险与建议

- **规范层面**：`Access-Control-Allow-Origin: *` 与 `Allow-Credentials: true` 在浏览器模型中 **通常不合法组合**；Starlette/FastAPI 实际响应可能 **回显请求 Origin**（需在目标浏览器复测并写入运维文档）。
- **建议（P1）**：评估 **按租户已验证域名列表反射 Origin**；管理端与用户端 **拆分策略**。
- **CSRF**：若 API **仅 Bearer Token**、无 Cookie 会话，可在安全文档中 **明确「为何 CSRF 风险可接受」**；若存在 Cookie 认证端点，需 **单独评估 SameSite / CSRF Token**（P1）。

---

## 5. 危险执行面

- **HTTP 工具**：[`http_executor.py`](backend/app/ai/tools/executors/http_executor.py) 使用 [`UrlValidator`](backend/app/ai/tools/security.py)、`follow_redirects=False`，与 [`test_http_executor.py`](backend/tests/services/test_http_executor.py) 等测试配合 — **SSRF 面已有意识**（持续跟进去重与 DNS 重绑定即可）。
- **代码执行 / Toolkit**：[code_execution_executor](backend/app/ai/tools/executors/code_execution_executor.py)、[toolkit_executor](backend/app/ai/tools/executors/toolkit_executor.py) — 需 **权限门控 + 资源限额** 与发布评审 checklist（引用现有安全测试）。
- **Celery**：[`celery_app.py`](backend/app/celery_app.py) 动态 `__import__` — **任务模块须在可信路径**（P1 文档化）。

---

## 6. 前端：XSS 与 `v-html`（附录 C）

- **MarkdownRender**：[markdown-render/index.vue](frontend/apps/web-antd/src/components/business/markdown-render/index.vue) — `markdown-it` **`html: false`** + **`DOMPurify.sanitize`** — **偏安全默认**。
- **AIResultPanel**：[AIResultPanel.vue](frontend/apps/web-antd/src/components/business/rich-text-editor/ai/AIResultPanel.vue) — 同上。
- **法律文档**：[legal-document.vue](frontend/apps/web-antd/src/views/user/authentication/legal-document.vue) — **`DOMPurify.sanitize(html)`** 后再 `v-html` — **合理**。

**P2**：为 DOMPurify 配置 **显式 ALLOWED_TAGS/ATTR** 的集中封装，便于审计对比。

---

## 7. 测试与 CI

- **`pytest -x`**：首个失败即停 — **适合 PR 速度**，发布前可考虑 **非 `-x` 夜间任务**（计划中记录）。
- **本轮已实施**：
  - 新增 **[`tests/core/test_readiness_endpoint.py`](backend/tests/core/test_readiness_endpoint.py)**：`/ready` **200** 与 **503**（启动后 mock `async_session_factory`）。
  - CI 新增 **`backend-mypy`** job，`continue-on-error: true`，执行 `mypy app/`（与 [pyproject mypy strict](backend/pyproject.toml) 对齐）。
- **FastAPI 修复**：`/ready` 路由增加 **`response_model=None`**，避免 `JSONResponse | dict` 注解导致 **应用无法创建**（属 **P0 稳定性**）。

---

## 8. 容器与供应链

### 8.1 本轮已实施

- **[`backend/Dockerfile`](backend/Dockerfile)**：`pip install -e ".[dev]"` 改为 **`pip install -e .`**，避免生产镜像装入 dev 依赖。
- **`HEALTHCHECK`**：对 **`api` stage** 使用 `curl` 请求 **`/health`**（镜像已装 `curl`）。

### 8.2 待办（P2）

- **非 root 用户**运行 uvicorn/celery。
- **多阶段构建**减小镜像体积。

---

## 9. 运维契约：探针与中间件

| 检查项 | 结论 |
|--------|------|
| `GET /ready` | 校验 DB `SELECT 1`；失败 **503** + `not_ready` |
| `MaintenanceMiddleware` 豁免 | 含 `/health`、`/ready` |
| `AccessControlMiddleware` 豁免 | 含 `/health`、`/ready` |
| `audit_log` 排除 | 含 `/health`、`/ready` |
| K8s | **liveness** 建议 `/health`；**readiness** 建议 **`/ready`** |

---

## 10. 依赖与许可证（建议）

- 启用 **Dependabot** 或定期 **`pip-audit`**（节奏由团队定，**不阻断**或 **仅高危阻断**）。
- 根 **[LICENSE](LICENSE)** 与 [frontend/LICENSE](frontend/LICENSE) 并存 — 发布说明中标注 **各子项目许可**（P2 文档）。

---

## 11. 前端 i18n（抽样）

- **Tenant `views` 模板内中文**：本次 `rg` 以注释与 AI 英文 `description` 字符串为主；**用户可见硬编码中文**在 tenant AI 大块页面中 **未检出明显模板内中文**（**P2**：对 `description: '...'` 双语字符串统一改 `$t`）。

---

## 附录 A — `except Exception:` + `pass` 清单（仓库快照）

检索式：`except Exception:\n\s*pass`（multiline），**backend** 命中文件（含插件/脚本）：

- `backend/migrations/env.py`（已注释，可选跳过）
- `backend/plugins/slider-captcha/backend/captcha_provider.py`
- `backend/app/ai/tools/executors/http_executor.py`（JSONPath 分支已改为 debug 日志）
- `backend/app/services/common/auth_service.py`（Redis 不可用静默）
- `backend/app/plugins/lifecycle.py`（3 处）
- `backend/app/codegen/migration_helper.py`（2 处）
- `backend/app/codegen/db_introspector.py`
- `backend/app/ai/engine/image_generation.py`
- `backend/app/tasks/ssl_tasks.py`（3 处）
- `backend/app/core/database.py`
- `backend/plugins/storage-migration/backend/services/migration_service.py`（4 处）
- `backend/scripts/plugin_cli.py`
- `backend/app/ai/rag/processor.py`（7 处）
- `backend/app/api/shared/_skill_test.py`
- `backend/app/plugins/sse.py`（连接已断开）
- `backend/app/tasks/agent_batch.py`（3 处）
- `backend/app/sio/ws_config.py`（4 处）

**分类建议**：**P2 静默合理** — SSE/断开、Redis 降级、迁移 env 插件缺失；**P1 需日志** — RAG 核心路径、SSL、agent_batch、storage-migration（按业务严重性微调）。

---

## 附录 B — `text(f"...")` 动态 SQL（`backend/app`）

| 文件 | 用途 | 数据来源判定 |
|------|------|----------------|
| `plugins/lifecycle.py` | `DROP TABLE` | `tbl` 经 `_is_safe_plugin_table_name` |
| `codegen/migration_helper.py` | `DROP TABLE` | codegen 内部表名 |
| `core/database.py` | `CREATE DATABASE` | 配置 `DATABASE_NAME` |
| `ai/data_intelligence/readonly_executor.py` | `statement_timeout` | `timeout_seconds` 数值 |
| `plugins/backup.py` | `SELECT *` | `table_name` 经 `_is_safe_plugin_table` |

---

## 附录 C — `v-html` 与清洗链

| 组件 | 清洗 |
|------|------|
| `markdown-render/index.vue` | `html: false` + DOMPurify |
| `rich-text-editor/ai/AIResultPanel.vue` | MarkdownIt + DOMPurify |
| `user/authentication/legal-document.vue` | DOMPurify on API HTML |

---

## 附录 D — CI 与本地工具链差异

| 工具 | 本地配置 | CI（本轮） |
|------|----------|------------|
| Ruff | `pyproject` + exclude migrations | `ruff check app/` |
| Mypy | `strict = true` | **新增** `backend-mypy`，`continue-on-error: true` |
| Pytest | `addopts -v` 等 | `pytest tests/ -x` |
| 迁移目录 Ruff | 排除 | **未覆盖**，依赖迁移专项验证 |

---

## 本轮已合并的代码/配置变更（便于评审）

1. [`backend/app/main.py`](backend/app/main.py)：`/ready` 使用 `response_model=None`。
2. [`backend/tests/core/test_readiness_endpoint.py`](backend/tests/core/test_readiness_endpoint.py)：新增 2 条用例。
3. [`backend/Dockerfile`](backend/Dockerfile)：生产依赖 + `HEALTHCHECK`。
4. [`.github/workflows/ci.yml`](.github/workflows/ci.yml)：`backend-mypy`（informational）。
5. [`backend/app/ai/tools/executors/http_executor.py`](backend/app/ai/tools/executors/http_executor.py)：JSONPath 异常 `debug` 日志。

---

**报告结束。**
