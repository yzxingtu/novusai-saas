# 插件系统全面审计（结合现有插件，2026-03-24）

## 范围

本审计基于宿主插件系统实现与现有插件样本联合进行，目标是回答以下问题：

1. 为什么插件经常出现菜单不显示、菜单未翻译、内容缺失多语言、tenant 菜单可见但页面无法进入。
2. 这些问题主要来自插件作者、skill/文档、脚手架，还是宿主插件系统本身。
3. 在现有插件集合中，这些问题已经以哪些具体形式出现。

本文件是第二轮综合审计记录。
第一轮七项核心问题记录见：

- [plugin-system-seven-findings-audit-20260324.md](/E:/git_clone/novusai-saas-yudi/docs/design/plugin-system-seven-findings-audit-20260324.md)

## 审计样本

- `backend/plugins/storage-billing`
- `backend/plugins/workflow-orchestration`
- `backend/plugins/storage-migration`
- `backend/plugins/weather-widget`

## 审计维度

1. 后端菜单注册与权限同步
2. 前端动态菜单与动态路由注册
3. tenant 可见性、套餐、角色、route guard 一致性
4. 插件 i18n 注入、命名空间与语言切换
5. loader、bootstrap、shared runtime 暴露时序
6. manifest schema 与文档契约一致性
7. CLI 脚手架、validate、build、pack 保护能力
8. 现有插件契约一致性
9. 前端 plugin extensions/slots 完整性
10. 测试覆盖与回归保护

## 当前结论

待本轮 10 路并行审计结果汇总后补充。

## 初步判断

基于第一轮七项核心问题，已经可以先给出一个方向性判断：

- 主因更偏向宿主插件系统设计与运行时契约不一致。
- `skill`、文档、脚手架和示例插件也存在漂移，但更多是在复制、放大宿主问题。
- 现有插件并非“无一例外都写错了”，而是长期处在一个脆弱宿主契约上开发。

## 待补充

- 每条新增 finding 的严重度、影响范围、可复现插件样本
- 哪些问题是已发生的现实缺陷，哪些是结构性高风险
- 修复优先级与最小收敛方案
