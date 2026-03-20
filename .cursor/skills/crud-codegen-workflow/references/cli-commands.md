# NovusAI CLI 完整命令参考

> novusai CLI 统一入口，整合 run / celery / db / plugin / license / codegen / check / info。
> Unified CLI entry for run / celery / db / plugin / license / codegen / check / info.

安装：`cd backend && pip install -e .`

---

## 应用运行

```bash
novusai run                              # 启动 FastAPI（默认 localhost:8000）
novusai run --port 9000                  # 自定义端口
novusai run --workers 4                  # 多 worker
novusai run --reload                     # 强制热重载
novusai run --no-reload                  # 禁止热重载
```

---

## Celery 任务管理

```bash
novusai celery worker                    # 启动 worker（全部队列）
novusai celery worker -Q ai_gateway      # 仅 AI 队列
novusai celery worker -Q default,high_priority  # 指定多个队列
novusai celery worker -c 4              # 并发数
novusai celery beat                      # 定时任务调度
novusai celery dev                       # 开发模式（Worker + Beat）
novusai celery flower                    # Flower 监控面板
novusai celery purge                     # 清空队列
```

队列：`default` / `high_priority` / `ai_gateway` / `scheduled` / `notification`

Windows 下 `dev` 用双线程分别跑 worker 和 beat。

---

## 数据库迁移

```bash
novusai db upgrade                       # 执行所有迁移（默认 head）
novusai db upgrade abc123                # 迁移到指定 revision
novusai db revision -m "add xxx"         # 手写空迁移文件
novusai db autogenerate -m "add xxx"     # 自动检测 Model 变更生成迁移
novusai db current                       # 查看当前版本
novusai db heads                         # 查看所有 head
novusai db history                       # 迁移历史
novusai db history -v                    # 详细历史
novusai db stamp head                    # 标记为最新（不执行迁移）
novusai db merge -m "merge branches"     # 合并多 head
```

自动注入插件迁移路径 `plugins/*/backend/migrations/versions/`。

---

## 插件管理

```bash
novusai plugin create my-plugin --template minimal        # 纯后端
novusai plugin create my-plugin --template skill          # 含 Skill/Executor
novusai plugin create my-plugin --template full-module    # 完整前后端
novusai plugin create my-plugin --template storage        # 含存储
novusai plugin validate plugins/my-plugin                 # 校验
novusai plugin pack plugins/my-plugin                     # 打包 ZIP
novusai plugin pack plugins/my-plugin --output out.zip    # 指定输出
novusai plugin list                                       # 列出已安装
novusai plugin cleanup                                    # 清理无效
```

---

## License 管理

```bash
novusai license keygen                   # 生成 Ed25519 密钥对（仅开发环境）
novusai license generate --plugin xxx    # 为插件生成许可证
novusai license generate --plugin xxx --email user@co.com --days 365
novusai license verify --plugin xxx --key KEY  # 验证许可证
```

---

## 代码生成器（codegen）

### 核心命令

```bash
# 生成
novusai codegen generate --config config.yaml          # 从 YAML
novusai codegen generate --id 5                         # 从数据库配置 ID
novusai codegen generate --resource notice              # 从资源名
novusai codegen generate --stdin                        # 从 stdin
novusai codegen generate -c config.yaml --force         # 强制覆盖
novusai codegen generate -c config.yaml --auto-migrate  # 生成 + 自动迁移
novusai codegen generate -c config.yaml --dry-run       # 仅预览
novusai codegen generate -c config.yaml --json          # JSON 输出

# 预览（不写入文件，仅输出到终端）
novusai codegen preview --config config.yaml
novusai codegen preview --id 5
novusai codegen preview --resource notice --verbose

# 校验
novusai codegen validate --config config.yaml
novusai codegen validate --stdin

# 回滚
novusai codegen rollback --resource notice
novusai codegen rollback --id 5
novusai codegen rollback --resource notice --dry-run
novusai codegen rollback --resource notice --force
```

配置来源优先级：`--stdin > --config > --id/--resource`

### 配置管理

```bash
novusai codegen list                     # 列出所有配置
novusai codegen list --json              # JSON 输出
novusai codegen show --id 5              # 查看详情
novusai codegen import -c config.yaml    # 导入 YAML 到数据库
novusai codegen export --id 5            # 导出为 YAML
novusai codegen export --resource notice
novusai codegen duplicate --id 5         # 复制配置
novusai codegen delete --id 5            # 删除配置
```

### DB 反射

```bash
novusai codegen db tables                # 列出数据库表
novusai codegen db columns -t notices    # 查看表列定义
novusai codegen db import -t notices     # 从表导入为 YAML
```

### 版本与辅助

```bash
novusai codegen versions --id 5          # 历史版本
novusai codegen restore --id 5 -v 3          # 恢复版本（-v/--version 为版本 ID）
novusai codegen history                  # 生成历史
novusai codegen init -t simple           # 从预设初始化
novusai codegen download --id 5 -o out.zip   # 下载 ZIP
```

预设模板：`simple` / `tree` / `dual_scope` / `workflow`

---

## 环境检查

```bash
novusai check                            # 全部（DB + Redis + Celery）
novusai check db                         # 数据库连接
novusai check redis                      # Redis 连接
novusai check celery                     # Celery worker 状态
```

---

## 系统信息

```bash
novusai info                             # 版本、环境、Python、DB、Redis（脱敏）
novusai --version                        # 版本号
```
