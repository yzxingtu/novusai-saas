import type { ItemType } from 'ant-design-vue/es/menu';
import type { ComputedRef, Ref } from 'vue';

import type { PendingOpDisplayItem } from './use-pending-page-ops';

import type {
  AgentItem,
  ChatAttachment,
  ChatKBBindingInfo,
  ChatMessage,
  ConversationItem,
  MemoryState,
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextDraftRuntimeState,
} from '#/types/ai-chat';

import type { usePageAICapability } from './use-page-ai-capability';
import type { useAIPanelStore } from '#/store';

export interface UseAIChatSlidePanelShellBindingsOptions {
  actionClick: (index: number, value: string) => void;
  activeConversationId: Ref<null | number>;
  agentKBBindings: Ref<ChatKBBindingInfo[]>;
  agents: Ref<AgentItem[]>;
  agentsLoading: Ref<boolean>;
  aiPanelStore: ReturnType<typeof useAIPanelStore>;
  apiPrefix: Ref<string>;
  askSuggested: (question: string) => void;
  canForceReroute: ComputedRef<boolean>;
  cancelEditTitle: () => void;
  chatAcceptAttribute: Ref<string>;
  chatMessages: Ref<ChatMessage[]>;
  cleanup: () => void;
  clearResolvedPageOps?: (() => void) | undefined;
  clearingMemory: Ref<boolean>;
  commitEditTitle: () => void;
  confirmAction: (index: number) => void;
  confirmConsent: (index: number) => void;
  conversationContextDiagnostics: Ref<null | Record<string, unknown>>;
  conversationSearch: Ref<string>;
  conversations: Ref<ConversationItem[]>;
  conversationsLoading: Ref<boolean>;
  copyMessage: (content: string) => Promise<void>;
  countdownNow: Ref<number>;
  editAndResend: (index: number) => void;
  editingConversationId: Ref<null | number>;
  editingTitle: Ref<string>;
  effectiveSuggestedQuestions: ComputedRef<string[]>;
  effectiveWelcomeMessage: ComputedRef<string>;
  ensureAgentVarsLoaded: (agentId: number) => void;
  exportMenuItems: ComputedRef<ItemType[]>;
  forceRerouteNextTurn: Ref<boolean>;
  getPendingOpsForMessage: (msg: ChatMessage) => PendingOpDisplayItem[];
  getRichTextDraftState: (
    message: ChatMessage,
  ) => null | RichTextDraftRuntimeState;
  groupedConversations: ComputedRef<
    Array<{ items: ConversationItem[]; label: string }>
  >;
  handleClose: () => void;
  handleDragOver: (event: DragEvent) => void;
  handleDrop: (event: DragEvent) => void;
  handleFileSelect: (event: Event) => void;
  handleInputKeyDown: (event: KeyboardEvent) => boolean;
  handleMessagesScroll: () => void;
  handleMinimize: () => void;
  handlePaste: (event: ClipboardEvent) => void;
  handleSendMessage: () => Promise<boolean>;
  handleToggleDock: () => void;
  handleToggleMode: () => void;
  hasHeaderVariableValues: ComputedRef<boolean>;
  headerConversationSummary: ComputedRef<string>;
  headerMoreHasAttention: ComputedRef<boolean>;
  headerMoreMenuItems: ComputedRef<ItemType[]>;
  inputMessage: Ref<string>;
  interactionMode: Ref<'confirm' | 'trusted_auto'>;
  interactionModeEffective: Ref<'confirm' | 'trusted_auto'>;
  isAgentSwitch: (index: number) => boolean;
  isPinned: ComputedRef<boolean>;
  lastRunSummary: Ref<null | Record<string, unknown>>;
  manualNewConversationAgentId: Ref<null | number>;
  memoryLoading: Ref<boolean>;
  memoryState: Ref<MemoryState | null>;
  mentionActiveIndex: Ref<number>;
  mentionCandidates: Ref<
    Array<{ binding: ChatKBBindingInfo; kind: 'knowledge_base' }>
  >;
  mentionOpen: Ref<boolean>;
  messagesContainer: Ref<HTMLElement | null>;
  onClearMemory: () => void;
  onDeleteConversation: (conversationId: number) => void;
  onDocumentClick: (event: MouseEvent) => void;
  onEditHeaderVars: () => void;
  onRichTextApply: (
    index: number,
    target: RichTextAIApplyTarget,
    mode: RichTextAIApplyMode,
  ) => void;
  onRichTextDiscard: (index: number) => void;
  onRichTextUndo: (index: number) => void;
  onSelectConversation: (conversationId: number) => void;
  onSelectMentionCandidate: (payload: {
    id: number;
    kind: 'knowledge_base';
  }) => void;
  onStartNewChat: () => void;
  onToggleForceReroute: () => void;
  pageAICapability: ReturnType<typeof usePageAICapability>;
  panelRef: Ref<HTMLElement | null>;
  panelTitle: ComputedRef<string>;
  pendingAttachments: Ref<ChatAttachment[]>;
  regenerateMessage: (index: number) => void;
  rejectAction: (index: number) => void;
  rejectConsent: (index: number) => void;
  removePendingAttachment: (index: number) => void;
  removeSelectedKnowledgeBase: (id: number) => void;
  resolvePendingOp: (invokeId: string, allowed: boolean) => void;
  retryLastMessage: (index: number) => void;
  routeNotice: ComputedRef<string>;
  routing: Ref<boolean>;
  scrollToBottom: (force?: boolean) => void;
  scrollToTop: () => void;
  selectedAgent: Ref<AgentItem | null>;
  selectedAgentId: Ref<null | number>;
  selectedKBIds: Ref<number[]>;
  selectMentionKnowledgeBase: (binding: ChatKBBindingInfo) => void;
  sending: Ref<boolean>;
  showAttachments: Ref<boolean>;
  showContextDrawer: Ref<boolean>;
  showHeaderMoreMenu: Ref<boolean>;
  showHeaderVarsButton: ComputedRef<boolean>;
  showHistory: Ref<boolean>;
  showMemoryPanel: Ref<boolean>;
  showScrollToBottom: Ref<boolean>;
  showScrollToTop: Ref<boolean>;
  showTimelineDrawer: Ref<boolean>;
  startEditTitle: (conversation: {
    id: number;
    title?: null | string;
    agent_name?: null | string;
  }) => void;
  stopGeneration: () => void;
  streaming: Ref<boolean>;
  supportsVision: ComputedRef<boolean>;
  timelineItems: Ref<unknown[]>;
  timelineLoading: Ref<boolean>;
  timelineRefreshing: Ref<boolean>;
  totalTokensUsed: ComputedRef<number>;
  unassociatedPendingOps: ComputedRef<PendingOpDisplayItem[]>;
  uploadUrl: Ref<string>;
  uploading: Ref<boolean>;
}
