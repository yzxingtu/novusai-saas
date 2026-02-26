/**
 * AI Chat Panel - Shared Types
 */

export interface ModelCapabilities {
  supports_vision: boolean;
  max_image_count: number | null;
  max_image_size_mb: number | null;
}

export interface AgentItem {
  id: number;
  tenant_id: number;
  name: string;
  description: string | null;
  avatar: string | null;
  status: string;
  model_name?: string | null;
  model_capabilities?: ModelCapabilities | null;
  welcome_message?: string | null;
  suggested_questions?: string[] | null;
}

export interface ConversationItem {
  id: number;
  title: string | null;
  status: string;
  created_at: string;
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
  ragSources?: RagSource[];
  attachments?: ChatAttachment[];
  toolCalls?: ToolCallEvent[];
  /** Pending CRUD confirmation request from tool */
  pendingConfirmation?: PendingConfirmation;
  /** Pending tool consent request (consent_mode=ask) */
  pendingConsent?: PendingConsent;
  /** Tool optimizer result (shown when tools were pre-filtered) */
  optimizingTools?: { total: number; selected: number };
  /** Interactive action buttons for user to click */
  actionButtons?: ActionButton[];
  /** Whether action buttons have been used (disabled after click) */
  actionButtonsUsed?: boolean;
  /** Generated images from image generation models */
  imageResults?: ImageResult[];
}

export interface AIChatPanelProps {
  /** 'page' = full page with sidebar, 'drawer' = compact drawer mode */
  mode: 'drawer' | 'page';
  /** API prefix: '/admin' or '/tenant' */
  apiPrefix: string;
  /** File upload URL */
  uploadUrl: string;
  /** Whether to show KB mention selector */
  showKbSelector?: boolean;
  /** Whether to show file attachments */
  showAttachments?: boolean;
  /** Function to fetch selectable KBs */
  fetchKbApi?: () => Promise<unknown[]>;
  /** i18n namespace prefix for labels */
  i18nPrefix?: string;
  /** Initial agent ID to auto-select on load */
  initialAgentId?: number;
  /** Initial conversation ID to auto-load after agent is selected */
  initialConversationId?: number;
  /** Custom welcome message (overrides default) */
  welcomeMessage?: string;
  /** Suggested question buttons shown in empty state */
  suggestedQuestions?: string[];
  /** Callback when a tool call completes successfully */
  onToolCall?: (toolName: string, output: string) => void;
  /** Callback when streaming completes (used for unread badge) */
  onStreamComplete?: () => void;
}
