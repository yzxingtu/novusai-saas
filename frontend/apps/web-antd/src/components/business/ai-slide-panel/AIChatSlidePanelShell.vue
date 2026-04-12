<script lang="ts" setup>
import type { AIPageMode } from '@vben/types';
import type { RichTextAITask } from '#/types/ai-chat';
import {
  computed,
  onMounted,
  onUnmounted,
  ref,
  toRef,
  watch,
  watchEffect,
} from 'vue';

import { Image, message } from 'ant-design-vue';
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
import AIChatContextDiagnosticsDrawer from './AIChatContextDiagnosticsDrawer.vue';
import AgentVarsModal from './AgentVarsModal.vue';
import AIChatComposer from './AIChatComposer.vue';
import AIChatConversationFooter from './AIChatConversationFooter.vue';
import AIChatHistoryPane from './AIChatHistoryPane.vue';
import AIChatMemoryPanel from './AIChatMemoryPanel.vue';
import AIChatMessageViewport from './AIChatMessageViewport.vue';
import AIChatPanelHeader from './AIChatPanelHeader.vue';
import AIChatPanelMinimizedBubble from './AIChatPanelMinimizedBubble.vue';
import AIChatPanelToolbarRow from './AIChatPanelToolbarRow.vue';
import AIChatTimelineDrawer from './AIChatTimelineDrawer.vue';
import { useAgentRouter } from './use-agent-router';
import { usePageAICapability } from './use-page-ai-capability';
import { usePanelComposer } from './use-panel-composer';
import { usePanelHistory } from './use-panel-history';
import { usePanelHeader } from './use-panel-header';
import { usePanelContextBridge } from './use-panel-context-bridge';
import { usePanelLinkPreview } from './use-panel-link-preview';
import { usePanelShellActions } from './use-panel-shell-actions';
import { usePanelVarsEditor } from './use-panel-vars-editor';
import { usePendingPageOps } from './use-pending-page-ops';
import { usePanelWidth } from './use-panel-width';
import { useRichTextTaskOrchestration } from './use-rich-text-task-orchestration';

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

const manualNewConversationAgentId = ref<null | number>(null);
const showHistory = ref(false);
const showMemoryPanel = ref(false);
const forceRerouteNextTurn = ref(false);
const sendPreparedRichTextTaskRef = ref<
  (task: RichTextAITask) => Promise<boolean>
>(async () => false);

const {
  deferSendForMissingVariables,
  onVarsCancel,
  onVarsConfirm,
  openVarsModal,
  varsFormValues,
  varsModalAgent,
  varsModalVisible,
  varsPersist,
} = usePanelContextBridge({
  agents,
  activeConversationId,
  allAgentsVariables,
  applyVariables,
  clearMentionedAgent: () => {},
  clearPendingRichTextTask: aiPanelStore.clearPendingRichTextTask,
  clearResolvedPageOps: () => aiPanelStore.clearResolvedPageOps?.(),
  chatMessages,
  consumePendingAgentId: () => aiPanelStore.consumePendingAgentId() ?? null,
  ensureAgentVarsLoaded,
  forceRerouteNextTurn,
  handleSendMessage,
  inputMessage,
  loadAgents,
  loadConversationMessages,
  loadConversations,
  manualNewConversationAgentId,
  onConversationRestored: () => emit('conversationRestored'),
  onMessageSent: () => emit('messageSent'),
  pendingConversationId: toRef(props, 'pendingConversationId'),
  pendingMessage: toRef(props, 'pendingMessage'),
  sendMessage,
  sendPreparedRichTextTask: (task) => sendPreparedRichTextTaskRef.value(task),
  selectedAgentId,
  showHistory,
  showMemoryPanel,
  startNewConversation,
  storePendingAgentId: toRef(aiPanelStore, 'pendingAgentId'),
  storePendingConversationId: toRef(aiPanelStore, 'pendingConversationId'),
  storePendingMessage: toRef(aiPanelStore, 'pendingMessage'),
  visible: toRef(aiPanelStore, 'visible'),
});

const {
  multiVarsFormValues,
  multiVarsModalVisible,
  multiVarsPersist,
  onMultiPersistChange,
  onMultiVarValueChange,
  onMultiVarsCancel,
  onMultiVarsConfirm,
  onSinglePersistChange,
  onSingleVarValueChange,
  openMultiVarsEditor,
} = usePanelVarsEditor({
  agentsWithVarsInConversation,
  allAgentsVariables,
  applyVariables,
  ensureAgentVarsLoaded,
  varsFormValues,
  varsPersist,
});

const {
  getRichTextDraftState,
  onRichTextApply,
  onRichTextDiscard,
  onRichTextUndo,
  sendPreparedRichTextTask,
} = useRichTextTaskOrchestration({
  activeConversationId,
  agents,
  allAgentsVariables,
  chatMessages,
  ensureAgentVarsLoaded,
  inputMessage,
  loadConversationMessages,
  manualNewConversationAgentId,
  onMissingVariables: ({ agentId, agentName, requiredVars, task }) => {
    deferSendForMissingVariables({
      agentId,
      agentName,
      pageContext: null,
      requiredVars,
      richTextTask: task,
      routeSource: 'rich_text_ai',
    });
  },
  onTaskQueued: () => {
    message.info($t('common.richTextTaskQueued'));
  },
  selectedAgentId,
  sendMessage,
  sending,
  showHistory,
  showMemoryPanel,
  startNewConversation,
  store: aiPanelStore,
  streaming,
});
sendPreparedRichTextTaskRef.value = sendPreparedRichTextTask;

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

const { routing, routeMessage } = useAgentRouter({
  apiPrefix: toRef(props, 'apiPrefix'),
  agents,
  pinnedAgentId: toRef(aiPanelStore, 'pinnedAgentId'),
  pinnedAgentName: toRef(aiPanelStore, 'pinnedAgentName'),
  activeConversationId,
});

const routeNotice = ref<null | string>(null);
let routeNoticeTimer: null | ReturnType<typeof setTimeout> = null;

function showRouteNotice(text: string) {
  routeNotice.value = text;
  if (routeNoticeTimer) clearTimeout(routeNoticeTimer);
  routeNoticeTimer = setTimeout(() => {
    routeNotice.value = null;
  }, 4000);
}

const currentConversationAgentName = computed(() => {
  if (!activeConversationId.value) return '';
  return (
    selectedAgent.value?.name ||
    conversations.value.find((conv) => conv.id === activeConversationId.value)
      ?.agent_name ||
    ''
  );
});

const canForceReroute = computed(
  () =>
    !!activeConversationId.value &&
    !isPinned.value &&
    !routing.value &&
    !sending.value &&
    !streaming.value,
);

function clearRoutingIntent() {
  forceRerouteNextTurn.value = false;
  manualNewConversationAgentId.value = null;
}

function onToggleForceReroute() {
  forceRerouteNextTurn.value = !forceRerouteNextTurn.value;
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
const pageAIOperationCount = pageAICapability.pageAIOperationCount;
const expandAllPageAIOperations = pageAICapability.expandAllPageAIOperations;
const hasExpandablePageAIDetails = pageAICapability.hasExpandablePageAIDetails;
const hasPageAI = pageAICapability.hasPageAI;
const pageAIDetailsExpanded = pageAICapability.pageAIDetailsExpanded;
const pageAIDiagnostics = pageAICapability.pageAIDiagnostics;
const pageAIFallbackOnly = pageAICapability.pageAIFallbackOnly;
const pageAIRailTooltip = pageAICapability.pageAIRailTooltip;
const pageAIRemainingOperationCount =
  pageAICapability.pageAIRemainingOperationCount;
const pageAISummary = pageAICapability.pageAISummary;
const pageAIStatBadges = pageAICapability.pageAIStatBadges;
const pageAIVisibleOperations = pageAICapability.pageAIVisibleOperations;
const resolvedPageAITitle = pageAICapability.resolvedPageAITitle;
const togglePageAIDetails = pageAICapability.togglePageAIDetails;

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
  filteredConversations,
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
  starterAgent,
  unpinAgent,
} = usePanelShellActions({
  aiPanelStore,
  handleSendMessage,
  inputMessage,
  selectedAgent,
});

const {
  headerConversationSummary,
  headerMoreHasAttention,
  headerMoreMenuItems,
  hasHeaderVariableValues,
  onClearMemory,
  onEditHeaderVars,
  refreshTimeline,
  showContextDrawer,
  showHeaderMoreMenu,
  showHeaderVarsButton,
  showTimelineDrawer,
  timelineItems,
  timelineLoading,
  timelineRefreshing,
} = usePanelHeader({
  activeConversationId,
  agentsWithVarsInConversation,
  allAgentsVariables,
  apiPrefix: toRef(props, 'apiPrefix'),
  chatMessages,
  clearConversationMemory,
  currentConversationAgentName,
  exportMenuItems,
  fetchConversationMemory,
  forceRerouteNextTurn,
  isPinned,
  lastMemoryUpdated,
  loadConversationMessages,
  onOpenMultiVarsEditor: openMultiVarsEditor,
  onOpenVarsModal: openVarsModal,
  routing,
  selectedAgent,
  showMemoryPanel,
  totalTokensUsed,
  unpinAgent,
});

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

async function onCopyMessage(content: string) {
  await copyMessage(content);
}
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
  if (routeNoticeTimer) clearTimeout(routeNoticeTimer);
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
          :single-open="varsModalVisible"
          :single-agent="varsModalAgent"
          :single-values="varsFormValues"
          :single-persist="varsPersist"
          :multi-open="multiVarsModalVisible"
          :multi-agents="agentsWithVarsInConversation"
          :multi-values="multiVarsFormValues"
          :multi-persist="multiVarsPersist"
          @single-confirm="onVarsConfirm"
          @single-cancel="onVarsCancel"
          @single-value-change="onSingleVarValueChange"
          @single-persist-change="onSinglePersistChange"
          @multi-confirm="onMultiVarsConfirm"
          @multi-cancel="onMultiVarsCancel"
          @multi-value-change="onMultiVarValueChange"
          @multi-persist-change="onMultiPersistChange"
        />

        <!-- Header -->
        <AIChatPanelHeader
          :can-force-reroute="canForceReroute"
          :docked="aiPanelStore.docked"
          :force-reroute-next-turn="forceRerouteNextTurn"
          :has-header-variable-values="hasHeaderVariableValues"
          :header-conversation-summary="headerConversationSummary"
          :header-more-has-attention="headerMoreHasAttention"
          :header-more-menu-items="headerMoreMenuItems"
          :mode="aiPanelStore.mode"
          :panel-title="panelTitle"
          :route-notice="routeNotice"
          :routing="routing"
          @close="handleClose"
          @minimize="handleMinimize"
          @toggle-dock="handleToggleDock"
          @toggle-mode="handleToggleMode"
        />

        <AIChatPanelToolbarRow
          :can-force-reroute="canForceReroute"
          :force-reroute-next-turn="forceRerouteNextTurn"
          :has-expandable-page-a-i-details="hasExpandablePageAIDetails"
          :has-header-variable-values="hasHeaderVariableValues"
          :has-page-a-i="hasPageAI"
          :header-more-has-attention="headerMoreHasAttention"
          :header-more-menu-items="headerMoreMenuItems"
          :page-a-i-details-expanded="pageAIDetailsExpanded"
          :page-a-i-diagnostics="pageAIDiagnostics"
          :page-a-i-fallback-only="pageAIFallbackOnly"
          :page-a-i-operation-count="pageAIOperationCount"
          :page-a-i-rail-tooltip="pageAIRailTooltip"
          :page-a-i-remaining-operation-count="pageAIRemainingOperationCount"
          :page-a-i-stat-badges="pageAIStatBadges"
          :page-a-i-summary="pageAISummary"
          :page-a-i-visible-operations="pageAIVisibleOperations"
          :resolved-page-a-i-title="resolvedPageAITitle"
          :show-header-more-menu="showHeaderMoreMenu"
          :show-header-vars-button="showHeaderVarsButton"
          :show-history="showHistory"
          :show-reroute-button="!!activeConversationId && !isPinned"
          @edit-vars="onEditHeaderVars"
          @new-chat="onStartNewChat"
          @toggle-history="toggleHistory"
          @toggle-page-details="togglePageAIDetails"
          @toggle-reroute="onToggleForceReroute"
          @expand-all-operations="expandAllPageAIOperations"
        />

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

        <AIChatHistoryPane
          v-if="showHistory"
          :active-conversation-id="activeConversationId"
          :conversation-search="conversationSearch"
          :conversations-count="conversations.length"
          :conversations-loading="conversationsLoading"
          :editing-conversation-id="editingConversationId"
          :editing-title="editingTitle"
          :grouped-conversations="groupedConversations"
          @start-new-chat="onStartNewChat"
          @update:conversation-search="conversationSearch = $event"
          @select-conversation="onSelectConversation"
          @delete-conversation="onDeleteConversation"
          @start-edit-title="startEditTitle"
          @update:editing-title="editingTitle = $event"
          @commit-edit-title="commitEditTitle"
          @cancel-edit-title="cancelEditTitle"
        />

        <!-- Chat area (when not showing history) -->
        <template v-if="!showHistory">
          <AIChatMessageViewport
            :api-prefix="props.apiPrefix"
            :agents="agents"
            :chat-messages="chatMessages"
            :countdown-now="countdownNow"
            :effective-suggested-questions="effectiveSuggestedQuestions"
            :effective-welcome-message="effectiveWelcomeMessage"
            :get-pending-ops-for-message="getPendingOpsForMessage"
            :get-rich-text-draft-state="getRichTextDraftState"
            :is-agent-switch="isAgentSwitch"
            :register-container="
              (element) => {
                if (
                  messagesContainer &&
                  typeof messagesContainer === 'object' &&
                  'value' in messagesContainer
                ) {
                  messagesContainer.value = element;
                }
              }
            "
            :routing="routing"
            :selected-agent="selectedAgent"
            :sending="sending"
            :show-scroll-to-bottom="showScrollToBottom"
            :show-scroll-to-top="showScrollToTop"
            :streaming="streaming"
            :unassociated-pending-ops="unassociatedPendingOps"
            @ask-suggested="askSuggested"
            @copy="onCopyMessage"
            @confirm="confirmAction"
            @reject="rejectAction"
            @consent-confirm="confirmConsent"
            @consent-reject="rejectConsent"
            @open-url="handleOpenUrl"
            @action-click="clickActionButton"
            @regenerate="regenerateMessage"
            @edit="editAndResend"
            @retry="retryLastMessage"
            @rich-text-apply="onRichTextApply"
            @rich-text-discard="onRichTextDiscard"
            @rich-text-undo="onRichTextUndo"
            @resolve-pending-op="
              (invokeId, allowed) =>
                aiPanelStore.resolvePageOp(invokeId, allowed)
            "
            @scroll="handleMessagesScroll"
            @scroll-to-top="scrollToTop()"
            @scroll-to-bottom="scrollToBottom(true)"
          />

          <AIChatConversationFooter
            :message-count="chatMessages.length"
            :total-tokens-used="totalTokensUsed"
            :streaming="streaming"
            :export-menu-items="exportMenuItems"
          />

          <AIChatComposer
            :model-value="inputMessage"
            :disabled="agents.length === 0 || sending"
            :max-length="32000"
            :character-count="inputMessage.length"
            :send-state="composerSendState"
            :send-disabled="composerSendDisabled"
            :show-attachments="props.showAttachments"
            :attach-disabled="agents.length === 0 || sending"
            :attachment-accept="chatAcceptAttribute"
            :attachments="composerAttachments"
            :attachment-limit-hint="composerAttachmentLimitHint"
            :show-screenshot-button="props.showAttachments && supportsVision"
            :screenshot-disabled="agents.length === 0 || sending || capturing"
            :screenshot-loading="capturing"
            :mention-open="mentionOpen"
            :mention-loading="agentsLoading"
            :mention-mixed-hint="$t('common.globalAiChat.mentionMixedHint')"
            :mention-empty-hint="
              mentionCandidates.length === 0 &&
              agentKBBindings.length === 0 &&
              !agentsLoading
                ? $t('common.globalAiChat.mentionKbNoneBound')
                : $t('common.globalAiChat.mentionAgentEmpty')
            "
            :mention-candidates="composerMentionCandidates"
            :bound-knowledge-bases="composerBoundKnowledgeBases"
            :selected-knowledge-bases="composerSelectedKnowledgeBases"
            :show-interaction-mode="chatMessages.length > 0"
            :interaction-mode="interactionMode"
            :shift-enter-hint="$t('common.globalAiChat.shiftEnterHint')"
            @update:model-value="inputMessage = $event"
            @update:interaction-mode="interactionMode = $event"
            @dragover="handleDragOver"
            @drop="handleDrop"
            @file-select="handleFileSelect"
            @keydown="handleKeyDown"
            @paste="handlePaste"
            @capture-screenshot="handleScreenshot"
            @remove-attachment="removePendingAttachment"
            @remove-selected-knowledge-base="removeSelectedKnowledgeBase"
            @select-mention-candidate="onSelectMentionCandidate"
            @send="handleSendMessage"
            @stop="stopGeneration"
          />
        </template>
      </div>
    </Transition>

    <AIChatPanelMinimizedBubble
      :open="aiPanelStore.minimized && !aiPanelStore.visible"
      :has-unread="aiPanelStore.hasUnread"
      @restore="aiPanelStore.restore()"
      @close="aiPanelStore.close()"
    />

    <AIChatContextDiagnosticsDrawer
      v-model:open="showContextDrawer"
      :interaction-mode-label="interactionModeLabel"
      :interaction-mode-requested="interactionModeRequested"
      :interaction-mode-downgraded="interactionModeDowngraded"
      :interaction-mode-downgrade-text="interactionModeDowngradeText"
      :conversation-context-diagnostics="conversationContextDiagnostics"
      :last-run-summary="lastRunSummary"
    />

    <AIChatTimelineDrawer
      :items="timelineItems"
      :loading="timelineLoading"
      :open="showTimelineDrawer"
      :refreshing="timelineRefreshing"
      @refresh="refreshTimeline"
      @update:open="(value) => (showTimelineDrawer = value)"
    />

    <!-- Hidden Image preview uses antd's built-in zoom/rotate toolbar -->
    <Image
      v-if="previewImageUrl"
      :src="previewImageUrl"
      :preview="{
        visible: previewImageVisible,
        onVisibleChange: (visible: boolean) => (previewImageVisible = visible),
      }"
      class="hidden"
    />
  </Teleport>
</template>

<style scoped src="./ai-chat-slide-panel-shell.css"></style>
