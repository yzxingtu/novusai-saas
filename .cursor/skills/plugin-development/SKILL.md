---
name: plugin-development
description: NovusAI 插件开发技能。当需要创建、安装、修复或审计插件，编写 plugin.yaml、实现 PluginBase 生命周期、注册插件菜单/权限，或处理插件前后端 UMD 扩展时，参考此技能。
---

# 插件开发技能

## 何时使用

- 新增 `backend/plugins/{name}/` 插件
- 修复 `plugin.yaml`、manifest 校验、capabilities、extensions
- 实现 `PluginBase` 生命周期钩子
- 处理插件菜单、权限同步、前端 UMD 加载
- 排查插件安装、启用、卸载、升级问题

## 核心原则

- 插件必须零侵入，代码只能位于 `backend/plugins/{name}/`
- `plugin.yaml` 是插件能力、菜单、权限、扩展点的单一事实来源
- 插件 Skill 只能使用系统现有 7 种类型，禁止自定义 SkillType
- 插件权限同步使用 `sync_plugin_permissions(plugin.name)`，不要在插件事务里跑全量同步

## 标准流程

1. 先检查是否已有同类插件或模板可复用
2. 校验 `plugin.yaml` 的 name/version/capabilities/extensions
3. 在 `backend/main.py` 实现或审查 `PluginBase` 生命周期
4. 如涉及前端，确认走 UMD 动态加载，不把代码写进主系统
5. 如涉及菜单/权限，同步检查 manifest、RBAC 注册和前端路由落点
6. 最后执行插件校验或打包命令

## 关键禁令

- 禁止在主系统目录写入插件组件、插件逻辑、插件 locale
- 禁止越过 `PluginDbProxy` 访问非 `px_{name}_*` 表
- 禁止未声明 capability 就调用对应上下文能力
- 禁止 `eval`、`exec`、`subprocess`

## 常用命令

```bash
novusai plugin create my-plugin --template=minimal
novusai plugin create my-plugin --template=skill
novusai plugin create my-plugin --template=full-module
novusai plugin validate plugins/my-plugin
novusai plugin pack plugins/my-plugin
```

## 参考

- `../novusai-saas/references/plugin-spec.md`
- `../novusai-saas/references/plugin-menu-registration.md`
- `../novusai-saas/references/rbac-permission-spec.md`
