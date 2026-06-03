# AI Writing 规范

> 本文档覆盖富文本编辑器 AI 写作能力，不属于通用 Agent Chat 页面能力。
> 适用范围：`/admin/ai/writing/{feature}`、`/tenant/ai/writing/{feature}`、富文本编辑器 `useEditorAI()`、`system.ai_writing` 智能体分配。

---

## 一、架构总览

```
RichTextEditor / useEditorAI()
  -> requestClient.postSSE('/admin|/tenant/ai/writing/{feature}')
  -> AIWriting endpoint
  -> writing_service.stream_writing_feature()
  -> AgentAssignmentService resolve('system.ai_writing')
  -> AgentChatService.stream_chat_ephemeral()
  -> SSE delta stream
  -> 前端接受结果并插入编辑器
```

核心原则：

- AI 写作必须复用平台级功能码 `system.ai_writing`
- 编辑器侧不得直接调用 `AIGateway`
- 管理端与企业端共用同一套写作服务，只是 `tenant_id` 不同
- 输出是 SSE 文本增量，不是一次性 JSON 响应

---

## 二、后端入口

### 路由

| 端 | 路径 | 文件 |
|----|------|------|
| Admin | `/admin/ai/writing/{feature}` | `backend/app/api/admin/ai_writing.py` |
| Tenant | `/tenant/ai/writing/{feature}` | `backend/app/api/tenant/ai_writing.py` |

### 支持的 feature

`VALID_FEATURES` 定义于 `backend/app/services/ai/writing_service.py`：

- `continue`
- `optimize`
- `proofread`
- `translate`
- `summarize`
- `expand`
- `rewrite`
- `custom`
- `chat`

新增 feature 时，必须同时更新：

1. `VALID_FEATURES`
2. `_PROMPTS`
3. 前端工具栏或编辑器调用入口

只改前端按钮或只改后端 prompt 都不算完成。

---

## 三、请求体契约

`AIWritingRequest` 当前字段：

| 字段 | 说明 | 限制 |
|------|------|------|
| `selected_text` | 选中文本 | 10000 |
| `before_text` | 光标前上下文 | 5000 |
| `after_text` | 光标后上下文 | 2000 |
| `context_title` | 文档标题 | 200 |
| `instruction` | 自定义指令 / chat 输入 | 2000 |
| `target_lang` | 翻译目标语言 | 50 |
| `history` | chat 历史消息 | 可空 |

`writing_service.build_ai_messages()` 会进一步裁剪：

- `selected_text` 最多 5000
- `before_text` 只取最后 2000
- `after_text` 只取前 500
- `instruction` 最多 1000

前端不要再自行做另一套不一致的截断规则。

---

## 四、Agent 解析规则

AI 写作不绑定固定 Agent ID，而是运行时解析：

- 功能码固定：`system.ai_writing`
- 平台端：走全局分配
- 企业端：优先企业覆盖，其次平台默认

解析流程：

1. `AgentAssignmentService.resolve_for_tenant()` 或 `resolve()`
2. 校验 assignment 是否存在且有 `agent_id`
3. 校验 Agent 未删除且状态为 `published`
4. 通过 `AgentChatService.stream_chat_ephemeral()` 发起临时会话

禁止事项：

- 禁止在前端硬编码 `agent_id`
- 禁止在 Controller 中直接实例化 `AIGateway`
- 禁止绕过 `system.ai_writing` 自建第二套“编辑器专用 AI 路由”

---

## 五、SSE 约定

后端返回：

- `event=message` + `delta`
- `event=done`
- 错误时 `format_error("AI_WRITING_ERROR", ...)`

前端 `useEditorAI()` 通过 `requestClient.postSSE()` 统一处理：

- 解析 `data: ...` 行
- 读取 `event === 'message'` 的 `delta`
- 忽略无法解析的行
- 支持 `AbortController` 取消

不要在具体页面里复制一份 SSE 解析器。编辑器 AI 相关页面统一复用 `frontend/apps/web-antd/src/components/business/rich-text-editor/ai/useEditorAI.ts`。

---

## 六、格式化输出

### 纯文本模式

- 默认按普通文本处理
- `acceptResult(false)` 直接把结果插入 TipTap

### Markdown 模式

- 当前由前端通过 `extra.withFormat` 触发
- `useEditorAI()` 会追加 `format_instruction`
- 返回结果先经 `markdown-it` 转为 HTML，再插入编辑器

规则：

- 需要结构化输出时，优先走 `withFormat`
- 不要在后端硬编码某个 feature 必须输出 HTML
- 不要让模型直接回传完整 JSON/HTML 控制协议给用户

---

## 七、前端接入规则

### 统一入口

`frontend/apps/web-antd/src/components/business/rich-text-editor/ai/useEditorAI.ts`

### 路径选择

`getAIWritingPath()` 当前根据浏览器 URL 判断：

- `/admin/*` -> `/admin/ai/writing/{feature}`
- 其他后台编辑器页 -> `/tenant/ai/writing/{feature}`

因此：

- 管理端编辑器不要手写 tenant 路径
- 企业端编辑器不要复写 admin 路径

### 上下文提取

统一通过编辑器 selection 和全文文本提取：

- `selected_text`
- `before_text`
- `after_text`

不要在业务页面自己再组装另一套上下文字段名。

---

## 八、常见失败点

| 场景 | 现象 | 原因 |
|------|------|------|
| feature 非法 | 400 | 未在 `VALID_FEATURES` 注册 |
| 功能未配置 | BusinessException | `system.ai_writing` 未绑定 Agent |
| Agent 不可用 | BusinessException | Agent 已删除或未发布 |
| SSE 无增量 | 前端只有空白结果 | 使用了错误路径或未复用 `postSSE` |
| 输出格式异常 | 插入后排版错乱 | 本应 `withFormat` 却按纯文本接收 |

---

## 九、文件索引

| 文件 | 职责 |
|------|------|
| `backend/app/api/admin/ai_writing.py` | 管理端 AI Writing SSE 入口 |
| `backend/app/api/tenant/ai_writing.py` | 企业端 AI Writing SSE 入口 |
| `backend/app/services/ai/writing_service.py` | feature prompt、Agent 解析、SSE 转发 |
| `frontend/apps/web-antd/src/components/business/rich-text-editor/ai/useEditorAI.ts` | 前端统一 AI 写作 composable |
| `frontend/apps/web-antd/src/components/business/rich-text-editor/*` | 富文本编辑器与工具栏接入 |

---

## 十、检查清单

- [ ] 是否复用了 `/admin|/tenant/ai/writing/{feature}`，而不是新建私有端点
- [ ] 是否通过 `system.ai_writing` 分配 Agent，而不是硬编码 Agent ID
- [ ] 是否复用了 `useEditorAI()`，而不是在页面里手写 SSE
- [ ] 是否区分纯文本插入与 Markdown 格式插入
- [ ] 新增 feature 时是否同步更新后端 prompt 与前端入口
