# 第二轮审计「未结项」Remediation 交接方案（给执行方 / GPT-5）

**目的**：把 [comprehensive-audit-round2-2026-03-31.md](./comprehensive-audit-round2-2026-03-31.md) 中**未逐项修复**的债，拆成**可独立验收**的任务包，便于另一模型或开发者按顺序落地。  
**约束**：执行前请通读本节「全局原则」；每任务完成后更新本文档末尾 **执行 checklist**（或单独 PR 描述中勾选）。

---

## 全局原则（必须遵守）

1. **小步 PR**：每个任务包尽量单独 PR，避免「审计式大杂烩」难以 review。
2. **行为优先于形式**：`except Exception: pass` 不是一律删；**预期静默**（客户端已断开、可选 Redis 不可用）保留语义，改为 **`logger.debug` + 简短原因** 或 **注释说明为何必须静默**。
3. **禁止**：在热路径把大量 `debug` 改成 `warning` 导致日志风暴；**禁止** `text(f"...")` 拼接**用户可控**表名/列名。
4. **测试**：凡改安全边界（CORS、鉴权、执行器）必须有**新增或更新测试**；纯日志级别调整可选测，但需在 PR 说明「为何无测」。
5. **回归命令**（在 `backend/` 或仓库根执行，按项目习惯）：
   - `python -m ruff check app/`
   - `python -m pytest tests/ -q --tb=no`（全量前可先跑相关子目录）
6. **不要修改** Cursor 计划文件；可更新本 handoff 的 checklist。

---

## 任务包索引与建议顺序

| 顺序 | 任务 ID | 名称 | 依赖 |
|------|---------|------|------|
| 1 | R-EXC-P1 | 附录 A：P1 文件 `pass` 收敛（日志化） | 无 |
| 2 | R-EXC-P2 | 附录 A：P2 文件 `pass` 评审与最小改动 | R-EXC-P1 可并行，建议错开 PR |
| 3 | R-CORS | CORS `*` + credentials 方案选型与实现 | 需产品/运维确认「是否允许改浏览器行为」 |
| 4 | R-IDOR | 多租户 IDOR 扫描 + 高风险路由表 | 无代码前置，但产出表后可能触发修复 PR |
| 5 | R-CELERY | Celery 动态 import 文档化 + 可选硬ening | 低侵入 |
| 6 | R-DOMPURIFY | DOMPurify 集中配置与白名单 | 前端 |
| 7 | R-DOCKER | Docker 非 root + 多阶段瘦身 | 需验证 K8s securityContext 是否已设 |
| 8 | R-SUPPLY | Dependabot / pip-audit | 仓库管理员权限 |
| 9 | R-CI | pytest `-x` 与迁移 ruff 策略 | 与团队发布节奏对齐 |

---

## R-EXC-P1：附录 A 中优先日志化的 `except Exception: pass`

### 目标

对 **业务失败应可诊断** 的路径，将 `pass` 改为 **`logger.debug` 或 `logger.warning`**（按频率选），并带 **异常对象**（`logger.debug("ctx: {}", exc)` 或 `exc_info=True` 仅用于非热路径）。

### 范围文件（首轮清单，执行时用 `rg` 再确认行号）

```bash
rg "except Exception:\s*\n\s*pass" backend/app backend/plugins -g"*.py" -U
```

**建议 P1 优先处理**（与报告附录 A 一致）：

- `backend/app/ai/rag/processor.py`（多处）：按函数分块，区分「解析旁路」vs「索引主路径」；主路径失败至少 `debug` + 文档化原因。
- `backend/app/tasks/ssl_tasks.py`
- `backend/app/tasks/agent_batch.py`
- `backend/plugins/storage-migration/backend/services/migration_service.py`（插件内）

### 步骤

1. 逐文件打开每个 `except` 块，回答：**若永远不打日志，排障是否不可能？** 若是 → 加日志。
2. 若该异常在循环内每秒触发 → 仅 `debug`，必要时带 **采样**（每 N 次打一条）——若实现采样，在注释写清 N 的选取。
3. 保持 **不改变对外 API 返回值**（除非原逻辑就是吞掉继续，且 PR 明确说明变更原因）。

### 验收标准

- [ ] 上述 P1 文件中不再有无注释的「裸 `pass`」**除非**紧邻一行注释说明「为何必须静默」（例如「连接已关闭」类可引用 `sse.py` 模式）。
- [ ] `ruff check app/` 通过；相关目录 `pytest` 通过（若有 RAG/任务测试则跑之）。

### 建议不纳入本包（留 R-EXC-P2）

- `auth_service.py`（Redis 不可用静默）— 已有注释则可保留，仅补 `debug` 一次即可。
- `migrations/env.py` — 仅保证注释清晰。

---

## R-EXC-P2：附录 A 其余 `pass` 与「明确静默」文档化

### 目标

对 **SSE / WS / 可选组件** 等路径：**保留静默语义**，但统一为 **`logger.debug`**（极低噪）或 **三行内注释** 说明「为何不能 log warning」。

### 范围

- `backend/app/plugins/sse.py`
- `backend/app/sio/ws_config.py`
- `backend/app/plugins/lifecycle.py`（3 处：逐段读上下文，勿改插件卸载语义）
- `backend/app/core/database.py`（若属于 shutdown 清理）
- `backend/app/codegen/*`、`backend/scripts/plugin_cli.py`、`_skill_test.py`、`image_generation.py`、`slider-captcha` 等

### 验收标准

- [ ] 全仓 `rg` 结果中，每一处 `pass` 要么已改为 `debug`，要么有 **紧邻注释**。
- [ ] 无新增 `except BaseException` 吞取消信号（勿误伤 `CancelledError`）。

---

## R-CORS：`*` + `allow_credentials=True` 行为改造（P1 安全）

### 背景证据

[`backend/app/main.py`](../../backend/app/main.py) 中 `CORSMiddleware`：`allow_origins=["*"]` 与 `allow_credentials=True` 并存；错误处理里另有按 `Origin` 回写 CORS 头的逻辑。需 **对照 Starlette 实际响应头** 在 Chrome/Firefox 各测一次（执行方完成并写入 `docs/operations/cors-behavior.md` 可选）。

### 方案分支（执行方任选其一，**必须在 PR 描述写清选型理由**）

**方案 A（推荐，中长期）**：反射白名单

1. 从配置或 DB 读取 **允许 Origin 列表**（例如：平台管理端固定域、各租户 `custom_domain` + 主域）。
2. 实现中间件或封装 `CORSMiddleware`：**若 `Origin in allowed` 则回显该 Origin，否则不回写 credentials 相关头**（具体与前端是否依赖 cookie 对齐）。
3. 保留 `expose_headers=["X-Trace-ID"]` 等行为。

**方案 B（短期，文档化）**：不改代码

1. 新增 `docs/operations/cors-and-csrf.md`：说明当前 API **是否以 Bearer 为主**、Cookie 使用范围、为何 CSRF 风险可接受或可忽略。
2. 在 `README` 或运维文档链接该页。

**方案 C（拆分）**：`/admin` 与 `/tenant` 使用不同 CORS 策略（需路由级中间件或子应用），工作量大，单独里程碑。

### 验收标准

- [ ] 选定 A/B/C 之一并落地；若选 A，需 **最小 e2e 或集成测**：带 `Origin` 预检请求断言响应头。
- [ ] 前端本地 `dev` 与生产构建 **仍能登录与调 API**（执行方自测清单写在 PR）。

---

## R-IDOR：多租户「按 ID 取资源」全量扫描与高风险表

### 目标

产出 **`docs/acceptance/idor-route-inventory-YYYY-MM-DD.md`**（或 JSON），列明：

- 路由方法、路径模板、Handler 函数、是否带 `tenant_id` / `ActiveTenantAdmin` / `TenantUser` 依赖、Service 是否注入 `tenant_id`。

### 方法论（可脚本化 + 人工补全）

1. **静态扫描**（Python）：
   - 枚举 `backend/app/api/admin/**/*.py`、`tenant/**/*.py`、`api/user/**/*.py` 中注册的路由（或 grep `@router.get("/{id}"`、`:id`、`:xxx_id`）。
2. **人工列**（必须）：每条「按 ID 详情」接口对应 **Service.get_by_id** 是否 **强制 tenant 过滤**；Admin 跨租户接口是否 **故意设计**（需备注业务原因）。
3. **输出「高风险」定义**（供执行方实现）：满足以下任一 → 标红：
   - Handler 仅 `id: int`，无 tenant 上下文注入 Service；
   - Service 查询仅 `where(Model.id == id)` 无 `tenant_id`。

### 验收标准

- [ ] 清单文件落库，`admin/tenant/user` **每类至少各 5 条**已人工复核（若总数不足则全部复核）。
- [ ] 高风险项：每个要么 **开 issue** 要么 **本批次修完**（修则需测试）。

---

## R-CELERY：动态 `__import__` 与危险执行面（文档 + 可选加固）

### 目标

1. 在 `docs/operations/celery-task-loading.md`（或 `backend/README` 一节）写明：**仅加载 `app.tasks` 包内模块**、禁止从用户输入拼接模块路径。
2. 代码层（可选 P1）：在 [`backend/app/celery_app.py`](../../backend/app/celery_app.py) 对 `__import__(module)` 增加 **前缀白名单**（例如 `module.startswith("app.tasks.")`），否则 `raise` 或 `logger.critical` + 拒绝加载。

### 验收标准

- [ ] 文档存在且与代码一致；若加固，需 **单元测试** 覆盖「非法模块名拒绝」。

### 关联（不强制本包完成）

- `code_execution_executor` / `toolkit_executor`：**权限与配额**在单独安全里程碑 review；本包仅交叉链接审计报告第 5 节。

---

## R-DOMPURIFY：前端集中白名单（P2）

### 目标

在 `frontend/apps/web-antd/src/utils/sanitize-html.ts`（或等价路径）封装：

```ts
import DOMPurify from 'dompurify';

const DEFAULT_CONFIG = { /* ALLOWED_TAGS / ALLOWED_ATTR 显式列出 */ };

export function sanitizeUserHtml(dirty: string): string {
  return DOMPurify.sanitize(dirty, DEFAULT_CONFIG);
}
```

### 替换点

- [`frontend/apps/web-antd/src/components/business/markdown-render/index.vue`](../../frontend/apps/web-antd/src/components/business/markdown-render/index.vue)
- [`frontend/apps/web-antd/src/components/business/rich-text-editor/ai/AIResultPanel.vue`](../../frontend/apps/web-antd/src/components/business/rich-text-editor/ai/AIResultPanel.vue)
- [`frontend/apps/web-antd/src/views/user/authentication/legal-document.vue`](../../frontend/apps/web-antd/src/views/user/authentication/legal-document.vue)

### 验收标准

- [ ] 三处均通过统一封装调用（法律文档若需更宽标签，可 **第二个 profile** `sanitizeLegalHtml`，并在注释写清原因）。
- [ ] `pnpm run lint` / `pnpm run typecheck` 通过。

---

## R-DOCKER：非 root + 多阶段瘦身（P2）

### 目标

- [`backend/Dockerfile`](../../backend/Dockerfile)：`api` / `worker` / `beat` 阶段使用 **`USER appuser`**（`adduser` + `chown`）。
- 可选：builder 阶段编译依赖，runtime 阶段仅拷贝 site-packages（多阶段）。

### 验收标准

- [ ] 本地 `docker build -f backend/Dockerfile --target api` 成功；容器内 `whoami` 非 root。
- [ ] `HEALTHCHECK` 仍可用（非 root 下 `curl` 若不可用则换 `wget` 或 `python -c`）。

### 注意

若 K8s 已设 `runAsNonRoot: true`，与本任务对齐，避免重复冲突。

---

## R-SUPPLY：Dependabot / pip-audit（P2）

### Dependabot（推荐）

在仓库 `.github/dependabot.yml`：

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
```

（按 monorepo 实际路径调整。）

### pip-audit（CI 可选）

- 新增 job：`pip install pip-audit && pip-audit -r backend/requirements.txt` **若无 lock 则从 pyproject 导出**；`continue-on-error: true` 直至基线清理。

### 验收标准

- [ ] Dependabot PR 能出现（或文档说明为何不用）；pip-audit 至少在文档中给出 **本地命令**。

---

## R-CI：pytest `-x` 与迁移目录 Ruff（流程债）

### 子任务 R-CI-A：pytest

- **现状**：`.github/workflows/ci.yml` 中 `pytest tests/ -x`。
- **选项**：
  1. 保留 `-x`，另加 **nightly workflow** 无 `-x` + `--maxfail=20`；
  2. PR 上去掉 `-x`，改为 `--maxfail=5` 平衡信号与时长。

### 子任务 R-CI-B：migrations ruff

- **选项**：
  1. 新增 job `ruff check migrations/versions --select F,E`（窄规则，避免与 autogen 冲突）；
  2. 或在 `pre-commit` 仅对新迁移生效。

### 验收标准

- [ ] 团队选定 A/B 并在 `ci.yml` 或文档中一致描述；CI 绿。

---

## 附录：快速检索命令（执行方复制用）

```bash
# except + pass（Python）
rg "except Exception:\s*\n\s*pass" backend/app backend/plugins backend/migrations backend/scripts -g"*.py" -U

# 动态 text(f
rg "text\(f[\"']" backend/app -g"*.py"

# 前端 v-html
rg "v-html" frontend/apps/web-antd/src -g"*.vue"
```

---

## 执行 Checklist（由执行方勾选）

- [ ] R-EXC-P1
- [ ] R-EXC-P2
- [ ] R-CORS（写明方案 A/B/C）
- [ ] R-IDOR 清单文件已落库
- [ ] R-CELERY 文档 / 白名单加固
- [ ] R-DOMPURIFY
- [ ] R-DOCKER
- [ ] R-SUPPLY
- [ ] R-CI-A / R-CI-B

---

**文档版本**：2026-03-31  
**维护**：完成任一包后更新 checklist 与（如有）新证据路径。
