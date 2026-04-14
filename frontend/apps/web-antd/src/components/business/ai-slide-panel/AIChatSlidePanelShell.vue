<script lang="ts" setup>
import type { AIPageMode } from '@vben/types';

import {
  computed,
  onMounted,
  onUnmounted,
  ref,
  toRef,
  watch,
  watchEffect,
} from 'vue';

import { message } from 'ant-design-vue';

import { useAIChat } from '#/components/business/ai-chat-panel/use-ai-chat';
import { useModalDetector } from '#/composables/use-modal-detector';
import {
  DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS,
  usePageScreenshot,
} from '#/composables/use-page-screenshot';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';
import { usePublicConfigStore } from '#/store/shared/public-config';
import { getAgentInputVariables } from '#/types/ai-chat';
import { normalizePageAIMode } from '#/utils/ai-page-capabilities';
import { getErrorMessage } from '#/utils/error-helpers';

import AgentVarsModal from './AgentVarsModal.vue';
import AIChatMemoryPanel from './AIChatMemoryPanel.vue';
import AIChatPanelBody from './AIChatPanelBody.vue';
import AIChatPanelHeader from './AIChatPanelHeader.vue';
import AIChatPanelOverlays from './AIChatPanelOverlays.vue';
import AIChatPanelToolbarRow from './AIChatPanelToolbarRow.vue';
import { useAgentRouter } from './use-agent-router';
import { usePageAICapability } from './use-page-ai-capability';
import { usePanelComposer } from './use-panel-composer';
import { usePanelHistory } from './use-panel-history';
import { usePanelLinkPreview } from './use-panel-link-preview';
import { usePanelShellActions } from './use-panel-shell-actions';
import { usePanelShellContext } from './use-panel-shell-context';
import { usePanelShellHeaderBindings } from './use-panel-shell-header-bindings';
import { usePanelShellOverlayBindings } from './use-panel-shell-overlay-bindings';
import { usePanelWidth } from './use-panel-width';
import { usePendingPageOps } from './use-pending-page-ops';

defineOptions({ name: 'AIChatSlidePanelShell' });

const props = withDefaults(
  defineProps<{
    /** Effective AI mode for current page / 当前页面生效的 AI 模式 */
    aiMode?: AIPageMode;
    /** API prefix / API 前缀 */
    apiPrefix: string;
    /** Disabled capability keys for current page / 当前页面禁用的能力键 */
    disabledCapabilities?: string[];
    /** Disabled operation names for current page / 当前页面禁用的操作名 */
    disabledOperations?: string[];
    /** Page-level pageContextKey (from route.meta.ai) / 页面级 pageContextKey（来自 route.meta.ai） */
    pageContextKey?: string;
    /** External pending conversation ID to restore (from CommandBar) / 外部传入的待恢复对话 ID（来自 CommandBar） */
    pendingConversationId?: null | number;
    /** External pending message (from CommandBar) / 外部传入的消息（来自 CommandBar） */
    pendingMessage?: null | string;
    /** Whether to show attachment button / 是否显示附件按钮 */
    showAttachments?: boolean;
    /** Upload URL / 上传地址 */
    uploadUrl: string;
  }>(),
  {
    aiMode: 'operate',
    disabledCapabilities: undefined,
    disabledOperations: undefined,
    showAttachments: true,
    pendingMessage: null,
    pendingConversationId: null,
    pageContextKey: undefined,
  },
);

const emit = defineEmits<{
  /** Conversation restored / 对话已恢复 */
  conversationRestored: [];
  /** Message consumed / 消息已消费 */
  messageSent: [];
}>();

const aiPanelStore = useAIPanelStore();
const publicConfigStore = usePublicConfigStore();
const { modalState } = useModalDetector();
const normalizedPageMode = computed(() => normalizePageAIMode(props.aiMode));
const pageAIPolicy = computed(() => ({
  mode: normalizedPageMode.value,
  disabledCapabilities: props.disabledCapabilities,
  disabledOperations: props.disabledOperations,
}));

const panelTitle = computed(() => {
  const siteName =
    publicConfigStore.platformConfig?.brand?.siteName ||
    publicConfigStore.tenantConfig?.brand?.siteName ||
    import.meta.env.VITE_APP_TITLE ||
    'NovusAI';
  return `${siteName} AI`;
});

const isPinned = computed(
  () => !!aiPanelStore.pinnedAgentId && !!aiPanelStore.pinnedAgentName,
);

const chat = useAIChat({
  apiPrefix: toRef(props, 'apiPrefix'),
  uploadUrl: toRef(props, 'uploadUrl'),
  onToolCall: (name: string, output: string) => {
    aiPanelStore.dispatchToolCall(name, output);
  },
  onStreamComplete: () => {
    aiPanelStore.markUnread();
  },
  pageContextResolver: () => currentPageContext.value,
  pageSessionIdGetter: getActivePageSessionId,
  onVariablesMissing: () => {
    const agent = selectedAgent.value;
    if (!agent) return;
    const inputVariables = getAgentInputVariables(agent);
    if (inputVariables.length > 0) {
      openVarsModal(inputVariables, agent.id, agent.name);
    }
  },
});

const {
  agents,
  agentsLoading,
  selectedAgentId,
  selectedAgent,
  loadAgents,
  conversations,
  conversationsLoading,
  activeConversationId,
  conversationContextDiagnostics,
  loadConversations,
  startNewConversation,
  deleteConversation,
  updateConversationTitle,
  loadConversationMessages,
  chatMessages,
  inputMessage,
  mentionOpen,
  mentionCandidates,
  mentionActiveIndex,
  sending,
  streaming,
  messagesContainer,
  sendMessage,
  stopGeneration,
  handleMessagesScroll,
  showScrollToBottom,
  showScrollToTop,
  scrollToBottom,
  scrollToTop,
  copyMessage,
  handleInputKeyDown,
  selectMentionKnowledgeBase,
  removeSelectedKnowledgeBase,
  selectedKBIds,
  cleanup,
  pendingAttachments,
  uploading,
  chatAcceptAttribute,
  handleFileSelect,
  handlePaste,
  handleDrop,
  handleDragOver,
  removePendingAttachment,
  confirmAction,
  rejectAction,
  confirmConsent,
  rejectConsent,
  interactionMode,
  interactionModeEffective,
  clickActionButton,
  regenerateMessage,
  editAndResend,
  retryLastMessage,
  clearConversationMemory,
  clearingMemory,
  fetchConversationMemory,
  memoryState,
  memoryLoading,
  lastMemoryUpdated,
  exportAsMarkdown,
  exportAsPlainText,
  lastRunSummary,
  totalTokensUsed,
  supportsVision,
  agentKBBindings,
  allAgentsVariables,
  ensureAgentVarsLoaded,
  agentsWithVarsInConversation,
  applyVariables,
} = chat;

const { countdownNow, getPendingOpsForMessage, unassociatedPendingOps } =
  usePendingPageOps({
    chatMessages,
    pendingPageOps: toRef(aiPanelStore, 'pendingPageOps'),
  });

// Template ref bindings / 模板 ref 绑定
void messagesContainer;
void handleMessagesScroll;
void showScrollToBottom;
void scrollToBottom;

const exportMenuItems = computed(() => [
  {
    key: 'md',
    label: $t('common.globalAiChat.exportFormatMarkdown'),
    onClick: () => exportAsMarkdown(),
  },
  {
    key: 'txt',
    label: $t('common.globalAiChat.exportFormatPlainText'),
    onClick: () => exportAsPlainText(),
  },
]);

const unpinAgentRef = ref<() => void>(() => {});

const { routing, routeMessage } = useAgentRouter({
  apiPrefix: toRef(props, 'apiPrefix'),
  agents,
  pinnedAgentId: toRef(aiPanelStore, 'pinnedAgentId'),
  pinnedAgentName: toRef(aiPanelStore, 'pinnedAgentName'),
  activeConversationId,
});

const panelShellContext = usePanelShellContext({
  activeConversationId,
  agents,
  applyVariables,
  agentsWithVarsInConversation,
  allAgentsVariables,
  apiPrefix: toRef(props, 'apiPrefix'),
  chatMessages,
  clearConversationMemory,
  clearResolvedPageOps: () => aiPanelStore.clearResolvedPageOps?.(),
  consumePendingAgentId: () => aiPanelStore.consumePendingAgentId() ?? null,
  conversations,
  ensureAgentVarsLoaded,
  exportMenuItems,
  fetchConversationMemory,
  handleSendMessage,
  inputMessage,
  isPinned,
  lastMemoryUpdated,
  loadAgents,
  loadConversationMessages,
  loadConversations,
  onConversationRestored: () => emit('conversationRestored'),
  onMessageSent: () => emit('messageSent'),
  panelStore: aiPanelStore,
  pendingConversationId: toRef(props, 'pendingConversationId'),
  pendingMessage: toRef(props, 'pendingMessage'),
  routing,
  selectedAgent,
  selectedAgentId,
  sending,
  sendMessage,
  startNewConversation,
  storePendingAgentId: toRef(aiPanelStore, 'pendingAgentId'),
  storePendingConversationId: toRef(aiPanelStore, 'pendingConversationId'),
  storePendingMessage: toRef(aiPanelStore, 'pendingMessage'),
  streaming,
  totalTokensUsed,
  unpinAgent: () => unpinAgentRef.value(),
  visible: toRef(aiPanelStore, 'visible'),
});

const {
  agentVarsModalListeners,
  agentVarsModalProps,
  canForceReroute,
  clearRoutingIntent,
  deferSendForMissingVariables,
  forceRerouteNextTurn,
  getRichTextDraftState,
  headerConversationSummary,
  headerMoreHasAttention,
  headerMoreMenuItems,
  hasHeaderVariableValues,
  manualNewConversationAgentId,
  onClearMemory,
  onEditHeaderVars,
  onRichTextApply,
  onRichTextDiscard,
  onRichTextUndo,
  onToggleForceReroute,
  openVarsModal,
  refreshTimeline,
  routeNotice,
  showContextDrawer,
  showHeaderMoreMenu,
  showHeaderVarsButton,
  showHistory,
  showMemoryPanel,
  showRouteNotice,
  showTimelineDrawer,
  timelineItems,
  timelineLoading,
  timelineRefreshing,
} = panelShellContext;

function isAgentSwitch(idx: number): boolean {
  const msg = chatMessages.value[idx];
  if (!msg || msg.role !== 'assistant' || !msg.agent_id) return false;
  // Find previous assistant message / 查找上一条助手消息
  for (let i = idx - 1; i >= 0; i--) {
    const prev = chatMessages.value[i];
    if (prev?.role === 'assistant') {
      return prev.agent_id !== msg.agent_id;
    }
  }
  return false;
}

const pageContextLimitBytes = computed(
  () =>
    publicConfigStore.platformConfig?.runtimeLimits?.pageContextMaxBytes ||
    publicConfigStore.tenantConfig?.runtimeLimits?.pageContextMaxBytes,
);

const pageAICapability = usePageAICapability({
  disabledCapabilities: toRef(props, 'disabledCapabilities'),
  modalState,
  normalizedPageMode,
  pageAIPolicy,
  pageContextKey: toRef(props, 'pageContextKey'),
  pageContextLimitBytes,
});
const currentPageContext = pageAICapability.currentPageContext;

const interactionModeLabel = computed(() => {
  return interactionModeEffective.value === 'trusted_auto'
    ? $t('common.globalAiChat.modeTrustedAuto')
    : $t('common.globalAiChat.modeConfirm');
});

const interactionModeRequested = computed(() => {
  return interactionMode.value === 'trusted_auto'
    ? $t('common.globalAiChat.modeTrustedAuto')
    : $t('common.globalAiChat.modeConfirm');
});

const interactionModeDowngraded = computed(() => {
  return (
    interactionMode.value === 'trusted_auto' &&
    interactionModeEffective.value === 'confirm'
  );
});

const interactionModeDowngradeText = computed(() => {
  const reason = String(lastRunSummary.value?.downgrade_reason || '');
  if (reason === 'missing_runtime_trust_policy') {
    return $t('common.globalAiChat.trustedAutoDowngradeMissingPolicy');
  }
  return reason || '';
});

async function handleSendMessage() {
  const text = inputMessage.value.trim();
  if (!text && pendingAttachments.value.length === 0) return false;

  const hasImageAttachments = pendingAttachments.value.some(
    (a) => a.type === 'image',
  );
  const hasAudioAttachments = pendingAttachments.value.some(
    (a) => a.type === 'audio',
  );
  const hasVideoAttachments = pendingAttachments.value.some(
    (a) => a.type === 'video',
  );
  const hasFileAttachments = pendingAttachments.value.some(
    (a) => a.type === 'file',
  );
  const hasCapabilitySensitiveAttachments =
    hasImageAttachments || hasAudioAttachments || hasVideoAttachments;
  const hasAnyAttachments = pendingAttachments.value.length > 0;

  const pageContext = currentPageContext.value;

  // P0: Agent is pinned → skip routing, send directly / 已固定智能体 → 跳过路由，直接发送
  if (isPinned.value && aiPanelStore.pinnedAgentId) {
    const pinnedId = aiPanelStore.pinnedAgentId;
    if (pinnedId !== selectedAgentId.value) {
      selectedAgentId.value = pinnedId;
    }
    const pinnedAgent = agents.value.find((a) => a.id === pinnedId);
    const pinnedInputVariables = getAgentInputVariables(pinnedAgent);
    const pinnedRequired = pinnedInputVariables.filter((v) => v.required);
    if (pinnedRequired.length > 0) {
      ensureAgentVarsLoaded(pinnedId);
      const pinnedVars = allAgentsVariables.value[pinnedId] ?? {};
      const pinnedMissing = pinnedRequired.filter(
        (v) => !pinnedVars[v.name]?.trim(),
      );
      if (pinnedMissing.length > 0) {
        deferSendForMissingVariables({
          agentId: pinnedId,
          agentName: pinnedAgent!.name,
          pageContext,
          requiredVars: pinnedInputVariables,
        });
        return false;
      }
    }
    return await sendMessage({ agentId: pinnedId, pageContext });
  }

  const forceReroute = forceRerouteNextTurn.value;
  if (forceReroute) {
    forceRerouteNextTurn.value = false;
  }

  if (
    !activeConversationId.value &&
    manualNewConversationAgentId.value &&
    selectedAgentId.value === manualNewConversationAgentId.value
  ) {
    const explicitAgentId = manualNewConversationAgentId.value;
    manualNewConversationAgentId.value = null;
    return await sendMessage({ agentId: explicitAgentId, pageContext });
  }

  if (activeConversationId.value && selectedAgentId.value && !forceReroute) {
    return await sendMessage({ pageContext });
  }

  try {
    // /route 要求 message 非空；仅发图时用占位符 / Route API requires non-empty message
    const routeMessageText = text || (hasAnyAttachments ? ' ' : '');
    const result = await routeMessage(
      routeMessageText,
      props.pageContextKey,
      pageContext,
      {
        hasAudioAttachments,
        hasFileAttachments,
        hasImageAttachments,
        hasVideoAttachments,
      },
      forceReroute,
    );

    manualNewConversationAgentId.value = null;

    // Update current agent context after explicit routing / 路由后更新当前智能体上下文
    if (result.agentId !== selectedAgentId.value) {
      selectedAgentId.value = result.agentId;
    }
    const routedPageContext = currentPageContext.value;

    // Show route notice (pinned and default don't show) / 显示路由提示（pinned 和 default 不显示）
    if (result.routedBy === 'router') {
      showRouteNotice(
        $t('common.aiPanel.routedTo', { agent: result.agentName }),
      );
    }

    // Check if routed agent has required vars not yet filled / 检查路由到的 agent 是否有必填变量未填
    const routedAgent = agents.value.find((a) => a.id === result.agentId);
    const routedInputVariables = getAgentInputVariables(routedAgent);
    const requiredVars = routedInputVariables.filter((v) => v.required);
    if (requiredVars.length > 0) {
      ensureAgentVarsLoaded(result.agentId);
      const agentVars = allAgentsVariables.value[result.agentId] ?? {};
      const missing = requiredVars.filter((v) => !agentVars[v.name]?.trim());
      if (missing.length > 0) {
        // Defer send: open modal and wait for vars to be filled / 延迟发送：打开弹窗等待变量填写
        deferSendForMissingVariables({
          agentId: result.agentId,
          agentName: routedAgent!.name,
          pageContext: routedPageContext,
          requiredVars: routedInputVariables,
        });
        return false;
      }
    }

    // Send message (using routed agent ID) / 发送消息（使用路由后的智能体 ID）
    return await sendMessage({
      agentId: result.agentId,
      pageContext: routedPageContext,
    });
  } catch (error: unknown) {
    if (selectedAgentId.value && !hasCapabilitySensitiveAttachments) {
      message.warning($t('common.globalAiChat.routeFailedFallback'));
      return await sendMessage({ pageContext });
    }

    const baseMsg = getErrorMessage(error, 'common.http.internalServerError');
    message.error(`${baseMsg} ${$t('common.globalAiChat.routeFailedHint')}`);
    return false;
  }
}

function handleKeyDown(e: KeyboardEvent) {
  if (handleInputKeyDown(e)) {
    return;
  }
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    handleSendMessage();
  }
}

const {
  cancelEditTitle,
  commitEditTitle,
  conversationSearch,
  editingConversationId,
  editingTitle,
  groupedConversations,
  onDeleteConversation,
  onSelectConversation,
  onStartNewChat,
  startEditTitle,
  toggleHistory,
} = usePanelHistory({
  clearResolvedPageOps: aiPanelStore.clearResolvedPageOps,
  clearRoutingIntent,
  conversations,
  deleteConversation,
  loadConversationMessages,
  showHistory,
  showMemoryPanel,
  startNewConversation,
  updateConversationTitle,
});
const {
  askSuggested,
  effectiveSuggestedQuestions,
  effectiveWelcomeMessage,
  handleClose,
  handleMinimize,
  handleToggleDock,
  handleToggleMode,
  onDocumentClick,
  panelRef,
  unpinAgent,
} = usePanelShellActions({
  aiPanelStore,
  handleSendMessage,
  inputMessage,
  selectedAgent,
});
void panelRef;
unpinAgentRef.value = unpinAgent;

const headerBindings = usePanelShellHeaderBindings({
  activeConversationId,
  aiPanelStore,
  canForceReroute,
  forceRerouteNextTurn,
  headerConversationSummary,
  headerMoreHasAttention,
  headerMoreMenuItems,
  hasHeaderVariableValues,
  onEditHeaderVars,
  onToggleForceReroute,
  panelTitle,
  pageAICapability,
  routeNotice,
  routing,
  showHeaderMoreMenu,
  showHeaderVarsButton,
  showHistory,
  showContextDrawer,
  showTimelineDrawer,
  timelineItems,
  timelineLoading,
  timelineRefreshing,
  refreshTimeline,
  isPinned,
  toggleHistory,
  togglePageAIDetails: pageAICapability.togglePageAIDetails,
  expandAllPageAIOperations: pageAICapability.expandAllPageAIOperations,
  onStartNewChat,
  handleClose,
  handleMinimize,
  handleToggleDock,
  handleToggleMode,
});
const { headerListeners, headerProps, toolbarListeners, toolbarProps } =
  headerBindings;

const {
  composerAttachmentLimitHint,
  composerAttachments,
  composerBoundKnowledgeBases,
  composerMentionCandidates,
  composerSelectedKnowledgeBases,
  composerSendDisabled,
  composerSendState,
  onSelectMentionCandidate,
} = usePanelComposer({
  agents,
  agentKBBindings,
  inputMessage,
  mentionActiveIndex,
  mentionCandidates,
  pendingAttachments,
  routing,
  selectedKBIds,
  selectMentionKnowledgeBase,
  sending,
  showAttachments: toRef(props, 'showAttachments'),
  streaming,
  uploading,
});

const resolvedAttachmentAccept = computed(() =>
  typeof chatAcceptAttribute === 'string'
    ? chatAcceptAttribute
    : (chatAcceptAttribute as { value: string }).value,
);

const panelBodyProps = computed(() => ({
  activeConversationId: activeConversationId.value,
  agents: agents.value,
  apiPrefix: props.apiPrefix,
  attachDisabled: agents.value.length === 0 || sending.value,
  attachmentAccept: resolvedAttachmentAccept.value,
  attachmentLimitHint: composerAttachmentLimitHint.value,
  attachments: composerAttachments.value,
  boundKnowledgeBases: composerBoundKnowledgeBases.value,
  chatMessages: chatMessages.value,
  characterCount: inputMessage.value.length,
  conversationSearch: conversationSearch.value,
  conversationsCount: conversations.value.length,
  conversationsLoading: conversationsLoading.value,
  countdownNow: countdownNow.value,
  editingConversationId: editingConversationId.value,
  editingTitle: editingTitle.value,
  effectiveSuggestedQuestions: effectiveSuggestedQuestions.value,
  effectiveWelcomeMessage: effectiveWelcomeMessage.value,
  exportMenuItems: exportMenuItems.value,
  getPendingOpsForMessage,
  getRichTextDraftState,
  groupedConversations: groupedConversations.value,
  inputMessage: inputMessage.value,
  interactionMode: interactionMode.value,
  isAgentSwitch,
  mentionCandidates: composerMentionCandidates.value,
  mentionEmptyHint:
    mentionCandidates.value.length === 0 &&
    agentKBBindings.value.length === 0 &&
    !agentsLoading.value
      ? $t('common.globalAiChat.mentionKbNoneBound')
      : $t('common.globalAiChat.mentionAgentEmpty'),
  mentionLoading: agentsLoading.value,
  mentionMixedHint: $t('common.globalAiChat.mentionMixedHint'),
  mentionOpen: mentionOpen.value,
  registerContainer: registerMessagesContainer,
  routing: routing.value,
  screenshotDisabled:
    agents.value.length === 0 || sending.value || capturing.value,
  screenshotLoading: capturing.value,
  selectedAgent: selectedAgent.value,
  selectedKnowledgeBases: composerSelectedKnowledgeBases.value,
  sendDisabled: composerSendDisabled.value,
  sendState: composerSendState.value,
  sending: sending.value,
  shiftEnterHint: $t('common.globalAiChat.shiftEnterHint'),
  showAttachments: props.showAttachments,
  showHistory: showHistory.value,
  showInteractionMode: chatMessages.value.length > 0,
  showScrollToBottom: showScrollToBottom.value,
  showScrollToTop: showScrollToTop.value,
  showScreenshotButton: props.showAttachments && supportsVision.value,
  streaming: streaming.value,
  totalTokensUsed: totalTokensUsed.value,
  unassociatedPendingOps: unassociatedPendingOps.value,
}));

const { capturing, captureAndUpload } = usePageScreenshot();

async function handleScreenshot() {
  if (capturing.value || !supportsVision.value) return;
  const result = await captureAndUpload({
    uploadUrl: props.uploadUrl,
    extraData: props.apiPrefix.includes('/admin')
      ? { tenant_id: '0' }
      : undefined,
    excludeSelectors: [...DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS],
  });
  if (result) {
    pendingAttachments.value.push(result.attachment);
  }
}

const { handleOpenUrl, previewImageUrl, previewImageVisible } =
  usePanelLinkPreview();

const overlayBindings = usePanelShellOverlayBindings({
  aiPanelStore,
  conversationContextDiagnostics,
  interactionModeDowngraded,
  interactionModeDowngradeText,
  interactionModeLabel,
  interactionModeRequested,
  lastRunSummary,
  previewImageUrl,
  previewImageVisible,
  refreshTimeline: headerBindings.refreshTimeline,
  showContextDrawer: headerBindings.showContextDrawer,
  showTimelineDrawer: headerBindings.showTimelineDrawer,
  timelineItems: headerBindings.timelineItems,
  timelineLoading: headerBindings.timelineLoading,
  timelineRefreshing: headerBindings.timelineRefreshing,
});
const { overlayListeners, overlayProps } = overlayBindings;

async function onCopyMessage(content: string) {
  await copyMessage(content);
}

function registerMessagesContainer(element: HTMLDivElement | null) {
  messagesContainer.value = element;
}

const panelBodyListeners = {
  actionClick: clickActionButton,
  askSuggested,
  cancelEditTitle,
  captureScreenshot: handleScreenshot,
  commitEditTitle,
  confirm: confirmAction,
  consentConfirm: confirmConsent,
  consentReject: rejectConsent,
  copy: onCopyMessage,
  deleteConversation: onDeleteConversation,
  dragover: handleDragOver,
  drop: handleDrop,
  edit: editAndResend,
  fileSelect: handleFileSelect,
  keydown: handleKeyDown,
  newChat: onStartNewChat,
  openUrl: handleOpenUrl,
  paste: handlePaste,
  regenerate: regenerateMessage,
  reject: rejectAction,
  removeAttachment: removePendingAttachment,
  removeSelectedKnowledgeBase,
  resolvePendingOp: (invokeId: string, allowed: boolean) =>
    aiPanelStore.resolvePageOp(invokeId, allowed),
  retry: retryLastMessage,
  richTextApply: onRichTextApply,
  richTextDiscard: onRichTextDiscard,
  richTextUndo: onRichTextUndo,
  scroll: handleMessagesScroll,
  scrollToBottom: () => scrollToBottom(true),
  scrollToTop: () => scrollToTop(),
  selectConversation: onSelectConversation,
  selectMentionCandidate: onSelectMentionCandidate,
  send: handleSendMessage,
  startEditTitle,
  stop: stopGeneration,
  'update:conversationSearch': (value: string) => {
    conversationSearch.value = value;
  },
  'update:editingTitle': (value: string) => {
    editingTitle.value = value;
  },
  'update:inputMessage': (value: string) => {
    inputMessage.value = value;
  },
  'update:interactionMode': (value: 'confirm' | 'trusted_auto') => {
    interactionMode.value = value;
  },
};

const {
  dragging,
  effectivePanelStyle,
  isFullMode,
  loadSavedWidth,
  onDragStart,
} = usePanelWidth(aiPanelStore);

watch(selectedAgentId, (agentId) => {
  if (agentId) {
    ensureAgentVarsLoaded(agentId);
  }
  if (
    manualNewConversationAgentId.value &&
    agentId !== manualNewConversationAgentId.value
  ) {
    manualNewConversationAgentId.value = null;
  }
});

watch(
  [() => aiPanelStore.pinnedAgentId, agents],
  ([pinnedAgentId, availableAgents]) => {
    if (
      pinnedAgentId &&
      availableAgents.some((agent) => agent.id === pinnedAgentId) &&
      selectedAgentId.value !== pinnedAgentId
    ) {
      selectedAgentId.value = pinnedAgentId;
    }
  },
  { immediate: true },
);

watch([activeConversationId, selectedAgentId], ([conversationId, agentId]) => {
  if (conversationId === null) {
    aiPanelStore.resetConversation();
    return;
  }
  aiPanelStore.setConversation(conversationId, agentId ?? undefined);
});

watchEffect(() => {
  const shouldOffset =
    aiPanelStore.visible &&
    !aiPanelStore.minimized &&
    aiPanelStore.mode === 'panel' &&
    aiPanelStore.docked;
  const offset = shouldOffset ? `${aiPanelStore.panelWidth}px` : '0px';
  document.documentElement.style.setProperty('--ai-panel-right-offset', offset);
});

onMounted(() => {
  loadSavedWidth();
  document.addEventListener('mousedown', onDocumentClick);
});

onUnmounted(() => {
  cleanup();
  document.removeEventListener('mousedown', onDocumentClick);
  document.documentElement.style.removeProperty('--ai-panel-right-offset');
});
</script>

<template>
  <Teleport to="body">
    <!-- Panel -->
    <Transition name="slide-panel">
      <div
        v-if="aiPanelStore.visible"
        ref="panelRef"
        data-ai-panel
        class="fixed right-0 top-0 z-[2001] flex h-full flex-col bg-card shadow-2xl transition-[width] duration-200"
        :class="isFullMode ? '' : 'border-l border-border/50'"
        :style="effectivePanelStyle"
      >
        <!-- Drag handle (left edge, hidden in fullscreen) -->
        <div
          v-if="!isFullMode"
          class="absolute left-0 top-0 z-10 h-full w-1 cursor-col-resize transition-colors hover:bg-primary/30"
          :class="dragging ? 'bg-primary/40' : ''"
          @mousedown="onDragStart"
        ></div>

        <AgentVarsModal
          v-bind="agentVarsModalProps"
          v-on="agentVarsModalListeners"
        />

        <!-- Header -->
        <AIChatPanelHeader v-bind="headerProps" v-on="headerListeners" />

        <AIChatPanelToolbarRow v-bind="toolbarProps" v-on="toolbarListeners" />

        <!-- Streaming progress bar (T5) -->
        <div
          v-if="streaming"
          class="h-0.5 w-full overflow-hidden bg-primary/10"
        >
          <div class="streaming-bar h-full bg-primary/60"></div>
        </div>

        <AIChatMemoryPanel
          :open="showMemoryPanel && !showHistory"
          :loading="memoryLoading"
          :clearing="clearingMemory"
          :memory-state="memoryState"
          @clear="onClearMemory"
        />

        <AIChatPanelBody v-bind="panelBodyProps" v-on="panelBodyListeners" />
      </div>
    </Transition>

    <AIChatPanelOverlays v-bind="overlayProps" v-on="overlayListeners" />
  </Teleport>
</template>

<style scoped src="./ai-chat-slide-panel-shell.css"></style>
