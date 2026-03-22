# AI 对话顶部区域重构方案

审计时间：2026-03-23

更新说明：2026-03-23 晚间已完成第一轮收口。用户端全页 AI 对话已去除“双层欢迎态”中的重复欢迎文案与空状态动作卡片，建议问题当前仅保留一层入口；本文其余内容仍作为顶部信息架构继续重构的规划依据。

## 一、问题定义

当前 AI 对话相关界面顶部存在明显的信息拥挤和层级混乱，已经开始影响以下体验：

- 用户很难在 1 秒内识别“我现在在和谁对话、当前会话处于什么状态、接下来最常用的动作是什么”
- 活跃会话时，顶部仍保留过多欢迎型 / 展示型内容，导致真正的对话区被下压
- 滑板版右上角集成了过多同层级按钮与状态徽标，形成“工具条过载”
- 移动端和窄宽度下，头部元素的压缩策略不明确，靠自然换行硬撑

这不是单纯的视觉样式问题，而是**信息架构、状态建模、组件职责划分**三方面同时失衡。

## 二、审计范围

本次重构规划覆盖两个主要入口：

### 1. 用户端全页 AI 对话

- [index.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/ai-chat/index.vue)

重点审计区域：

- 顶部工作台 Hero 区：约 [index.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/ai-chat/index.vue#L627) 起
- 聊天区头部：约 [index.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/ai-chat/index.vue#L978) 起

### 2. 右侧滑板 AI 对话面板

- [AIChatSlidePanel.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue)

重点审计区域：

- 顶部头部：约 [AIChatSlidePanel.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue#L1428) 起
- 头部状态/动作集中区：约 [AIChatSlidePanel.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue#L1464) 至 [AIChatSlidePanel.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue#L1722)

## 三、现状问题拆解

## 3.1 用户端全页 AI 对话的问题

### A. “工作台展示层”和“对话操作层”同时存在

当前全页顶部包含两套语义重叠的区域：

- 上方工作台 Hero：标题、说明、CTA、建议问题、当前智能体摘要、会话信号卡
- 下方聊天头部：再次显示当前智能体、变量入口、新建会话、记忆入口

结果是：

- 当前智能体信息被重复展示 2 次
- 建议问题既在 Hero 中出现，又在空消息区再次出现
- 活跃会话时，展示型内容仍占据顶部大面积空间

### B. 空会话与活跃会话没有切换不同头部模式

当前代码中已经具备以下状态信号：

- `chatMessages.length`
- `activeConversationId`
- `sending`
- `streaming`

但顶部结构并没有根据这些状态切换形态，导致：

- 空会话时合理的欢迎式布局，被错误延续到活跃会话
- 活跃会话时用户真正关心的是“当前会话上下文 + 快捷操作”，而不是“产品介绍 + 大卡片”

### C. 聊天头部的右侧动作没有优先级

当前全页头部右侧主要包含：

- 编辑变量
- 新建会话
- 会话记忆

问题不在数量本身，而在：

- 缺少主动作和次动作区分
- 没有“更多操作”容器，未来继续加功能一定再次拥挤
- 当前智能体说明文本与动作按钮处于同一视觉层级，没有形成主次关系

## 3.2 滑板版 AI 对话的问题

### A. 头部把 4 类信息塞进了一行结构

当前滑板头部混杂了以下四种完全不同的语义：

1. **产品/容器身份**
   - 面板标题
   - AI 图标

2. **会话/智能体状态**
   - pinned agent
   - current conversation agent
   - reroute armed
   - routing 中
   - route notice

3. **页面能力 / 系统诊断**
   - page AI supported
   - current page operations count

4. **用户操作**
   - 变量编辑
   - 重新分配本轮
   - 切换智能体并新开对话
   - 新对话
   - 历史
   - 记忆
   - dock / undock
   - fullscreen
   - minimize
   - close

这些内容当前都挤在头部同一视觉层，用户无法快速分辨“状态”和“操作”。

### B. 瞬时状态和持久状态被做成同一种 chip

例如：

- `routeNotice` 是短暂反馈
- `reroute armed` 是本轮开关状态
- `current conversation agent` 是会话上下文
- `page AI supported` 是页面能力诊断

它们现在都作为同等级小徽标出现，结果是：

- 反馈信息容易淹没在常驻 chip 中
- 状态变化时，头部宽度和布局抖动明显
- 用户要花额外认知成本去区分“这个 badge 是提示、配置，还是当前状态”

### C. 头部动作栏没有溢出策略

当前滑板动作是“能放就放”，而不是“按优先级分配”：

- 没有窄宽度下的降级方案
- 没有二级菜单承接次级操作
- 没有统一的动作分组模型

这会导致后续一旦继续加导出、会话设置、调试入口、Agent profile 等功能，头部会再次失控。

## 四、根因判断

综合来看，顶部混乱的根因有四个：

### 1. 没有“头部状态模式”

当前头部缺少明确模式切换，例如：

- `landing`
- `conversation-active`
- `panel-compact`
- `panel-full`
- `routing-feedback`

所以所有状态都在争抢同一套头部结构。

### 2. 没有“信息优先级模型”

系统没有定义哪些元素属于：

- P0 主身份
- P1 当前会话上下文
- P2 高频动作
- P3 低频动作
- P4 诊断/调试信息

没有优先级，就只能并排堆。

### 3. 没有“共享头部抽象”

全页版和滑板版虽然交互形态不同，但底层用的是同一套聊天能力：

- `selectedAgent`
- `activeConversationId`
- `memoryState`
- `routeNotice`
- `forceRerouteNextTurn`

现在两边各自堆模板，导致：

- 结构重复
- 文案语义接近但表达方式不统一
- 后续维护时每次都要改两处

### 4. 诊断能力被放进主工作流入口

`page AI supported` 这种能力更多是“系统能力提示”，不应该长期与“新对话 / 历史 / 记忆 / 变量”这些高频操作争夺头部主位。

## 五、重构目标

本次重构应同时满足以下目标：

### 目标 A：头部只表达一层核心叙事

任何一个时刻，头部只能突出一件事：

- 空会话：欢迎开始对话
- 活跃会话：当前与谁对话、会话状态如何
- 窄面板：快速访问核心操作

### 目标 B：状态与动作分层

必须把以下内容拆层：

- 身份层：标题、当前智能体
- 状态层：路由、会话、pin、reroute、记忆更新
- 动作层：新建、历史、变量、更多
- 窗口层：停靠、全屏、最小化、关闭

### 目标 C：活跃会话时尽可能压缩顶部

当用户已进入会话，顶部不应继续用大展示卡占据空间；要把纵向空间还给消息流和输入区。

### 目标 D：建立稳定的溢出策略

必须定义：

- 什么动作永远可见
- 什么动作可折叠进 overflow
- 什么状态可放次级行
- 什么反馈要单独用 banner，不与 chip 混用

## 六、目标信息架构

## 6.1 全页版目标结构

### 模式 1：Landing / 空会话模式

适用条件：

- `chatMessages.length === 0`
- `!sending && !streaming`
- 没有活跃会话，或用户刚进入 AI 工作台

顶部结构：

1. `ChatWorkspaceHero`
   - 工作台标题
   - 一段简短描述
   - 1 个主 CTA
   - 1 个次 CTA
   - 最多 2 条建议问题

2. `ChatAgentContextCard`
   - 当前智能体摘要
   - 关键能力 2~3 个，不再用 4 张同级信号卡平铺

3. 聊天主区域保持简洁空状态

关键变化：

- 建议问题不再在 Hero 和消息空状态重复展示两次
- 信号卡由 4 张并列，收敛为“智能体摘要 + 小型能力列表”

### 模式 2：Conversation Active / 活跃会话模式

适用条件：

- `chatMessages.length > 0` 或存在 `activeConversationId`

顶部结构：

1. `ConversationTopBar`
   - 左：当前智能体头像、名称、简短状态副标题
   - 右：高频操作

2. `ConversationContextStrip`
   - 仅在有内容时显示
   - 可承载会话创建时间、变量已配置、记忆已更新等上下文 chip

关键变化：

- 进入活跃会话后，Hero 直接折叠，不再长期占位
- 当前智能体卡只保留一份，不再上下重复

## 6.2 滑板版目标结构

### 目标分成两行，而不是一行塞满

#### 第一行：Primary Header

只放两类内容：

- 左：`ChatHeaderIdentity`
  - 面板标题
  - 当前智能体 / 当前会话简短身份
- 右：`ChatWindowControls`
  - dock / fullscreen / minimize / close

第一行原则：

- 不放 page AI
- 不放 reroute
- 不放 route notice
- 不放记忆按钮

#### 第二行：Context + Actions Row

左侧：`ChatStatusRail`

- pinned agent
- current conversation agent
- reroute armed
- routing in progress
- memory updated

右侧：`ChatActionToolbar`

永远可见：

- 历史
- 新对话
- 变量

可折叠到 overflow：

- 重新分配本轮
- 切换智能体并新开对话
- 记忆面板
- 导出
- page AI diagnostics

#### 瞬时反馈独立为 Banner

`routeNotice` 不再作为 chip 混在状态栏中，而是单独出现在第二行下方的轻量通知条：

- 4 秒自动消失
- 不参与主 header 宽度竞争
- 不与 page AI / pinned / reroute 抢位置

## 七、元素迁移规则

为了避免实施时“边改边乱”，先明确每个元素的归宿。

| 现有元素 | 当前位置 | 目标位置 |
|---|---|---|
| 面板标题 | 滑板头部左侧 | 保留在第一行 |
| 当前智能体信息 | 全页 Hero + 全页头部重复 | 活跃会话时仅保留在 `ConversationTopBar` |
| 工作台描述 | 全页 Hero | 仅保留在 Landing 模式 |
| 建议问题 | Hero + 空消息区重复 | Hero 最多 2 条；空消息区保留主入口即可 |
| 当前会话智能体 chip | 滑板第一行 | 第二行 `StatusRail` |
| pinned agent chip | 滑板第一行 | 第二行 `StatusRail` |
| reroute armed chip | 滑板第一行 | 第二行 `StatusRail` |
| routeNotice | 滑板第一行 | 独立 `RouteNoticeBanner` |
| page AI supported | 滑板第一行 | Overflow 内的 diagnostics 区，或可折叠状态说明 |
| 变量按钮 | 头部右侧 | 保留为高频动作 |
| 新建会话 | 头部右侧 | 保留为高频动作 |
| 历史 | 滑板头部右侧 | 保留为高频动作 |
| 记忆按钮 | 头部右侧 | 次级动作，默认进入 overflow，必要时以红点/徽标提示 |
| 切换智能体并新开对话 | 滑板头部右侧 | overflow |
| 重新分配本轮 | 滑板头部右侧 | overflow；若已 armed，则在 `StatusRail` 展示状态 |

## 八、组件拆分方案

为避免继续在大模板里堆条件分支，建议拆成以下组件。

### 8.1 共享展示组件

- `ChatHeaderIdentity.vue`
  - 输入：`title`、`selectedAgent`、`subtitle`
  - 职责：只负责“我现在在哪、和谁对话”

- `ChatStatusRail.vue`
  - 输入：status items 数组
  - 职责：只负责常驻状态 chip 的展示和截断

- `ChatActionToolbar.vue`
  - 输入：primary actions、overflow actions
  - 职责：负责动作优先级、图标、tooltip、一致尺寸

- `ChatRouteNoticeBanner.vue`
  - 输入：`routeNotice`
  - 职责：展示短时反馈，不参与主 header 排版

- `ChatWindowControls.vue`
  - 输入：dock/fullscreen/minimize/close handlers
  - 职责：窗口控制统一化

### 8.2 全页专用组件

- `ChatWorkspaceHero.vue`
  - 只在空会话模式出现

- `ChatAgentContextCard.vue`
  - 负责 landing 模式下的智能体摘要，不再在 Hero 主区和聊天头部重复出现

- `ConversationTopBar.vue`
  - 活跃会话时使用

### 8.3 逻辑模型层

新增一个纯计算 composable：

- `use-chat-header-model.ts`

输出：

- `headerMode`
- `identityModel`
- `statusItems`
- `primaryActions`
- `overflowActions`
- `routeNoticeBanner`

这样可以把“头部显示什么”从模板里抽离出来，避免条件散落在两个大页面组件内部。

## 九、状态优先级模型

建议显式定义优先级，而不是靠模板顺序隐式决定。

### P0：身份

- 面板 / 页面标题
- 当前智能体

### P1：当前会话上下文

- 当前会话智能体
- pinned 状态
- reroute armed
- 记忆已更新

### P2：高频操作

- 新对话
- 历史
- 编辑变量

### P3：次级操作

- 切换智能体并新开对话
- 重新分配本轮
- 导出
- 记忆面板显式打开

### P4：诊断 / 系统能力

- page AI supported
- operation count

规则：

- P0 / P1 优先显示
- P2 在宽度允许时显示
- P3 默认进入 overflow
- P4 不占主工具栏主位

## 十、响应式策略

## 10.1 全页版

### Desktop

- 活跃会话仅保留紧凑头部
- Hero 仅在 landing 模式可见

### Tablet / Mobile

- 头部改为上下两层
- 左侧身份块单独一行
- 右侧动作收敛为 `变量 + 更多`

## 10.2 滑板版

### 宽面板

- 第二行可同时展示 `StatusRail + 3 个 primary actions`

### 中等宽度

- `StatusRail` 可横向滚动
- 动作栏只保留 `历史 + 变量 + 更多`

### 极窄宽度 / 非全屏

- 第二行右侧只保留 `更多`
- `更多` 菜单中承接历史、记忆、新对话、reroute、切换智能体

## 十一、实施步骤

建议分 4 个阶段落地。

### 阶段 1：先止血，重构滑板头部

范围：

- [AIChatSlidePanel.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue)

动作：

1. 把头部拆成“两行 + 一个 transient banner”
2. 提取窗口控制区
3. 把 page AI indicator 移出主头部动作带
4. 为动作建立 primary / overflow 分组

收益：

- 这是当前最拥挤、最容易失控的区域
- 改完后能立刻改善大部分“乱七八糟”的观感

### 阶段 2：收敛全页版空会话与活跃会话模式

范围：

- [index.vue](/E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/ai-chat/index.vue)

动作：

1. 新增 `isConversationActive` 之类的显式状态
2. Landing 模式显示 Hero
3. 活跃会话模式折叠 Hero
4. 当前智能体信息只保留一份
5. 建议问题只保留一个主入口

### 阶段 3：抽共享头部模型

动作：

1. 提取 `use-chat-header-model.ts`
2. 提取 `ChatHeaderIdentity` / `ChatStatusRail` / `ChatActionToolbar`
3. 全页版和滑板版共用头部状态建模

### 阶段 4：细化性能与体验

动作：

1. 给 overflow 操作补 icon / keyboard / accessibility
2. 给 `StatusRail` 加溢出提示和 aria-label
3. 做移动端/窄宽度交互校验

## 十二、验收标准

重构完成后，至少满足以下标准：

### 视觉与交互

- 滑板头部第一行不再同时出现 6 个以上状态/动作元素
- `routeNotice` 不再和常驻 chip 混排
- page AI indicator 不再占据头部主位
- 活跃会话下，全页不再保留大块 Hero 展示区
- 当前智能体不再重复展示两次

### 信息层级

- 用户进入会话后，能在第一眼识别当前智能体
- 高频动作可在一层点击完成
- 低频动作统一收敛到 overflow

### 代码结构

- 头部逻辑不再散落在两个大模板中
- 至少完成 2~3 个共享展示组件提取
- 条件判断从模板迁到 composable / model 层

## 十三、测试建议

重构时建议同步补测试，避免“看起来更清爽，但行为回归”。

### 单元 / 组件测试

- 空会话模式 vs 活跃会话模式切换
- 滑板头部 primary / overflow 动作分配
- `routeNotice` 显示和自动消失
- reroute armed 状态与 overflow 行为

### 视觉回归

- 全页 Desktop
- 全页 Mobile
- 滑板普通宽度
- 滑板窄宽度
- 滑板 full mode

## 十四、最终建议

不要把这次问题当成“把头部按钮减两个”的小修，而要按下面的思路做：

1. 先把**头部模式**定义清楚
2. 再把**状态、动作、诊断信息**分层
3. 最后再做样式与组件抽取

如果只做视觉微调，不解决模式和优先级，后面一旦再加一个“导出”“智能体档案”或“页面调试”入口，顶部还会再次失控。

本方案建议优先从滑板版开始实施，因为它是当前拥挤最严重、收益也最大的区域；随后再把全页版从“工作台页”和“活跃会话页”两个状态真正拆开。
