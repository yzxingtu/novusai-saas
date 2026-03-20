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
| `novusai plugin` | create, validate, pack, list | 插件管理 |
| `novusai license` | generate, verify, keygen | License 管理 |
| `novusai codegen` | generate, preview, validate, rollback, list, show, import, export, db, init, ... | 代码生成器 |
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
novusai db upgrade [revision]           # 默认 head
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
novusai plugin pack <path> [--output file.zip]
novusai plugin list
```

- `create`/`validate`/`pack` 复用 `scripts/plugin_cli.py` 逻辑
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
novusai codegen preview --config codegen_configs/xxx.yaml                   # 预览
novusai codegen validate --config codegen_configs/xxx.yaml                  # 校验
novusai codegen rollback --resource xxx                                    # 回滚
```

### 3.7 novusai check

```bash
novusai check              # 检查 DB + Redis + Celery
novusai check db
novusai check redis
novusai check celery
```

### 3.8 novusai info

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
| `python scripts/alembic_run.py upgrade head` | `novusai db upgrade head` |
| `python scripts/plugin_cli.py create/validate/pack` | `novusai plugin create/validate/pack` |
| `python scripts/generate_license_key.py` | `novusai license generate/keygen` |

在保留脚本头部添加：

```python
# DEPRECATED: Use `novusai <command>` instead.
# 已弃用：请使用 `novusai <command>` 替代。
```

---

## 五、新增子命令流程

1. 在 `app/cli.py` 中定义 `@cli.command()` 或 `@cli.group()`
2. 更新本规范 `cli-spec.md`
3. 更新 `SKILL.md` 检查清单
