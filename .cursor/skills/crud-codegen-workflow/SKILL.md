---
name: crud-codegen-workflow
description: CRUD 代码生成工作流。当需要新增 CRUD 模块、编写 codegen YAML 配置、使用 `novusai codegen` 生成/预览/回滚代码，或在 codegen 不适用时按项目规范手写 CRUD 时使用。
---

# CRUD 开发与 Codegen 工作流

> 默认走 Codegen-First。只有标准 CRUD 明显不适用时，才退回手写实现。

## 何时使用

- 新增标准 CRUD 模块
- 从 YAML / DB 反射 / 已保存配置生成 CRUD 骨架
- 调整 codegen 配置并重新生成
- 回滚 codegen 生成结果
- 判断当前场景是否应该改用手写 CRUD

## 快速决策

- 标准列表 + 表单 + 路由 + 权限：
  优先 `novusai codegen`
- 树形、双端、工作流类 CRUD：
  仍优先 `novusai codegen` + preset
- Dashboard、聚合页、纯配置页、明显非标准 CRUD：
  才考虑手写

## 最短路径

```bash
novusai codegen validate --config codegen_configs/notice.yaml
novusai codegen preview --config codegen_configs/notice.yaml
novusai codegen generate --config codegen_configs/notice.yaml --auto-migrate
```

其他入口：

- DB 反射：`novusai codegen db import -t notices`
- 已保存配置：`novusai codegen generate --id 5` 或 `--resource notice`
- 回滚：`novusai codegen rollback --resource notice`

## 按任务读取

- CLI 参数、来源选择器、导入导出、版本、下载：
  读 [references/cli-commands.md](references/cli-commands.md)
- YAML 结构、字段类型、预设、常见写法：
  读 [references/codegen-yaml.md](references/codegen-yaml.md)
- auto-migrate 周期、manifest、回滚与冲突防护：
  读 [references/auto-migrate.md](references/auto-migrate.md)
- codegen 不适用时的手写 CRUD 骨架：
  读 [references/crud-handwrite.md](references/crud-handwrite.md)
- 三栏 Builder / WYSIWYG：
  读 [../novusai-saas/references/codegen-builder-spec.md](../novusai-saas/references/codegen-builder-spec.md)

## 永远成立的规则

- 不要复制别的模块整套 CRUD 代码起新模块
- 不要把通用 CLI 运维命令继续塞回这个 skill
- `generate --auto-migrate` 的迁移语义是 `upgrade heads`
- codegen 后仍要人工补业务逻辑、验证路由、i18n 和权限
- 手写 CRUD 时，也要遵守项目的分层、响应、RBAC 和迁移规范
- 若只是查看项目级 CLI 命令面，优先读 [../novusai-saas/references/cli-spec.md](../novusai-saas/references/cli-spec.md)
