import type { ItemType } from 'ant-design-vue/es/menu';

import type { ComputedRef, Ref } from 'vue';

import type {
  ChatKBBindingInfo,
  ConversationTimelineItem,
  MemoryState,
} from '#/api/shared/ai-chat';
import type { useAIPanelStore } from '#/store';
import type {
  AgentKnowledgeBaseBindingsByAgentId,
  AgentSkillBindingsByAgentId,
  AgentSkillBindingSummary,
  AgentItem,
  ChatAttachment,
  ChatMessage,
  ConversationItem,
  MentionCandidate,
  MentionKnowledgeBaseBinding,
} from '#/types/ai-chat';

export interface UseAIChatSlidePanelShellBindingsOptions {
  actionClick: (index: number, value: string) => void;
  activeConversationId: Ref<null | number>;
  agentKBBindings: Ref<ChatKBBindingInfo[]>;
  agentKBBindingsByAgentId?: Ref<AgentKnowledgeBaseBindingsByAgentId>;
  agentSkillBindingsByAgentId?: Ref<AgentSkillBindingsByAgentId>;
  agents: Ref<AgentItem[]>;
  agentsLoading: Ref<boolean>;
  aiPanelStore: ReturnType<typeof useAIPanelStore>;
  apiPrefix: Ref<string>;
  askSuggested: (question: string) => void;
  canForceReroute: ComputedRef<boolean>;
  cancelEditTitle: () => void;
  chatAcceptAttribute: string;
  chatMessages: Ref<ChatMessage[]>;
  cleanup: () => void;
  clearingMemory: Ref<boolean>;
  commitEditTitle: () => void;
  confirmAction: (index: number) => void;
  confirmConsent: (index: number) => void;
  conversationContextDiagnostics: Ref<null | Record<string, unknown>>;
  conversationSearch: Ref<string>;
  conversations: Ref<ConversationItem[]>;
  conversationsLoading: Ref<boolean>;
  copyMessage: (content: string) => Promise<void>;
  editAndResend: (index: number) => void;
  editingConversationId: Ref<null | number>;
  editingTitle: Ref<string>;
  effectiveSuggestedQuestions: ComputedRef<string[]>;
  effectiveWelcomeMessage: ComputedRef<string>;
  ensureAgentVarsLoaded: (agentId: number) => void;
  exportMenuItems: ComputedRef<ItemType[]>;
  forceRerouteNextTurn: Ref<boolean>;
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
  headerMemoryHasAttention: ComputedRef<boolean>;
  headerMoreHasAttention: ComputedRef<boolean>;
  headerMoreMenuItems: ComputedRef<ItemType[]>;
  inputMessage: Ref<string>;
  interactionMode: Ref<'confirm' | 'trusted_auto'>;
  interactionModeEffective: Ref<'confirm' | 'trusted_auto'>;
  isPinned: ComputedRef<boolean>;
  lastRunSummary: Ref<null | Record<string, unknown>>;
  manualNewConversationAgentId: Ref<null | number>;
  memoryLoading: Ref<boolean>;
  memoryState: Ref<MemoryState | null>;
  mentionActiveIndex: Ref<number>;
  mentionCandidates: Readonly<Ref<MentionCandidate[]>>;
  mentionOpen: Ref<boolean>;
  messagesContainer: Ref<HTMLElement | null>;
  loadAgentKBBindings: (agentId: number) => Promise<ChatKBBindingInfo[]>;
  loadAgentSkillBindings: (
    agentId: number,
  ) => Promise<AgentSkillBindingSummary[]>;
  onClearMemory: () => void;
  onDeleteConversation: (conversationId: number) => void;
  onDocumentClick: (event: MouseEvent) => void;
  onEditHeaderVars: () => void;
  onToggleMemory: () => void | Promise<void>;
  onSelectConversation: (conversationId: number) => void;
  onStartNewChat: () => void;
  onToggleForceReroute: () => void;
  panelRef: Ref<HTMLElement | null>;
  panelTitle: ComputedRef<string>;
  pendingAttachments: Ref<ChatAttachment[]>;
  refreshTimeline: () => void;
  regenerateMessage: (index: number) => void;
  rejectAction: (index: number) => void;
  rejectConsent: (index: number) => void;
  removePendingAttachment: (index: number) => void;
  removeSelectedKnowledgeBase: (id: number) => void;
  retryLastMessage: (index: number) => void;
  routeNotice: Ref<null | string>;
  routing: Ref<boolean>;
  scrollToBottom: (force?: boolean) => void;
  scrollToTop: () => void;
  selectedAgent: Ref<AgentItem | null>;
  selectedAgentId: Ref<null | number>;
  selectedKBIds: Ref<number[]>;
  selectMentionKnowledgeBase: (
    binding: Pick<MentionKnowledgeBaseBinding, 'knowledge_base_id'>,
  ) => void;
  sending: Ref<boolean>;
  showAttachments: Readonly<Ref<boolean>>;
  showContextDrawer: Ref<boolean>;
  showHeaderMemoryButton: ComputedRef<boolean>;
  showHeaderMoreMenu: Ref<boolean>;
  showHeaderVarsButton: ComputedRef<boolean>;
  showHistory: Ref<boolean>;
  showMemoryPanel: Ref<boolean>;
  showScrollToBottom: Ref<boolean>;
  showScrollToTop: Ref<boolean>;
  showTimelineDrawer: Ref<boolean>;
  startEditTitle: (conversation: {
    agent_name?: null | string;
    id: number;
    title?: null | string;
  }) => void;
  stopGeneration: () => void;
  streaming: Ref<boolean>;
  supportsVision: ComputedRef<boolean>;
  timelineItems: Ref<ConversationTimelineItem[]>;
  timelineLoading: Ref<boolean>;
  timelineRefreshing: Ref<boolean>;
  totalTokensUsed: ComputedRef<number>;
  uploadUrl: Ref<string>;
  uploading: Ref<boolean>;
}
