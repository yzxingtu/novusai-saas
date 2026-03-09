/**
 * AI Chat Panel - Shared Types
 */

export interface ModelCapabilities {
  supports_vision: boolean;
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

export interface ConversationItem {
  id: number;
  agent_id: number;
  title: null | string;
  status: string;
  created_at: string;
  /** Agent name (enriched by global conversations API) */
  agent_name?: null | string;
  /** Agent avatar URL (enriched by global conversations API) */
  agent_avatar?: null | string;
}

export interface RagSource {
  doc_name: string;
  doc_id: number;
  score: number;
  snippet: string;
  page?: number;
  heading?: string;
}

export interface ChatAttachment {
  type: 'file' | 'image';
  url: string;
  name?: string;
  mime_type?: string;
  preview?: string;
}

export interface ToolCallEvent {
  name: string;
  /** 'running' = tool_start received, 'success'/'error' = tool_call received */
  status: 'error' | 'running' | 'success';
  arguments?: Record<string, unknown>;
  output?: string;
  error?: string;
  durationMs?: number;
  skillName?: string;
  skillType?: string;
  /** Human-friendly display name for the tool */
  displayName?: string;
  /** One-line summary of the tool execution result */
  summary?: string;
  /** Link to view the created/updated resource */
  resultLink?: string;
}

export interface PendingConfirmation {
  action: string;
  table: string;
  preview?: Record<string, unknown>;
  /** Whether the user has responded (confirmed or rejected) */
  resolved?: boolean;
}

export interface PendingConsent {
  toolName: string;
  arguments?: Record<string, unknown>;
  skillName?: string;
  skillType?: string;
  /** Whether the user has responded (allowed or rejected) */
  resolved?: boolean;
  /** Whether the consent was rejected (vs approved) */
  rejected?: boolean;
  /** Whether auto-approved by trust session */
  autoApproved?: boolean;
}

export interface ActionButton {
  /** Display label for the button */
  label: string;
  /** Value sent as user message when clicked */
  value: string;
  /** Button style: primary, default, or danger */
  style?: 'danger' | 'default' | 'primary';
}

export interface ImageResult {
  /** Image URL */
  url: string;
  /** Whether the URL is base64 encoded */
  isBase64?: boolean;
  /** Revised prompt from the model */
  revisedPrompt?: string;
}

export interface ChatMessage {
  role: 'assistant' | 'user';
  content: string;
  streaming?: boolean;
  tokenUsage?: number;
  durationMs?: number;
  /** Agent ID (for multi-agent conversation tracking) */
  agent_id?: null | number;
  /** Agent name (resolved from agents list) */
  agent_name?: null | string;
  /** Agent avatar URL (resolved from agents list) */
  agent_avatar?: null | string;
  /** Agent description (resolved from agents list) */
  agent_description?: null | string;
  /** LLM model name used by the agent */
  model_name?: null | string;
  ragSources?: RagSource[];
  attachments?: ChatAttachment[];
  toolCalls?: ToolCallEvent[];
  /** Pending CRUD confirmation request from tool */
  pendingConfirmation?: PendingConfirmation;
  /** Pending tool consent request (consent_mode=ask) */
  pendingConsent?: PendingConsent;
  /** Tool optimizer result (shown when tools were pre-filtered) */
  optimizingTools?: { selected: number; total: number };
  /** Interactive action buttons for user to click */
  actionButtons?: ActionButton[];
  /** Whether action buttons have been used (disabled after click) */
  actionButtonsUsed?: boolean;
  /** Generated images from image generation models */
  imageResults?: ImageResult[];
  /** Whether session memory was updated during this response */
  memoryUpdated?: boolean;
  /** Message creation timestamp (ISO string) */
  created_at?: string;
}

