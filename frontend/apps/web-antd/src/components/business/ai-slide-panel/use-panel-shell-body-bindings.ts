import type { ItemType } from 'ant-design-vue/es/menu';

import type { ComputedRef, Ref } from 'vue';

import type { ChatKBBindingInfo } from '#/api/shared/ai-chat';
import type {
  AgentKnowledgeBaseBindingsByAgentId,
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingsByAgentId,
  AgentSkillBindingSummary,
  AgentItem,
  ChatMessage,
} from '#/types/ai-chat';

import { computed } from 'vue';

type ComposerSendState = 'idle' | 'routing' | 'sending' | 'streaming';

interface HistoryConversationItem {
  agent_name?: null | string;
  id: number;
  title?: null | string;
}

interface HistoryConversationGroup {
  items: HistoryConversationItem[];
  label: string;
}

interface ComposerAttachmentItem {
  icon?: string;
  key: string;
  name: string;
  previewUrl?: string;
  type: 'audio' | 'file' | 'image' | 'video';
}

interface ComposerKnowledgeBaseChip {
  id: number;
  label: string;
}

interface ComposerSkillPackageChip {
  id: string;
  label: string;
  value: string;
}

interface ComposerMentionCandidateItem {
  active: boolean;
  id: number;
  kind: 'knowledge_base' | 'skill_package';
  subtitle?: string;
  title: string;
}

interface UsePanelShellBodyBindingsOptions {
  actionClick: (index: number, value: string) => void;
  activeConversationId: Ref<null | number>;
  agentKnowledgeBases?: ComputedRef<AgentKnowledgeBaseBindingSummary[] | null>;
  agentKnowledgeBaseMap?: ComputedRef<AgentKnowledgeBaseBindingsByAgentId>;
  agentSkillMap?: ComputedRef<AgentSkillBindingsByAgentId>;
  agentKBBindings: Ref<ChatKBBindingInfo[]>;
  agents: Ref<AgentItem[]>;
  apiPrefix: Ref<string>;
  askSuggested: (question: string) => void;
  attachmentAccept: ComputedRef<string>;
  attachmentLimitHint: ComputedRef<string>;
  attachments: ComputedRef<ComposerAttachmentItem[]>;
  attachDisabled: ComputedRef<boolean>;
  boundKnowledgeBases: ComputedRef<ComposerKnowledgeBaseChip[]>;
  cancelEditTitle: () => void;
  chatMessages: Ref<ChatMessage[]>;
  characterCount: ComputedRef<number>;
  commitEditTitle: () => void;
  compactMessages: ComputedRef<boolean>;
  composerMentionCandidates: ComputedRef<ComposerMentionCandidateItem[]>;
  confirmAction: (index: number) => void;
  confirmConsent: (index: number) => void;
  conversationSearch: Ref<string>;
  conversationsCount: ComputedRef<number>;
  conversationsLoading: Ref<boolean>;
  copyMessage: (content: string) => Promise<void>;
  editAndResend: (index: number) => void;
  editingConversationId: Ref<null | number>;
  editingTitle: Ref<string>;
  effectiveSuggestedQuestions: Ref<string[]>;
  effectiveWelcomeMessage: Ref<string>;
  exportMenuItems: ComputedRef<ItemType[]>;
  fileSelect: (event: Event) => void;
  groupedConversations: ComputedRef<HistoryConversationGroup[]>;
  handleDragOver: (event: DragEvent) => void;
  handleDrop: (event: DragEvent) => void;
  handleInputKeyDown: (event: KeyboardEvent) => boolean;
  handleMessagesScroll: () => void;
  handleOpenUrl: (url: string) => void;
  handleSendMessage: () => Promise<boolean>;
  ensureAgentKnowledgeBases: (agentId: number) => Promise<ChatKBBindingInfo[]>;
  ensureAgentSkills: (agentId: number) => Promise<AgentSkillBindingSummary[]>;
  inputMessage: Ref<string>;
  mentionEmptyHint: ComputedRef<string>;
  mentionLoading: Ref<boolean>;
  mentionMixedHint: string;
  mentionOpen: Ref<boolean>;
  newChat: () => void;
  onDeleteConversation: (conversationId: number) => void;
  onSelectConversation: (conversationId: number) => void;
  onSelectMentionCandidate: (payload: {
    id: number;
    kind: 'knowledge_base' | 'skill_package';
  }) => void;
  paste: (event: ClipboardEvent) => void;
  regenerateMessage: (index: number) => void;
  registerMessagesContainer: (element: HTMLDivElement | null) => void;
  rejectAction: (index: number) => void;
  rejectConsent: (index: number) => void;
  removeAttachment: (index: number) => void;
  removeSelectedKnowledgeBase: (id: number) => void;
  removeSelectedSkillName: (skillName: string) => void;
  retryLastMessage: (index: number) => void;
  routing: Ref<boolean>;
  scrollToBottom: (force?: boolean) => void;
  scrollToTop: () => void;
  selectedAgent: Ref<AgentItem | null>;
  selectedKnowledgeBases: ComputedRef<ComposerKnowledgeBaseChip[]>;
  selectedSkillPackages: ComputedRef<ComposerSkillPackageChip[]>;
  sendDisabled: ComputedRef<boolean>;
  sending: Ref<boolean>;
  sendState: ComputedRef<ComposerSendState>;
  shiftEnterHint: string;
  showAttachments: Ref<boolean>;
  showHistory: Ref<boolean>;
  showScrollToBottom: Ref<boolean>;
  showScrollToTop: Ref<boolean>;
  startEditTitle: (conversation: HistoryConversationItem) => void;
  stopGeneration: () => void;
  streaming: Ref<boolean>;
  totalTokensUsed: Ref<number>;
}

export function usePanelShellBodyBindings(
  options: UsePanelShellBodyBindingsOptions,
) {
  const panelBodyProps = computed(() => ({
    activeConversationId: options.activeConversationId.value,
    agentKnowledgeBases:
      options.agentKnowledgeBases?.value ?? options.agentKBBindings.value,
    agentKnowledgeBaseMap: options.agentKnowledgeBaseMap?.value ?? {},
    agentSkillMap: options.agentSkillMap?.value ?? {},
    agents: options.agents.value,
    apiPrefix: options.apiPrefix.value,
    attachDisabled: options.attachDisabled.value,
    attachmentAccept: options.attachmentAccept.value,
    attachmentLimitHint: options.attachmentLimitHint.value,
    attachments: options.attachments.value,
    boundKnowledgeBases: options.boundKnowledgeBases.value,
    characterCount: options.characterCount.value,
    chatMessages: options.chatMessages.value,
    compactMessages: options.compactMessages.value,
    conversationSearch: options.conversationSearch.value,
    conversationsCount: options.conversationsCount.value,
    conversationsLoading: options.conversationsLoading.value,
    editingConversationId: options.editingConversationId.value,
    editingTitle: options.editingTitle.value,
    effectiveSuggestedQuestions: options.effectiveSuggestedQuestions.value,
    effectiveWelcomeMessage: options.effectiveWelcomeMessage.value,
    exportMenuItems: options.exportMenuItems.value,
    groupedConversations: options.groupedConversations.value,
    inputMessage: options.inputMessage.value,
    ensureAgentKnowledgeBases: options.ensureAgentKnowledgeBases,
    ensureAgentSkills: options.ensureAgentSkills,
    mentionCandidates: options.composerMentionCandidates.value,
    mentionEmptyHint: options.mentionEmptyHint.value,
    mentionLoading: options.mentionLoading.value,
    mentionMixedHint: options.mentionMixedHint,
    mentionOpen: options.mentionOpen.value,
    registerContainer: options.registerMessagesContainer,
    routing: options.routing.value,
    selectedAgent: options.selectedAgent.value,
    selectedKnowledgeBases: options.selectedKnowledgeBases.value,
    selectedSkillPackages: options.selectedSkillPackages.value,
    sendDisabled: options.sendDisabled.value,
    sending: options.sending.value,
    sendState: options.sendState.value,
    shiftEnterHint: options.shiftEnterHint,
    showAttachments: options.showAttachments.value,
    showHistory: options.showHistory.value,
    showScrollToBottom: options.showScrollToBottom.value,
    showScrollToTop: options.showScrollToTop.value,
    streaming: options.streaming.value,
    totalTokensUsed: options.totalTokensUsed.value,
  }));

  async function onCopyMessage(content: string) {
    await options.copyMessage(content);
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (options.handleInputKeyDown(event)) {
      return;
    }
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      void options.handleSendMessage();
    }
  }

  const panelBodyListeners = {
    actionClick: options.actionClick,
    askSuggested: options.askSuggested,
    cancelEditTitle: options.cancelEditTitle,
    commitEditTitle: options.commitEditTitle,
    confirm: options.confirmAction,
    consentConfirm: options.confirmConsent,
    consentReject: options.rejectConsent,
    copy: onCopyMessage,
    deleteConversation: options.onDeleteConversation,
    dragover: options.handleDragOver,
    drop: options.handleDrop,
    edit: options.editAndResend,
    fileSelect: options.fileSelect,
    keydown: handleKeyDown,
    newChat: options.newChat,
    openUrl: options.handleOpenUrl,
    paste: options.paste,
    regenerate: options.regenerateMessage,
    reject: options.rejectAction,
    removeAttachment: options.removeAttachment,
    removeSelectedKnowledgeBase: options.removeSelectedKnowledgeBase,
    removeSelectedSkillPackage: options.removeSelectedSkillName,
    retry: options.retryLastMessage,
    scroll: options.handleMessagesScroll,
    scrollToBottom: () => options.scrollToBottom(true),
    scrollToTop: options.scrollToTop,
    selectConversation: options.onSelectConversation,
    selectMentionCandidate: options.onSelectMentionCandidate,
    send: options.handleSendMessage,
    startEditTitle: options.startEditTitle,
    stop: options.stopGeneration,
    'update:conversationSearch': (value: string) => {
      options.conversationSearch.value = value;
    },
    'update:editingTitle': (value: string) => {
      options.editingTitle.value = value;
    },
    'update:inputMessage': (value: string) => {
      options.inputMessage.value = value;
    },
  };

  return {
    panelBodyListeners,
    panelBodyProps,
  };
}
