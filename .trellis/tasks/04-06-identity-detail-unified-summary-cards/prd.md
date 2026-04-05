# 身份详情浮层 / 详情卡统一增强

## 目标

在不修改后端接口契约和 `IdentityTrigger` / `IdentityProfileTrigger` 既有调用方式的前提下，统一前端人物身份详情体系：

- 共享 `IdentitySummaryCard` 展示基元
- 收口 `IdentityQuickCard` / `IdentityDetailDrawer` 的字段顺序与条件判断
- 统一桌面 hover / 点击 / 键盘 / 触屏交互
- 将操作日志、AI 操作日志、AI monitoring 中手写的人物身份块替换为共享身份卡

## 非目标

- 不改后端 DTO / 接口
- 不新增 `/identity/*` 接口
- 不改 agent 卡、profile hero、dashboard 大卡片

## 需求

1. 共享展示层
   - 新增 `IdentitySummaryCard`
   - 默认只使用 `model + detailRequest/fallback + createIdentityDetailPreview()`
   - `IdentityQuickCard` 仅作为 `IdentitySummaryCard + 查看详情按钮` 包装
   - `IdentityDetailDrawer` 改为“头部摘要 + 3 个 section”

2. 共享纯函数
   - `buildIdentitySummaryRows(detail, mode)`
   - `buildIdentityStatusChips(detail)`
   - `buildIdentityActivityRows(detail)`
   - `resolveIdentityPrimaryContextLabel/Value(detail)`
   - `shouldShowSecondaryOrganization(detail)`
   - `shouldShowRoleRow(detail)`

3. 交互统一
   - 桌面端仅在 `hover: hover` 且 `pointer: fine` 时启用 quick card popover
   - 点击始终打开详情 drawer
   - 触屏设备点击直接打开 drawer
   - 键盘 `Enter / Space` 打开 drawer
   - 补齐 `aria-haspopup="dialog"`、`aria-label`、focus-visible

4. 错误与回退
   - 有 fallback 时先展示 fallback
   - 请求失败时保留已知身份信息并显示 warning
   - 完全无 fallback 且无详情时才显示 empty

5. 页面替换
   - 管理端/企业端操作日志详情 drawer
   - 管理端/企业端 AI 操作日志详情
   - AI Monitoring 相关 drawer
   - MonitoringUsagePage 中如有人物详情块则统一为共享身份卡

## 验收标准

- `IdentityQuickCard` 与 `IdentityDetailDrawer` 不再各自决定字段顺序
- `tenant_user` 主上下文显示角色，其他身份主上下文显示所属架构
- `roleName === orgNodeName` 时不重复展示角色
- 详情 drawer 固定按“身份概览 / 账号属性 / 最近活动”顺序展示
- 桌面端 hover 有 quick card，点击一定打开 drawer
- 触屏/粗指针设备不依赖 hover
- 单测覆盖 helper、quick card、detail drawer、profile trigger
- 浏览器回归覆盖 operation logs / AI action logs / monitoring / organization member
