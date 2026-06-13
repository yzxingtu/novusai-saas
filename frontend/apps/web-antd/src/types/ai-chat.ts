/**
 * AI chat shared types / AI 对话共享类型
 *
 * Shared data structures used across API, stores, composables, and UI surfaces.
 * 供 API、store、composables 与 UI 共用的数据结构。
 */

import type { AppErrorInfo } from '#/utils/request';

export type InteractionMode = 'confirm' | 'trusted_auto';

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

export interface AgentSkillBindingSummary {
  enabled?: boolean;
  id?: number;
  name?: null | string;
  package_id?: null | number;
  package_name?: null | string;
  skill_id?: number;
  skill_key?: null | string;
  skill_name?: null | string;
  type?: null | string;
}

export interface AgentKnowledgeBaseBindingSummary {
  enabled?: boolean;
  id?: number;
  kb_name?: null | string;
  knowledge_base_id?: number;
  name?: null | string;
}

export type AgentKnowledgeBaseBindingsByAgentId = Record<
  number,
  AgentKnowledgeBaseBindingSummary[]
>;

export type AgentSkillBindingsByAgentId = Record<
  number,
  AgentSkillBindingSummary[]
>;

/** KB row for @ mention panel (aligns with ChatKBBindingInfo) / @ 面板知识库行 */
export interface MentionKnowledgeBaseBinding {
  knowledge_base_id: number;
  kb_name: null | string;
}

/** Skill package row for @ mention panel / @ 面板技能包行 */
export interface MentionSkillPackageBinding {
  package_id?: null | number;
  package_name?: null | string;
  skill_id: number;
  skill_name?: null | string;
}

/** Unified @ candidate: bound KBs and skill packages / 统一 @ 候选：已绑定知识库与技能包 */
export type MentionCandidate =
  | {
      binding: MentionKnowledgeBaseBinding;
      kind: 'knowledge_base';
    }
  | {
      binding: MentionSkillPackageBinding;
      kind: 'skill_package';
    };

export interface SelectedSkillPackageChip {
  id: string;
  label: string;
  value: string;
}

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
  skills?: AgentSkillBindingSummary[] | null;
  knowledge_base_ids?: null | number[];
  knowledge_bases?: AgentKnowledgeBaseBindingSummary[] | null;
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
  updated_at?: string;
  message_count?: number;
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
  /** Source classification from backend; historical records may still carry legacy values. */
  source_kind?: 'ephemeral_doc' | 'formal_kb';
  /** Source knowledge base (when provided by RAG) / 片段所属知识库 */
  knowledge_base_id?: number;
  knowledge_base_name?: null | string;
}

export type TurnFlowStageType =
  | 'answer_assembly'
  | 'completed'
  | 'failed'
  | 'retrieval'
  | 'thinking'
  | 'tool_execution'
  | 'tool_selection';

export type TurnFlowStageStatus =
  | 'completed'
  | 'error'
  | 'interrupted'
  | 'running'
  | 'skipped';

export interface TurnFlowStage {
  detailLines?: string[];
  durationMs?: number;
  endedAtMs?: number;
  id: string;
  metrics?: Record<string, number | string>;
  sourceRefs?: string[];
  startedAtMs?: number;
  status: TurnFlowStageStatus;
  summary?: string;
  title?: string;
  toolCallIds?: string[];
  type: TurnFlowStageType;
}

export type TurnFlowEvidenceKind =
  | 'document'
  | 'knowledge_base'
  | 'memory'
  | 'tool';

export interface TurnFlowEvidenceItem {
  arguments?: Record<string, unknown>;
  badge?: string;
  chunkId?: number;
  displayName?: string;
  docId?: number;
  docName?: string;
  durationMs?: number;
  error?: string;
  errorType?: string;
  id: string;
  kind: TurnFlowEvidenceKind;
  knowledgeBaseId?: number;
  knowledgeBaseName?: null | string;
  output?: string;
  resultLink?: string;
  score?: number;
  skillName?: string;
  skillType?: string;
  sourceKind?: 'ephemeral_doc' | 'formal_kb' | string;
  snippet?: string;
  startedAt?: number;
  status?: 'error' | 'running' | 'success';
  sourceRef?: string;
  summaryPayload?: Record<string, unknown>;
  title?: string;
  toolCallId?: string;
  toolName?: string;
  url?: string;
}

export interface TurnFlowAnswerCardSection {
  body?: string;
  bullets?: string[];
  content?: string;
  id?: string;
  title?: string;
}

export interface TurnFlowAnswerCard {
  confidenceLabel?: string;
  followUpSuggestions?: string[];
  sections?: TurnFlowAnswerCardSection[];
  sourceChipIds?: string[];
  summary?: string;
}

export interface TurnFlowErrorSurface {
  debugMessage?: string;
  detail?: string;
  error?: string;
  errorType?: string;
  message?: string;
  reason?: string;
  summary?: string;
  traceId?: string;
}

export interface TurnFlowViewModel {
  answerCard?: TurnFlowAnswerCard;
  complete?: boolean;
  completionReason?: string;
  evidence: TurnFlowEvidenceItem[];
  finalStageStatus?: TurnFlowStageStatus;
  interrupted?: boolean;
  timeline: TurnFlowStage[];
  traceId?: string;
  errorSurface?: TurnFlowErrorSurface;
  failureKind?: string;
  turnOutcome?: string;
}

export interface TurnFlowStagePayload extends Partial<TurnFlowStage> {
  detail_lines?: string[];
  duration_ms?: number;
  ended_at_ms?: number;
  source_refs?: string[];
  stage_id?: string;
  stage_type?: TurnFlowStageType;
  started_at_ms?: number;
  tool_call_ids?: string[];
}

export interface TurnFlowEvidenceItemPayload extends Partial<TurnFlowEvidenceItem> {
  chunk_id?: number;
  doc_id?: number;
  doc_name?: string;
  document_id?: number;
  document_name?: string;
  knowledge_base_id?: number;
  knowledge_base_name?: null | string;
  source_kind?: string;
  source_ref?: string;
  tool_call_id?: string;
}

export type TurnFlowAnswerCardSectionPayload =
  Partial<TurnFlowAnswerCardSection>;

export interface TurnFlowAnswerCardPayload {
  confidence_label?: string;
  follow_up_suggestions?: string[];
  confidenceLabel?: string;
  followUpSuggestions?: string[];
  sections?: Array<string | TurnFlowAnswerCardSectionPayload>;
  source_chip_ids?: string[];
  sourceChipIds?: string[];
  summary?: string;
}

export interface TurnFlowErrorSurfacePayload extends Partial<TurnFlowErrorSurface> {
  debug_message?: string;
  error_type?: string;
  trace_id?: string;
}

export interface TurnFlowViewPayload extends Partial<
  Omit<
    TurnFlowViewModel,
    'answerCard' | 'errorSurface' | 'evidence' | 'timeline'
  >
> {
  answerCard?: null | TurnFlowAnswerCardPayload;
  answer_card?: null | TurnFlowAnswerCardPayload;
  completion_reason?: string;
  errorSurface?: null | TurnFlowErrorSurfacePayload;
  error_surface?: null | TurnFlowErrorSurfacePayload;
  evidence?: TurnFlowEvidenceItemPayload[];
  failure_kind?: string;
  final_stage_status?: TurnFlowStageStatus;
  sources?: TurnFlowEvidenceItemPayload[];
  stages?: TurnFlowStagePayload[];
  timeline?: TurnFlowStagePayload[];
  trace_id?: string;
  turn_flow_complete?: boolean;
  turn_outcome?: string;
}

export interface ChatAttachment {
  attachment_id?: number;
  type: 'audio' | 'file' | 'image' | 'video';
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
  /** Structured summary payload from backend SSE / 后端 SSE 下发的结构化摘要 */
  summaryPayload?: Record<string, unknown>;
  /** Link to view the created/updated resource / 查看创建/更新资源的链接 */
  resultLink?: string;
  /** Error type for tool actions: timeout, user_cancelled, not_registered, invalid_input, etc. / 工具动作错误类型 */
  errorType?: string;
  /** Timestamp when tool_start was received (for "still running" hint after 8s) / 收到 tool_start 的时间戳 */
  startedAt?: number;
}

export interface ToolApprovalPresentationTarget {
  label?: string;
  name?: string;
  type?: string;
  value?: string;
  [key: string]: unknown;
}

export interface ToolApprovalPresentationDetail {
  key?: string;
  label?: string;
  sensitive?: boolean;
  value?: unknown;
  valueText?: string;
  value_text?: string;
  [key: string]: unknown;
}

export interface ToolApprovalPresentation {
  actionLabel?: string;
  action_label?: string;
  businessAreaLabel?: string;
  business_area_label?: string;
  details?: ToolApprovalPresentationDetail[];
  detailFields?: ToolApprovalPresentationDetail[];
  detail_fields?: ToolApprovalPresentationDetail[];
  menuLabel?: string;
  menu_label?: string;
  operationType?: string;
  operation_type?: string;
  permissionCode?: string;
  permission_code?: string;
  riskLabel?: string;
  riskLevel?: string;
  risk_label?: string;
  risk_level?: string;
  safeDetails?: ToolApprovalPresentationDetail[];
  safe_details?: ToolApprovalPresentationDetail[];
  summary?: string;
  target?: string | ToolApprovalPresentationTarget;
  targetLabel?: string;
  targetText?: string;
  target_label?: string;
  target_text?: string;
  technical?: Record<string, unknown>;
  technicalDetails?: Record<string, unknown>;
  technical_details?: Record<string, unknown>;
  title?: string;
  [key: string]: unknown;
}

export interface PendingConfirmation {
  action?: string;
  approvalPresentation?: ToolApprovalPresentation;
  preview?: Record<string, unknown>;
  table?: string;
  toolName?: string;
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
  clientKey: string;
  role: 'assistant' | 'user';
  content: string;
  /** Unified turn flow read-model used by timeline/evidence UI / 统一轮次流程读模型 */
  turnFlow?: TurnFlowViewPayload;
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
  /** Agent-bound skill summaries when included by message payload / 消息携带的智能体技能绑定摘要 */
  agent_skills?: AgentSkillBindingSummary[] | null;
  /** Agent-bound KB ids when included by message payload / 消息携带的智能体知识库 ID */
  agent_knowledge_base_ids?: null | number[];
  /** Agent-bound KB summaries when included by message payload / 消息携带的智能体知识库摘要 */
  agent_knowledge_bases?: AgentKnowledgeBaseBindingSummary[] | null;
  /** LLM model name used by the agent / 智能体使用的模型名 */
  model_name?: null | string;
  attachments?: ChatAttachment[];
  /** Pending CRUD confirmation request from tool / 待确认的 CRUD 请求 */
  pendingConfirmation?: PendingConfirmation;
  /** Pending tool consent request (consent_mode=ask) / 待用户同意的工具请求 */
  pendingConsent?: PendingConsent;
  /** Interactive action buttons for user to click / 可点击的操作按钮 */
  actionButtons?: ActionButton[];
  /** Whether action buttons have been used (disabled after click) / 操作按钮是否已使用 */
  actionButtonsUsed?: boolean;
  /** Generated images from image generation models / 生成图片列表 */
  imageResults?: ImageResult[];
  /** Whether session memory was updated during this response / 本次回复是否更新了会话记忆 */
  memoryUpdated?: boolean;
  /** Whether a compacted context snapshot was used / 是否使用了压缩上下文快照 */
  contextCompacted?: boolean;
  /** Whether a pre-compaction memory flush was triggered / 是否触发了压缩前记忆冲刷 */
  memoryFlushTriggered?: boolean;
  /** Whether long-term memory recall was injected / 是否注入了长期记忆召回 */
  memoryRecalled?: boolean;
  /** Prompt-only pruning diagnostics / 仅 prompt 层裁剪诊断 */
  pruneStats?: Record<string, unknown>;
  /** RAG source kinds used in this turn / 本轮使用的 RAG 来源类型 */
  ragSourceKinds?: string[];
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
  /** Structured error payload for UI rendering / 结构化错误对象，用于统一展示 */
  error?: AppErrorInfo;
}
