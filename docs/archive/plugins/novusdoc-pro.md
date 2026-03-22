# novusdoc-pro 归档说明

归档日期：2026-03-22

## 结论

`novusdoc-pro` 当前按“已归档样例插件”处理，不纳入现行正式插件集合。

## 原因

- 当前仓库不存在 `backend/plugins/novusdoc-pro/` 正式源码根目录。
- 历史材料显示它主要承担富文本测试/文档菜单页样例用途，不是当前商业插件体系的核心插件。
- 继续把它当作现行核心插件会误导：
  - License 设计判断
  - 前端契约判断
  - 菜单/页面模型判断

## 当前规则

- 不再以 `novusdoc-pro` 的历史描述作为插件系统现行架构依据。
- 若未来重新恢复正式源码，必须按当前统一模型重新接入：
  - `trial / fixed_term / perpetual`
  - `pages + menu`
  - `frontend.dev.entry`
  - `frontend.release.manifest`
  - `plugin build / validate / pack --release / pack --source`
