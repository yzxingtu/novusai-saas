/**
 * AI Chat API (shared) / AI Chat API（共享）
 *
 * Wraps all requestClient calls from use-ai-chat.ts.
 * Differentiates admin/tenant via apiPrefix parameter.
 * 封装 use-ai-chat.ts 中的所有 requestClient 调用。
 */
import type {
  TurnContextSourcePayload,
  TurnRecordPayload,
} from '#/api/shared/types';
import type { ChatAttachment, RagSource } from '#/types/ai-chat';

import { smartUploadFile as adminSmartUploadFile } from '#/api/admin/attachment';
import { smartUploadFile as tenantSmartUploadFile } from '#/api/tenant/attachment';
import { smartUploadFile as userSmartUploadFile } from '#/api/user/attachment';
import { toAbsoluteApiUrl } from '#/utils/image';
import { requestClient } from '#/utils/request';

export type { TurnContextSourcePayload, TurnRecordPayload };

// ============ Types / 类型 ============

export interface PaginatedResponse<T = Record<string, unknown>> {
  items: T[];
  total: number;
}

export type InteractionMode = 'confirm' | 'trusted_auto';

export interface RawMessageItem {
  agent_avatar?: null | string;
  agent_id?: null | number;
  agent_name?: null | string;
  role: string;
  content: null | string;
  created_at?: null | string;
  model_id?: null | number;
  model_name?: null | string;
  provider_id?: null | number;
  provider_name?: null | string;
  tool_calls?: Array<{
    display_name?: string;
    duration_ms?: number;
    error_type?: string;
    function?: { arguments?: string; name?: string };
    id?: string;
    package_name?: string;
    pending_confirmation?: {
      action?: string;
      preview?: Record<string, unknown>;
      table?: string;
      tool_name?: string;
    };
    pending_consent?: {
      arguments?: Record<string, unknown>;
      package_name?: string;
      skill_name?: string;
      tool_name?: string;
    };
    result_link?: string;
    skill_name?: string;
    success?: boolean;
    summary?: string;
    summary_payload?: Record<string, unknown>;
  }> | null;
  tool_call_id?: null | string;
  tool_name?: null | string;
  metadata?: null | {
    action_buttons?: Array<{
      label: string;
      style?: 'danger' | 'default' | 'primary';
      value: string;
    }>;
    action_buttons_used?: boolean;
    attachments?: ChatAttachment[];
    completion_reason?: string;
    context_compacted?: boolean;
    context_sources?: TurnContextSourcePayload[];
    error?: boolean;
    error_debug_message?: string;
    error_message?: string;
    error_only?: boolean;
    error_trace_id?: string;
    error_type?: string;
    interrupted?: boolean;
    memory_flush_triggered?: boolean;
    memory_recalled?: boolean;
    memory_updated?: boolean;
    model_name?: string;
    partial?: boolean;
    pending_confirmation?: {
      action?: string;
      preview?: Record<string, unknown>;
      resolved?: boolean;
      table?: string;
      tool_name?: string;
    };
    pending_consent?: {
      arguments?: Record<string, unknown>;
      auto_approved?: boolean;
      package_name?: string;
      rejected?: boolean;
      resolved?: boolean;
      skill_name?: string;
      tool_name?: string;
    };
    protocol_path?: string;
    provider_id?: number;
    provider_name?: string;
    prune_stats?: Record<string, unknown>;
    rag_source_kinds?: string[];
    rag_sources?: RagSource[];
    route_source?: string;
    selected_skill_names?: string[];
    selected_tool_names?: string[];
    termination_reason?: string;
    thinking_content?: string;
    tool_display_name?: string;
    tool_error?: string;
    tool_error_type?: string;
    tool_result_link?: string;
    tool_success?: boolean;
    tool_summary?: string;
    tool_summary_payload?: Record<string, unknown>;
    turn_outcome?: string;
    turn_record?: TurnRecordPayload;
  };
}

export interface ConversationDetailResponse {
  agent_id?: null | number;
  context_diagnostics?: null | Record<string, unknown>;
  interaction_mode_effective?: InteractionMode;
  interaction_mode_requested?: InteractionMode;
  last_run_summary?: null | Record<string, unknown>;
  message_list: RawMessageItem[];
}

export interface FileUploadResponse {
  url: string;
  attachment: {
    extension?: null | string;
    id: number;
    mime_type?: null | string;
    name?: string;
    original_name?: null | string;
    preview_url?: null | string;
    previewUrl?: null | string;
    size?: number;
  };
  used_bytes: number;
}

export interface TrustPolicyRef {
  policy_ids?: number[];
  allowed_tool_names?: string[];
  tool_families?: string[];
  risk_level_cap?: null | string;
}

export interface SSEOptions {
  abortController: AbortController;
  onMessage: (rawChunk: string) => Promise<void> | void;
  onEnd: () => void;
  onError: (error: Error) => void;
}

type ChatUploadEndpoint = 'admin' | 'tenant' | 'user';

// ============ API Functions / 接口函数 ============

function chatBaseUrl(apiPrefix: string): string {
  return `${apiPrefix}/ai/agent-chat`;
}

/**
 * Get published agent list / 获取已发布智能体列表
 *
 * Admin: returns only admin-usable resource scopes (admin_only / global_shared / admin_and_selected_tenants).
 * Tenant: backend auto-filters by tenant_id + scope.
 * 管理端：仅返回管理端可用资源作用域；企业端：后端自动过滤。
 */
export async function getChatAgentsApi<T = Record<string, unknown>>(
  apiPrefix: string,
): Promise<PaginatedResponse<T>> {
  const params: Record<string, number | string> = {
    'filter[status][eq]': 'published',
    'page[size]': 100,
  };
  if (apiPrefix.includes('/admin')) {
    params['filter[scope][in]'] =
      'admin_only,global_shared,admin_and_selected_tenants';
  }
  return requestClient.get<PaginatedResponse<T>>(`${apiPrefix}/ai/agents`, {
    params,
  });
}

/**
 * Get global conversation list (cross-agent) / 获取全局对话列表（跨智能体）
 */
export async function getGlobalConversationsApi<T = Record<string, unknown>>(
  apiPrefix: string,
  pageSize = 50,
): Promise<PaginatedResponse<T>> {
  return requestClient.get<PaginatedResponse<T>>(
    `${chatBaseUrl(apiPrefix)}/conversations`,
    { params: { 'page[size]': pageSize, sort: '-created_at' } },
  );
}

/**
 * Delete conversation / 删除对话
 */
export async function deleteChatConversationApi(
  apiPrefix: string,
  conversationId: number,
): Promise<unknown> {
  return requestClient.delete(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}`,
  );
}

/**
 * Update conversation title / 更新对话标题
 */
export async function updateChatConversationTitleApi(
  apiPrefix: string,
  conversationId: number,
  title: string,
): Promise<{ id: number; title: null | string }> {
  return requestClient.patch<{ id: number; title: null | string }>(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}`,
    { title },
  );
}

/**
 * Clear conversation memory state (without deleting messages) / 清空会话记忆状态
 */
export async function clearChatConversationMemoryApi(
  apiPrefix: string,
  conversationId: number,
): Promise<{ deleted_count: number }> {
  return requestClient.delete<{ deleted_count: number }>(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}/memory-state`,
  );
}

/**
 * Get conversation memory state (preferences/constraints/tasks/facts) / 获取会话记忆状态
 */
export interface MemoryState {
  preferences: string[];
  constraints: string[];
  task_states: string[];
  verified_facts: string[];
  version: number;
  updated_at: number;
}

export async function getChatConversationMemoryApi(
  apiPrefix: string,
  conversationId: number,
): Promise<MemoryState> {
  return requestClient.get<MemoryState>(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}/memory-state`,
  );
}

/**
 * Get conversation message list / 获取对话消息列表
 */
export async function getChatConversationMessagesApi(
  apiPrefix: string,
  conversationId: number,
): Promise<ConversationDetailResponse> {
  return requestClient.get<ConversationDetailResponse>(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}`,
  );
}

export async function compactChatConversationApi(
  apiPrefix: string,
  conversationId: number,
): Promise<Record<string, unknown>> {
  return requestClient.post<Record<string, unknown>>(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}/compact`,
  );
}

export async function getChatConversationTimelineApi(
  apiPrefix: string,
  conversationId: number,
): Promise<ConversationTimelineItem[]> {
  return requestClient.get<ConversationTimelineItem[]>(
    `${chatBaseUrl(apiPrefix)}/conversations/${conversationId}/timeline`,
  );
}

function resolveChatUploadEndpoint(uploadUrl: string): ChatUploadEndpoint {
  if (uploadUrl.startsWith('/admin/')) {
    return 'admin';
  }
  if (uploadUrl.startsWith('/api/user/')) {
    return 'user';
  }
  return 'tenant';
}

/**
 * Upload chat attachment through standard smart-upload APIs / 通过标准 smart-upload API 上传聊天附件
 *
 * @param uploadUrl - Upload endpoint URL (used for endpoint resolution)
 * @param file - File to upload
 * @param extraData - Additional form fields (currently used for admin tenant_id)
 */
export async function uploadChatFileApi(
  uploadUrl: string,
  file: File,
  extraData?: Record<string, string>,
): Promise<FileUploadResponse> {
  const endpoint = resolveChatUploadEndpoint(uploadUrl);
  if (endpoint === 'admin') {
    const tenantId = Number(extraData?.tenant_id ?? '0');
    return adminSmartUploadFile({
      file,
      tenant_id: Number.isFinite(tenantId) ? tenantId : 0,
      visibility: 'private',
    });
  }
  if (endpoint === 'user') {
    return userSmartUploadFile({
      file,
      visibility: 'private',
    });
  }
  return tenantSmartUploadFile({
    file,
    visibility: 'private',
  });
}

export function normalizeChatAttachment(
  attachment: ChatAttachment,
): ChatAttachment {
  const normalizedUrl = toAbsoluteApiUrl(attachment.url) || attachment.url;
  const normalizedPreview =
    typeof attachment.preview === 'string'
      ? toAbsoluteApiUrl(attachment.preview) || attachment.preview
      : attachment.preview;

  return {
    ...attachment,
    url: normalizedUrl,
    ...(normalizedPreview ? { preview: normalizedPreview } : {}),
  };
}

export function normalizeChatAttachments(
  attachments?: ChatAttachment[] | null,
): ChatAttachment[] | undefined {
  if (!Array.isArray(attachments) || attachments.length === 0) {
    return undefined;
  }
  return attachments.map((attachment) => normalizeChatAttachment(attachment));
}

export function buildChatAttachmentFromUpload(
  file: File,
  upload: FileUploadResponse,
): ChatAttachment {
  const isImage = file.type.startsWith('image/');
  const isAudio = file.type.startsWith('audio/');
  const isVideo = file.type.startsWith('video/');
  let type: ChatAttachment['type'] = 'file';
  if (isImage) {
    type = 'image';
  } else if (isAudio) {
    type = 'audio';
  } else if (isVideo) {
    type = 'video';
  }
  const previewUrl =
    upload.attachment.previewUrl || upload.attachment.preview_url || upload.url;

  return normalizeChatAttachment({
    attachment_id: upload.attachment.id,
    type,
    url: type === 'image' ? previewUrl : upload.url,
    name: upload.attachment.original_name || file.name,
    mime_type: upload.attachment.mime_type || file.type,
  });
}

// ============ Route Types / 路由请求类型 ============

export type PageSurfaceKind =
  | 'drawer'
  | 'dropdown'
  | 'modal'
  | 'page'
  | 'popover';

export interface PageSurfaceSummary {
  kind: PageSurfaceKind;
  surface_id: string;
  title?: string;
}

export type ActiveFormMode = 'create' | 'edit' | 'unknown' | 'view';

export type ActiveFormStage =
  | 'failed'
  | 'filled_partial'
  | 'opening'
  | 'ready'
  | 'ready_to_submit'
  | 'submitted'
  | 'submitting'
  | 'validating';

export interface ActiveFormSummary {
  can_submit?: boolean;
  entity_name?: string;
  form_session_id: string;
  mode?: ActiveFormMode;
  record_id?: number | string;
  remaining_required_fields?: string[];
  stage?: ActiveFormStage;
  submit_policy?: 'auto' | 'confirm' | 'off';
}

export type PageContextSuggestedTool =
  | 'ui_click'
  | 'ui_fill_form'
  | 'ui_get_form_state'
  | 'ui_get_snapshot'
  | 'ui_list_interactables'
  | 'ui_open_surface'
  | 'ui_read_region'
  | 'ui_read_table'
  | 'ui_set_field'
  | 'ui_submit_form';

export interface PageContextSuggestedTools {
  primary: PageContextSuggestedTool[];
  reason?: string;
  secondary?: PageContextSuggestedTool[];
}

export interface PageContext {
  active_form_session_id?: string;
  active_form_summary?: ActiveFormSummary;
  active_surface_id?: string;
  locale?: string;
  page_key: string;
  page_session_id?: string;
  page_title?: string;
  suggested_tools?: PageContextSuggestedTools;
  surface_stack?: PageSurfaceSummary[];
  ui_epoch?: number;
}

export interface AgentChatImageParams {
  n?: number;
  quality?: string;
  size?: string;
  style?: string;
}

export interface AgentChatRequestBody {
  attachments?: ChatAttachment[];
  consented_actions?: string[];
  conversation_id?: null | number;
  image_params?: AgentChatImageParams;
  interaction_mode?: InteractionMode;
  interaction_updates?: Array<{
    action?: string;
    auto_approved?: boolean;
    kind: 'action_buttons' | 'pending_confirmation' | 'pending_consent';
    rejected?: boolean;
    table?: string;
    tool_name?: string;
    value?: string;
  }>;
  knowledge_base_ids?: number[];
  message?: string;
  /** 批量消息（800ms 内多条合并为一次请求） */
  messages?: string[];
  page_context?: null | PageContext;
  page_session_id?: null | string;
  route_source?: null | string;
  trust_policy_ref?: TrustPolicyRef;
  variables?: Record<string, string>;
}

export interface ConversationTimelineItem {
  auto_approved?: boolean;
  correlation_key?: null | string;
  detail_payload?: null | Record<string, unknown>;
  interaction_mode_effective?: InteractionMode;
  occurred_at: string;
  risk_level?: null | string;
  status: string;
  summary?: null | string;
  title: string;
  tool_name?: null | string;
  trace_id?: null | string;
  type: string;
}

export interface AgentRouteResponse {
  agent_id: number;
  agent_name: string;
  confidence: number;
  routed_by: string;
}

/**
 * Smart routing — select target agent based on message and context / 智能路由
 */
export async function routeMessageApi(
  apiPrefix: string,
  body: {
    conversation_id?: null | number;
    /** 强制重新路由，忽略当前对话已绑定的智能体 */
    force_reroute?: boolean;
    /** 含音频附件时传 true，后端可感知音频能力需求 */
    has_audio_attachments?: boolean;
    /** 含通用文件附件时传 true，用于路由上下文 */
    has_file_attachments?: boolean;
    /** 含图片附件时传 true，后端强制要求视觉能力 */
    has_image_attachments?: boolean;
    /** 含视频附件时传 true，后端可感知视频能力需求 */
    has_video_attachments?: boolean;
    message: string;
    page_context?: null | PageContext;
    pinned_agent_id?: null | number;
  },
): Promise<AgentRouteResponse> {
  return requestClient.post<AgentRouteResponse>(
    `${chatBaseUrl(apiPrefix)}/route`,
    body,
    {
      showCodeMessage: false,
      showErrorMessage: false,
    },
  );
}

// ============ Agent KB Bindings / 智能体知识库绑定 ============

export interface ChatKBBindingInfo {
  id: number;
  knowledge_base_id: number;
  kb_name: null | string;
  enabled: boolean;
}

/**
 * Get agent's bound knowledge base list (enabled only) / 获取智能体已绑定的知识库列表
 */
export async function getChatAgentKBBindingsApi(
  apiPrefix: string,
  agentId: number,
): Promise<ChatKBBindingInfo[]> {
  return requestClient.get<ChatKBBindingInfo[]>(
    `${apiPrefix}/ai/agents/${agentId}/knowledge-bases`,
  );
}

// ============ Agent Skill Bindings / 智能体技能绑定 ============

export interface ChatSkillBindingInfo {
  id: null | number;
  agent_id: number;
  skill_id: number;
  skill_name: null | string;
  skill_key?: null | string;
  skill_description?: null | string;
  skill_type?: null | string;
  enabled?: boolean;
  default_consent_mode?: string;
  package_id: null | number;
  package_name: null | string;
  package_description: null | string;
  package_is_system: boolean;
  is_auto_bound?: boolean;
  consent_mode?: string;
}

/**
 * Get agent's skill binding list (shared, auto routes by apiPrefix) / 获取智能体的技能绑定列表
 */
export async function getChatAgentSkillsApi(
  apiPrefix: string,
  agentId: number,
): Promise<ChatSkillBindingInfo[]> {
  return requestClient.get<ChatSkillBindingInfo[]>(
    `${apiPrefix}/ai/agents/${agentId}/skills`,
  );
}

/**
 * Send SSE streaming chat message / 发送 SSE 流式聊天消息
 */
export async function sendChatStreamApi(
  apiPrefix: string,
  agentId: number,
  body: AgentChatRequestBody,
  sseOptions: SSEOptions,
): Promise<void> {
  return requestClient.postSSE(
    `${chatBaseUrl(apiPrefix)}/${agentId}/chat/stream`,
    body,
    sseOptions,
  );
}
