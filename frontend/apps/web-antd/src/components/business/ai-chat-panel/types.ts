/**
 * AI Chat Panel - Shared Types
 */

export interface AgentItem {
  id: number;
  tenant_id: number;
  name: string;
  description: string | null;
  avatar: string | null;
  status: string;
  model_name?: string | null;
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
}

export interface PendingConfirmation {
  action: string;
  table: string;
  preview?: Record<string, unknown>;
  /** Whether the user has responded (confirmed or rejected) */
  resolved?: boolean;
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
  /** Extended thinking/reasoning content from the model */
  thinkingContent?: string;
  /** Pending CRUD confirmation request from tool */
  pendingConfirmation?: PendingConfirmation;
  /** Tool optimizer result (shown when tools were pre-filtered) */
  optimizingTools?: { total: number; selected: number };
}

export interface AIChatPanelProps {
  /** 'page' = full page with sidebar, 'drawer' = compact drawer mode */
  mode: 'drawer' | 'page';
  /** API prefix: '/admin' or '/tenant' */
  apiPrefix: string;
  /** File upload URL */
  uploadUrl: string;
  /** Whether to show KB mention selector */
  showKBSelector?: boolean;
  /** Whether to show file attachments */
  showAttachments?: boolean;
  /** Function to fetch selectable KBs */
  fetchKBApi?: (...args: unknown[]) => Promise<unknown[]>;
  /** i18n namespace prefix for labels */
  i18nPrefix?: string;
  /** Custom welcome message (overrides default) */
  welcomeMessage?: string;
  /** Suggested question buttons shown in empty state */
  suggestedQuestions?: string[];
}
