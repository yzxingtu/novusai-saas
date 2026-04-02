# AI 对话方案实施全面审计报告

本文档对「Ctrl+K 换行、发送区停止生成与 AI 对话功能审计」方案及 P1/P2 增强的实施结果做逐项与交叉审计，包含正确性、边界情况、一致性与可改进点。

---

## 一、方案项逐项审计

### 1. 问题 1：Ctrl+K 多行换行

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 控件类型 | 通过 | CommandBar.vue 已使用 `Input.TextArea`，`auto-size="{ minRows: 1, maxRows: 4 }"` |
| 绑定与事件 | 通过 | `:value="inputText"`、`@update:value="handleInputChange"`；handleKeydown 中 Enter 且非 Shift 提交，Shift+Enter 不 preventDefault |
| focus | 通过 | inputRef 类型为 `{ resizableTextArea?: { textArea: HTMLTextAreaElement } }`，watch(open) 中 `inputRef.value?.resizableTextArea?.textArea?.focus()` |
| 样式 | 通过 | `resize-none overflow-y-auto`，与单行视觉一致 |
| placeholder / tooltip | 通过 | placeholder 使用 globalAiChat.inputPlaceholder；Tooltip 拼接 inputPlaceholder + shiftEnterHint |
| 依赖 | 通过 | 已从 ant-design-vue 引入 Input、Tooltip |
| mention / 菜单搜索 | 通过 | mention 模式下 Enter 选智能体、Shift+Enter 不提交；有 menu 结果时 Enter 选菜单或提交；纯输入时 Enter 提交，逻辑未破坏 |

### 2. 问题 2：停止合并到发送

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 浮动停止按钮移除 | 通过 | AIChatSlidePanel、user/ai-chat 仅保留「滚动到底部」浮动按钮（`showScrollToBottom && !streaming`） |
| 发送区主按钮行为 | 通过 | 两处均为 `streaming ? stopGeneration() : handleSendMessage()/handleSendClick()`，流式时图标 square，非流式 arrow-up |
| disabled 逻辑 | 通过 | `!streaming && (无内容且无附件 \|\| 无 agent \|\| sending)`，流式时按钮可点 |
| aria-label | 通过 | 两处均 `:aria-label="streaming ? $t('common.globalAiChat.stop') : $t('common.commandBar.send')"` |
| Spin 显示 | 通过 | Slide 为 `!streaming && (sending \|\| routing)`，user 页为 `!streaming && sending`（无 routing），符合设计 |

### 3. P1：复制 toaster、生成已停止、SSE 重试

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 复制成功 toaster | 通过 | copyMessage 成功分支内 `message.success($t('common.globalAiChat.copySuccess'))` |
| stoppedByUser | 通过 | stopGeneration 对最后一条 assistant 设 `last.stoppedByUser = true`；ChatMessageItem 在 `msg.stoppedByUser && !msg.streaming` 时渲染 generationStopped |
| requestFailedRetry | 通过 | onError 中设 `msg.requestFailedRetry = true`；类型已扩展 |
| 重试按钮与 retryLastMessage | 通过 | ChatMessageItem 对 requestFailedRetry 展示重试并 emit('retry', index)；两处面板 @retry="retryLastMessage"；retryLastMessage 删除最后一条、恢复上一条 user 到 input/attachments、sendMessage({ silent: true }) |
| ChatMessageItem 依赖 | 通过 | Button、Tooltip 已从 ant-design-vue 引入 |

### 4. P2：工具确认说明、信任持久化、导出、路由、页面操作

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 工具确认首次说明 | 通过 | ChatMessageItem 待确认卡片（v-else）顶部展示 consentFirstTimeHint |
| 信任会话持久化 | 已废弃 | 前端 sessionStorage 方案不再作为授权真相；正式交互模式与自动批准以后端运行时信任策略为准 |
| 导出格式可选 | 通过 | exportAsPlainText 存在；两处面板均为 Dropdown + Menu，exportMenuItems 含 Markdown/纯文本并调用对应方法 |
| 路由失败提示 | 通过 | AIChatSlidePanel 路由失败且无 selectedAgentId 时 message.error 使用 baseMsg + routeFailedHint |
| 页面操作超时提示 | 通过 | ChatMessageItem 在 tc.status === 'error' 时展示 pageOpTimeoutHint |

### 5. i18n 与 Lint

| 检查项 | 结论 |
|--------|------|
| globalAiChat 新增 key | 通过 | copySuccess、generationStopped、retry、consentFirstTimeHint、exportFormatMarkdown、exportFormatPlainText、routeFailedHint、pageOpTimeoutHint 在 zh-CN / en-US 均已存在 |
| Lint | 通过 | CommandBar、use-ai-chat、ChatMessageItem、AIChatSlidePanel、user/ai-chat 无报错 |

---

## 二、边界与一致性审计

### 2.1 retryLastMessage

- **prev.attachments 为空**：仅当 `prev.attachments?.length` 时设置 `pendingAttachments`，未清空。若之前有残留（理论上 sendMessage 已 clear），可能带旧附件重发。**建议**：在 retryLastMessage 开头先 `clearPendingAttachments()`，再按 prev 恢复，避免脏状态。

### 2.2 重试按钮仅应对「最后一条」失败消息

- **现象**：重试按钮仅根据 `msg.requestFailedRetry` 显示，不区分是否为当前最后一条。用户若在失败后继续发新消息，旧失败条仍显示「重试」，但点击后 retryLastMessage 检查的是 `messages.at(-1)`（新消息），无 requestFailedRetry 会直接 return，按钮无效。
- **建议**：仅对「最后一条消息」展示重试。做法：在两处使用 ChatMessageItem 的父组件中传入 `is-last="idx === chatMessages.length - 1"`，ChatMessageItem 中重试区域改为 `v-if="msg.requestFailedRetry && isLast"`。

### 2.3 服务端 SSE 内 event.error 未标 requestFailedRetry

- **现状**：onError（网络/Abort）时设置 `msg.requestFailedRetry = true`；流式解析里 `event.error` 分支（L1115-1118）只设置了 `msg.content`，未设 `requestFailedRetry`。
- **影响**：服务端通过 event 返回错误时，不会出现「重试」按钮，仅网络层错误会显示。
- **建议**：在 `else if (event.error)` 分支内同样设置 `msg.requestFailedRetry = true`，并在该分支后调用 finalizeMessage（若尚未统一在流结束处调用则需确认一次调用即可）。

### 2.4 新建会话时交互模式延续

- **现状**：startNewConversation 会清空当前会话状态，但输入区的交互模式选择会沿用用户刚才的选择。
- **影响**：如果用户上一会话选择了 `trusted_auto`，新会话打开时仍会显示该模式；真正是否自动批准仍以后端运行时信任策略判定为准，未命中策略时会自动降级为 `confirm`。
- **结论**：这是当前产品语义允许的行为；前端不再维护 `trustSession` 一类会话级“授权真相”。

### 2.5 validateUpload 未再弹窗

- **现状**：validateUpload 仅 return result.valid，未在 valid 为 false 时再调 message.warning。validateChatFile/validateFile 内部已对图片/扩展名/大小做 message.warning。
- **结论**：按方案「若未弹窗，可补」为可选；当前校验路径已有提示，无必须修改。

---

## 三、消费者与回归面

- **ChatMessageItem**：仅 AIChatSlidePanel 与 views/user/ai-chat 使用，两处均已绑定 @retry、并传入所需 props，无遗漏。
- **useAIChat**：仅上述两处与 command-bar 相关逻辑使用；command-bar 仅负责打开面板与提交文案，不直接依赖 retryLastMessage/interactionMode 等新增行为，无回归风险。
- **CommandBar**：mention 与菜单搜索的键盘逻辑未改，仅输入控件由 input 改为 TextArea，行为符合预期。

---

## 四、审计结论汇总

- **与方案一致**：问题 1、问题 2 及 P1/P2 所列项均已按方案实现，无漏做或做错。
- **建议修复/增强**（按优先级）：
  1. **建议**：重试按钮仅对最后一条消息显示（传入 isLast 或等价方式），避免失效的重试按钮残留。
  2. **建议**：retryLastMessage 开头调用 clearPendingAttachments()，再根据 prev 恢复附件，避免脏附件。
  3. **可选**：SSE 流内 event.error 分支设置 requestFailedRetry 并保证 finalizeMessage 调用一致，使服务端错误也可重试。
  4. **可选**：若产品希望新会话默认回到保守模式，可在 startNewConversation 时主动将交互模式重置为 `confirm`。

以上为本次实施的全面审计结果与可跟进项。
