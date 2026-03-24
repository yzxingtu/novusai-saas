# NovusAI CLI 工具规范 / NovusAI CLI Tool Specification

> 统一 CLI 入口 `novusai`，整合 run / celery / db / plugin / license / codegen / check / info 等子命令。
> Unified CLI entry `novusai`, integrating run / celery / db / plugin / license / codegen / check / info subcommands.

---

## 一、安装与入口

```bash
cd backend
pip install -e .
novusai --help
```

入口定义于 `backend/pyproject.toml`：

```toml
[project.scripts]
novusai = "app.cli:cli"
```

---

## 二、子命令一览

| 命令组 | 子命令 | 说明 |
|--------|--------|------|
| `novusai run` | - | 启动 FastAPI（uvicorn） |
| `novusai celery` | worker, beat, dev, flower, purge | Celery 管理 |
| `novusai db` | upgrade, revision, current, heads, history, stamp, merge, autogenerate | Alembic 迁移 |
| `novusai plugin` | create, validate, build, pack, list, cleanup, sync-manifest, activate-license, enable, assign-tenant | 插件管理 |
| `novusai license` | generate, verify, keygen | License 管理 |
| `novusai codegen` | generate, preview, validate, rollback, versions, restore, list, show, import, export, delete, duplicate, presets, init, history, download | 代码生成器 |
| `novusai trace` | show | 根据 `trace_id` 查询操作日志与文件日志上下文 |
| `novusai check` | all, db, redis, celery | 环境连通性检查 |
| `novusai info` | - | 版本/环境/配置摘要 |

---

## 三、子命令详情

### 3.1 novusai run

```bash
novusai run [--host 0.0.0.0] [--port 8000] [--reload|--no-reload] [--workers 1]
```

- `--reload` 默认在 `APP_ENV=development` 时开启
- 内部调用 `uvicorn app.main:app`

### 3.2 novusai celery

```bash
novusai celery worker [-Q queues] [-c concurrency] [-l loglevel]
novusai celery beat [-l loglevel]
novusai celery dev [-l loglevel]   # Worker + Beat 开发模式
novusai celery flower [-l loglevel]
novusai celery purge
```

- `worker` 默认监听全部队列：default, high_priority, ai_gateway, scheduled, notification
- `dev` 在 Windows 下用双线程分别跑 worker 和 beat，Linux 下用 `--beat` 单进程

### 3.3 novusai db

```bash
novusai db upgrade [revision]           # 默认 heads
novusai db revision -m "desc" [--autogenerate]
novusai db current
novusai db heads
novusai db history [-v]
novusai db stamp [revision]
novusai db merge [-m "merge"]
novusai db autogenerate -m "desc"
```

- 自动注入插件迁移路径（`plugins/*/backend/migrations/versions/`）

### 3.4 novusai plugin

```bash
novusai plugin create <name> [--template minimal|skill|full-module|storage] [--output dir]
novusai plugin validate <path>
novusai plugin build <path>
novusai plugin pack <path> [--output file.zip] [--release] [--source]
novusai plugin list
novusai plugin cleanup --plugin <name> [--revision rev1,rev2]
novusai plugin sync-manifest --plugin <name>
novusai plugin activate-license --plugin <name> --key <license_key>
novusai plugin enable --plugin <name>
novusai plugin assign-tenant --plugin <name> --tenant-id 1 [--tenant-id 2]
```

- `create`/`validate`/`build`/`pack` 复用 `scripts/plugin_cli.py` 逻辑
- `cleanup` 调用 `scripts/cleanup_plugin.py`，用于清理插件 DB 记录、Alembic 版本与构建产物
- `sync-manifest` / `activate-license` / `enable` / `assign-tenant` 通过 `PluginService` 对已安装插件做运维操作
- `list` 读取 `plugins/` 目录

### 3.5 novusai license

```bash
novusai license generate --plugin <name> [--email <email>] [--days N] [--scope *]
novusai license verify --plugin <name> --key <key>
novusai license keygen
```

### 3.6 novusai codegen

代码生成器：通过 YAML 配置生成 CRUD 骨架。完整命令与参数见 [codegen-spec.md](codegen-spec.md) 和 [cli-commands.md](../../crud-codegen-workflow/references/cli-commands.md)。

```bash
novusai codegen generate --config codegen_configs/xxx.yaml --auto-migrate  # 生成 + 自动迁移
novusai codegen preview --config codegen_configs/xxx.yaml                   # 按文件预览
novusai codegen preview --resource xxx --step frontend --verbose            # 按资源局部预览
novusai codegen validate --config codegen_configs/xxx.yaml                  # 校验
novusai codegen rollback --resource xxx                                    # 回滚
novusai codegen versions --resource xxx                                    # 查看版本
novusai codegen restore --resource xxx --version-id 1                      # 恢复版本
novusai codegen list [--resource xxx]                                      # 列出记录
novusai codegen show --resource xxx                                        # 查看详情
novusai codegen import --input xxx.yaml                                    # 导入配置
novusai codegen export --resource xxx [--output xxx.yaml]                  # 导出配置
novusai codegen delete --resource xxx                                      # 删除记录
novusai codegen duplicate --resource xxx --new-resource yyy                # 复制配置
novusai codegen presets list [--json]                                      # 列出预设
novusai codegen presets show --name simple [--json]                        # 查看预设
novusai codegen init --template simple [--output xxx.yaml]                 # 从预设初始化
novusai codegen history [--resource xxx] [--json]                          # 查看生成历史
novusai codegen download --resource xxx --output xxx.zip                   # 按资源下载生成结果
novusai codegen download --config xxx.yaml --output xxx.zip                # 按配置文件下载
novusai codegen download --stdin --output xxx.zip                          # 从 stdin 下载
```

- `presets list/show` 对应 `app.codegen.preset_loader`
- `init` 本质上是从 preset 写出 YAML 配置
- `preview` 支持 `--config` / `--id` / `--resource` / `--stdin` 四种来源，并支持 `--step model|controller|frontend` 与 `--verbose`
- `download` 要求且仅允许一个来源选择器：`--id` / `--resource` / `--config` / `--stdin`
- `generate --auto-migrate` 走 `novusai db upgrade heads` 语义，与启动自动迁移保持一致

### 3.7 novusai check

```bash
novusai check              # 检查 DB + Redis + Celery
novusai check db
novusai check redis
novusai check celery
```

### 3.8 novusai trace

```bash
novusai trace show <trace_id> [--source auto|db|logs|all] [--json]
                    [--context 20] [--max-blocks 10] [--since-hours 72]
                    [--no-redact] [--unsafe]
```

- 用途：根据 `trace_id` 聚合两类信息
  - `system.operation_logs` 中的同 trace 审计日志
  - `LOG_DIR` 下 `*.log*` 中的命中日志块
- `--source auto` 默认值：
  - 先尝试 DB + 日志
  - 若 DB lookup 异常，则自动回退到仅日志文件扫描
- `--context`：命中行前后文
- `--max-blocks`：最多返回多少段日志块
- `--since-hours`：只扫描最近 N 小时修改过的日志文件；传 `<=0` 取消时间过滤
- `--json`：输出 JSON，适合脚本、工单系统或自动化采集
- `--no-redact`：关闭脱敏
- 生产 / 预发环境中，若要关闭脱敏，必须同时满足：
  - `--unsafe`
  - `NOVUSAI_ALLOW_UNSAFE_TRACE=1`
- 退出码约定：
  - `0`：找到命中
  - `1`：未找到命中
  - `2`：unsafe 输出被阻断

### 3.9 novusai info

```bash
novusai info
```

输出：版本、环境、Python、Database、Redis（敏感信息脱敏）

---

## 四、弃用脚本

以下脚本已弃用，请使用 `novusai` 对应命令：

| 原脚本 | 替代命令 |
|--------|----------|
| `python scripts/start_worker.py worker/beat/dev` | `novusai celery worker/beat/dev` |
| `python scripts/alembic_run.py upgrade heads` | `novusai db upgrade heads` |
| `python scripts/plugin_cli.py create/validate/build/pack` | `novusai plugin create/validate/build/pack` |
| `python scripts/generate_license_key.py` | `novusai license generate/keygen` |

在保留脚本头部添加：

```python
# DEPRECATED: Use `novusai <command>` instead.
# 已弃用：请使用 `novusai <command>` 替代。
```

---

## 五、新增子命令流程

1. 在 `app/cli.py` 中定义 `@cli.command()` 或 `@cli.group()`
2. 更新本规范 [cli-spec.md](cli-spec.md)
3. 更新 [../SKILL.md](../SKILL.md) 与 [delivery-checklist.md](delivery-checklist.md) 中受影响的检查项
