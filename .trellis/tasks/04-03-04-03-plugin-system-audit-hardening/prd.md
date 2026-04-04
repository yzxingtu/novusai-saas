# Plugin System Audit Hardening

## Goal

以 plugin manifest 和 canonical runtime playbook 为唯一真源，收口插件运行时、插件管理界面、资源边界、恢复链与 release/validation 流程，避免在当前脏仓里继续依赖隐式兼容。

## Requirements

- 对齐 `.trellis/spec/guides/plugin-runtime-playbook.md`、`.cursor/rules/plugin-system.md`、后端插件宿主实现与前端插件管理 UI。
- 明确 `/plugin-assets/...` 与 `/plugin-public-assets/...` 的资源边界。
- 保证 menu/page/runtime gate 三套权限判断同一语义。
- 将插件恢复、调度刷新、健康检查与 admin 操作链统一到当前 runtime 设计上。
- 让 `validate/build/pack --release` 与浏览器回归可以作为独立工作流完成。

## Acceptance Criteria

- manifest 是插件元数据与菜单标题的唯一真源。
- 插件 runtime、插件管理 UI 与 release/build/test 路径一致，不再依赖旧 playbook 或重复规则正文。
- 插件恢复/调度相关后端测试与插件管理前端测试可独立通过。
- 本任务拥有完整的 deep-path Trellis artifacts，而不是继续停留在 legacy task metadata。
