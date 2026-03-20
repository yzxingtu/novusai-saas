/**
 * AI 对话面板共享类型 / AI Chat Panel - Shared Types
 *
 * 对话列表、消息、工具调用、待确认/待授权等数据结构。
 * Data structures for conversation list, messages, tool calls, pending confirmation/consent.
 */

export interface ModelCapabilities {
  supports_vision: boolean;
  supports_audio?: boolean;
  supports_video?: boolean;
  max_image_count: null | number;
  max_image_size_mb: null | number;
}

export interface InputVariable {
  name: string;
  label: string;
  type: string;
  required?: boolean;
  default?: string;
}

/** KB row for @ mention panel (aligns with ChatKBBindingInfo) / @ 面板知识库行 */
export interface MentionKnowledgeBaseBinding {
  knowledge_base_id: number;
  kb_name: null | string;
}

/** Unified @ candidate: agent or bound knowledge base / 统一 @ 候选 */
export type MentionCandidate =
  | { kind: 'agent'; agent: AgentItem }
  | { kind: 'knowledge_base'; binding: MentionKnowledgeBaseBinding };

export interface AgentItem {
  id: number;
  tenant_id: number;
  name: string;
  description: null | string;
  avatar: null | string;
  status: string;
  model_name?: null | string;
  model_capabilities?: ModelCapabilities | null;
  welcome_message?: null | string;
  suggested_questions?: null | string[];
  input_variables?: InputVariable[] | null;
}

export function getAgentInputVariables(
  agent?: null | Pick<AgentItem, 'input_variables'>,
): InputVariable[] {
  return Array.isArray(agent?.input_variables) ? agent.input_variables : [];
}

export interface ConversationItem {
  id: number;
  agent_id: number;
  title: null | string;
  status: string;
  created_at: string;
  /** Agent name (enriched by global conversations API) / 智能体名称 */
  agent_name?: null | string;
  /** Agent avatar URL (enriched by global conversations API) / 智能体头像 URL */
  agent_avatar?: null | string;
}

export interface RagSource {
  doc_name: string;
  doc_id: number;
  score: number;
  snippet: string;
  page?: number;
  heading?: string;
  /** Source knowledge base (when provided by RAG) / 片段所属知识库 */
  knowledge_base_id?: number;
  knowledge_base_name?: null | string;
}

export interface ChatAttachment {
  type: 'file' | 'image' | 'audio' | 'video';
  url: string;
  name?: string;
  mime_type?: string;
  preview?: string;
}

export interface ToolCallEvent {
  /** Tool call ID from LLM/SSE (for associating pending confirmation card) / 工具调用 ID，用于关联待确认卡片 */
  id?: string;
  name: string;
  /** 'running' = tool_start received, 'success'/'error' = tool_call received / 工具调用状态 */
  status: 'error' | 'running' | 'success';
  arguments?: Record<string, unknown>;
  output?: string;
  error?: string;
  durationMs?: number;
  skillName?: string;
  skillType?: string;
  /** Human-friendly display name for the tool / 工具展示名称 */
  displayName?: string;
  /** One-line summary of the tool execution result / 工具执行结果摘要 */
  summary?: string;
  /** Link to view the created/updated resource / 查看创建/更新资源的链接 */
  resultLink?: string;
  /** Error type for page ops: timeout, user_cancelled, not_registered, invalid_input, etc. / 页面操作错误类型 */
  errorType?: string;
  /** Timestamp when tool_start was received (for "still running" hint after 8s) / 收到 tool_start 的时间戳 */
  startedAt?: number;
}

export interface PendingConfirmation {
  action: string;
  table: string;
  preview?: Record<string, unknown>;
  /** Whether the user has responded (confirmed or rejected) / 用户是否已响应 */
  resolved?: boolean;
}

export interface PendingConsent {
  toolName: string;
  arguments?: Record<string, unknown>;
  skillName?: string;
  skillType?: string;
  /** Whether the user has responded (allowed or rejected) / 用户是否已响应 */
  resolved?: boolean;
  /** Whether the consent was rejected (vs approved) / 是否被拒绝 */
  rejected?: boolean;
  /** Whether auto-approved by trust session / 是否由信任会话自动通过 */
  autoApproved?: boolean;
}

export interface ActionButton {
  /** Display label for the button / 按钮展示文案 */
  label: string;
  /** Value sent as user message when clicked / 点击后作为用户消息发送的值 */
  value: string;
  /** Button style: primary, default, or danger / 按钮样式 */
  style?: 'danger' | 'default' | 'primary';
}

export interface ImageResult {
  /** Image URL / 图片 URL */
  url: string;
  /** Whether the URL is base64 encoded / 是否为 base64 */
  isBase64?: boolean;
  /** Revised prompt from the model / 模型修订后的提示词 */
  revisedPrompt?: string;
}

export interface ChatMessage {
  role: 'assistant' | 'user';
  content: string;
  /** Streaming thinking/reasoning content shown separately from final answer / 与最终答复分开展示的思考内容 */
  thinkingContent?: string;
  streaming?: boolean;
  tokenUsage?: number;
  durationMs?: number;
  /** Agent ID (for multi-agent conversation tracking) / 智能体 ID */
  agent_id?: null | number;
  /** Agent name (resolved from agents list) / 智能体名称 */
  agent_name?: null | string;
  /** Agent avatar URL (resolved from agents list) / 智能体头像 URL */
  agent_avatar?: null | string;
  /** Agent description (resolved from agents list) / 智能体描述 */
  agent_description?: null | string;
  /** LLM model name used by the agent / 智能体使用的模型名 */
  model_name?: null | string;
  /** Route source marker for UI badges (e.g. one-time @ mention) / 路由来源标记 */
  routeSource?: null | string;
  ragSources?: RagSource[];
  attachments?: ChatAttachment[];
  toolCalls?: ToolCallEvent[];
  /** Pending CRUD confirmation request from tool / 待确认的 CRUD 请求 */
  pendingConfirmation?: PendingConfirmation;
  /** Pending tool consent request (consent_mode=ask) / 待用户同意的工具请求 */
  pendingConsent?: PendingConsent;
  /** Tool optimizer result (shown when tools were pre-filtered) / 工具优化结果 */
  optimizingTools?: { selected: number; total: number };
  /** Interactive action buttons for user to click / 可点击的操作按钮 */
  actionButtons?: ActionButton[];
  /** Whether action buttons have been used (disabled after click) / 操作按钮是否已使用 */
  actionButtonsUsed?: boolean;
  /** Generated images from image generation models / 生成图片列表 */
  imageResults?: ImageResult[];
  /** Whether session memory was updated during this response / 本次回复是否更新了会话记忆 */
  memoryUpdated?: boolean;
  /** Message creation timestamp (ISO string) / 消息创建时间 */
  created_at?: string;
  /** Persisted partial response marker / 持久化的未完成回复标记 */
  partial?: boolean;
  /** Persisted interrupted response marker / 持久化的中断回复标记 */
  interrupted?: boolean;
  /** Completion reason persisted from backend / 后端持久化的结束原因 */
  completionReason?: string;
  /** Set when user clicked stop during streaming; show "（生成已停止）" / 用户停止生成 */
  stoppedByUser?: boolean;
  /** Set when SSE onError (non-Abort); show retry button / 请求失败需重试 */
  requestFailedRetry?: boolean;
}

