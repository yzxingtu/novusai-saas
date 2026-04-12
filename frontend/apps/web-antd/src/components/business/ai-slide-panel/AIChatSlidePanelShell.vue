<script lang="ts" setup>
/**
 * AI Chat Slide Panel
 *
 * Right slide-in panel with intelligent routing / 右侧滑入面板，集成智能路由：
 * - Reuses useAIChat for messages, SSE streaming, conversation management / 复用 useAIChat 处理消息、SSE 流式、对话管理
 * - Integrates useAgentRouter for P1-P4 intelligent routing / 集成 useAgentRouter 实现 P1-P4 智能路由
 * - Panel state controlled by useAIPanelStore / 由 useAIPanelStore 控制面板状态
 * - Route result notification badge / 路由结果提示 badge
 * - Pin agent UI / Pin 智能体 UI
 */
import type { AIPageMode } from '@vben/types';

import type { RichTextAITask } from '#/types/ai-chat';

import {
  computed,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  toRef,
  watch,
  watchEffect,
} from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Drawer, Image, message, Spin, Tooltip } from 'ant-design-vue';
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
import { normalizeStarterQuestions } from '#/utils/ai-starter-questions';
import { getErrorMessage } from '#/utils/error-helpers';
import { getFileIcon } from '#/utils/file';
import { toAbsoluteApiUrl } from '#/utils/image';

import AgentVarsModal from './AgentVarsModal.vue';
import AIChatComposer from './AIChatComposer.vue';
import AIChatConversationFooter from './AIChatConversationFooter.vue';
import AIChatHistoryPane from './AIChatHistoryPane.vue';
import AIChatMessageViewport from './AIChatMessageViewport.vue';
import AIChatPanelHeader from './AIChatPanelHeader.vue';
import AIChatTimelineDrawer from './AIChatTimelineDrawer.vue';
import AIChatPanelUtilityActions from './AIChatPanelUtilityActions.vue';
import PageAIRail from './PageAIRail.vue';
import { useAgentRouter } from './use-agent-router';
import { usePageAICapability } from './use-page-ai-capability';
import { usePanelHistory } from './use-panel-history';
import { usePanelHeader } from './use-panel-header';
import { usePanelContextBridge } from './use-panel-context-bridge';
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

/** Panel title: "{SiteName} AI" / 面板标题 */
const panelTitle = computed(() => {
  const siteName =
    publicConfigStore.platformConfig?.brand?.siteName ||
    publicConfigStore.tenantConfig?.brand?.siteName ||
    import.meta.env.VITE_APP_TITLE ||
    'NovusAI';
  return `${siteName} AI`;
});

/** Whether an agent is pinned (via Ctrl+K CommandBar) / 智能体是否被固定（通过 Ctrl+K CommandBar） */
const isPinned = computed(
  () => !!aiPanelStore.pinnedAgentId && !!aiPanelStore.pinnedAgentName,
);

// ============ Chat Logic (reuse useAIChat) / 对话逻辑（复用 useAIChat） ============

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

// ============ Input Variables Modal / 输入变量弹窗 ============

/** Multi-agent vars editor (edit button in header) / 多智能体变量编辑（头部编辑按钮） */
const multiVarsModalVisible = ref(false);
const multiVarsFormValues = reactive<Record<number, Record<string, string>>>(
  {},
);
const multiVarsPersist = ref(false);

function openMultiVarsEditor() {
  for (const a of agentsWithVarsInConversation.value) {
    ensureAgentVarsLoaded(a.id);
    multiVarsFormValues[a.id] = { ...allAgentsVariables.value[a.id] };
    // Fill defaults for any vars not yet set / 为未设置的变量填充默认值
    for (const v of a.input_variables ?? []) {
      if (!multiVarsFormValues[a.id]![v.name]) {
        multiVarsFormValues[a.id]![v.name] = v.default ?? '';
      }
    }
  }
  multiVarsPersist.value = false;
  multiVarsModalVisible.value = true;
}

function onMultiVarsConfirm() {
  for (const a of agentsWithVarsInConversation.value) {
    const vals = multiVarsFormValues[a.id];
    if (vals) {
      applyVariables(a.id, { ...vals }, multiVarsPersist.value);
    }
  }
  multiVarsModalVisible.value = false;
}

function onSingleVarValueChange(payload: { name: string; value: string }) {
  varsFormValues[payload.name] = payload.value;
}

function onSinglePersistChange(value: boolean) {
  varsPersist.value = value;
}

function onMultiVarValueChange(payload: {
  agentId: number;
  name: string;
  value: string;
}) {
  if (!multiVarsFormValues[payload.agentId]) {
    multiVarsFormValues[payload.agentId] = {};
  }
  multiVarsFormValues[payload.agentId]![payload.name] = payload.value;
}

function onMultiPersistChange(value: boolean) {
  multiVarsPersist.value = value;
}

function onMultiVarsCancel() {
  multiVarsModalVisible.value = false;
}

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

/** Detect agent switch: adjacent assistant messages with different agent_id / 检测智能体切换（相邻助手消息 agent_id 不同） */
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

// ============ Agent Router / 智能体路由 ============

const { routing, routeMessage } = useAgentRouter({
  apiPrefix: toRef(props, 'apiPrefix'),
  agents,
  pinnedAgentId: toRef(aiPanelStore, 'pinnedAgentId'),
  pinnedAgentName: toRef(aiPanelStore, 'pinnedAgentName'),
  activeConversationId,
});

/** Route result notice (fade out) / 路由结果提示（渐隐） */
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

// ============ Page AI Capability Indicator / 页面 AI 能力指示 ============
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

// ============ Send message (routing + streaming) / 发送消息（路由 + 流式） ============

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

// ============ Input keyboard handling / 输入键盘处理 ============

function handleKeyDown(e: KeyboardEvent) {
  if (handleInputKeyDown(e)) {
    return;
  }
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    handleSendMessage();
  }
}

// ============ History panel / 历史面板 ============
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
// ============ Panel Controls / 面板控制 ============
const panelRef = ref<HTMLElement | null>(null);
function handleClose() {
  aiPanelStore.clearResolvedPageOps?.();
  aiPanelStore.close();
}

function handleMinimize() {
  aiPanelStore.minimize();
}

function handleToggleMode() {
  aiPanelStore.toggleMode();
}

function handleToggleDock() {
  aiPanelStore.toggleDock();
}

// ============ Click-outside: close when not docked / 非停靠时点击外部关闭 ============

function onDocumentClick(e: MouseEvent) {
  if (
    !aiPanelStore.docked &&
    aiPanelStore.visible &&
    panelRef.value &&
    !panelRef.value.contains(e.target as Node)
  ) {
    aiPanelStore.close();
  }
}

// ============ Pin / 固定智能体 ============
function unpinAgent() {
  aiPanelStore.togglePin(0, '');
}
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

const composerAttachments = computed(() =>
  pendingAttachments.value.map((attachment, index) => ({
    icon:
      attachment.type === 'image'
        ? undefined
        : getFileIcon(attachment.name || '', attachment.mime_type),
    key: attachment.url || `${attachment.type}-${index}`,
    name: attachment.name || '',
    previewUrl: attachment.preview || attachment.url,
    type: attachment.type,
  })),
);

const composerBoundKnowledgeBases = computed(() =>
  agentKBBindings.value.map((binding) => ({
    id: binding.knowledge_base_id,
    label: binding.kb_name || `KB#${binding.knowledge_base_id}`,
  })),
);

const composerSelectedKnowledgeBases = computed(() =>
  selectedKBIds.value.map((knowledgeBaseId) => ({
    id: knowledgeBaseId,
    label:
      agentKBBindings.value.find(
        (binding) => binding.knowledge_base_id === knowledgeBaseId,
      )?.kb_name || `KB#${knowledgeBaseId}`,
  })),
);

const composerMentionCandidates = computed(() =>
  mentionCandidates.value.map((candidate, candidateIndex) => ({
    active: candidateIndex === mentionActiveIndex.value,
    id: candidate.binding.knowledge_base_id,
    kind: candidate.kind,
    subtitle: $t('common.globalAiChat.mentionKbPickHint'),
    title:
      candidate.binding.kb_name || `KB#${candidate.binding.knowledge_base_id}`,
  })),
);

const composerSendState = computed(() => {
  if (streaming.value) {
    return 'streaming' as const;
  }
  if (routing.value) {
    return 'routing' as const;
  }
  if (sending.value || uploading.value) {
    return 'sending' as const;
  }
  return 'idle' as const;
});

const composerSendDisabled = computed(
  () =>
    (!inputMessage.value.trim() && pendingAttachments.value.length === 0) ||
    agents.value.length === 0 ||
    sending.value ||
    uploading.value,
);

const composerAttachmentLimitHint = computed(() =>
  props.showAttachments && pendingAttachments.value.length > 0
    ? $t('common.globalAiChat.attachmentCount', {
        count: pendingAttachments.value.length,
        max: 5,
      })
    : '',
);

function onComposerSelectMentionCandidate(payload: {
  id: number;
  kind: 'knowledge_base';
}) {
  const knowledgeBaseCandidate = mentionCandidates.value.find(
    (candidate) =>
      candidate.kind === 'knowledge_base' &&
      candidate.binding.knowledge_base_id === payload.id,
  );
  if (knowledgeBaseCandidate?.kind === 'knowledge_base') {
    selectMentionKnowledgeBase(knowledgeBaseCandidate.binding);
  }
}

// ============ Screenshot / 页面截图 ============

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

// ============ Welcome & Suggested Questions / 欢迎语与推荐问 ============

const starterAgent = computed(() => {
  return selectedAgent.value ?? null;
});

const effectiveWelcomeMessage = computed(() => {
  return starterAgent.value?.welcome_message || '';
});

const effectiveSuggestedQuestions = computed<string[]>(() => {
  return normalizeStarterQuestions(starterAgent.value?.suggested_questions);
});

function askSuggested(question: string) {
  inputMessage.value = question;
  handleSendMessage();
}

// ============ Image preview lightbox / 图片预览灯箱 ============

const previewImageUrl = ref('');
const previewImageVisible = ref(false);

function openImagePreview(url: string) {
  previewImageUrl.value = url;
  previewImageVisible.value = true;
}

function isLikelyImageUrl(url: string) {
  const normalized = (url || '').trim().toLowerCase();
  if (!normalized) return false;
  if (normalized.startsWith('data:image/')) return true;
  if (normalized.startsWith('blob:')) return true;
  if (/\/api\/public\/attachments\/\d+\/image(?:[?#]|$)/.test(normalized)) {
    return true;
  }
  const withoutQuery = normalized.split('?')[0]?.split('#')[0] || normalized;
  return /\.(?:avif|bmp|gif|ico|jpe?g|png|svg|webp)$/i.test(withoutQuery);
}

function handleOpenUrl(url: string) {
  const normalizedUrl = toAbsoluteApiUrl(url) || url;
  if (!normalizedUrl) return;
  if (isLikelyImageUrl(normalizedUrl)) {
    openImagePreview(normalizedUrl);
    return;
  }
  window.open(normalizedUrl, '_blank', 'noopener,noreferrer');
}

// ============ Copy / 复制消息 ============

async function onCopyMessage(content: string) {
  await copyMessage(content);
}

// ============ Panel width / 面板宽度 ============
const {
  dragging,
  effectivePanelStyle,
  isFullMode,
  loadSavedWidth,
  onDragStart,
} = usePanelWidth(aiPanelStore);

// ============ Pre-load vars on agent switch（KB 绑定由 useAIChat 内 effectiveKbAgentId 加载）===========

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

// ============ Sync conversation state to store / 同步对话状态到 store ============

watch([activeConversationId, selectedAgentId], ([conversationId, agentId]) => {
  if (conversationId === null) {
    aiPanelStore.resetConversation();
    return;
  }
  aiPanelStore.setConversation(conversationId, agentId ?? undefined);
});

// ============ Lifecycle / 生命周期 ============

/** Sync CSS variable for drawer/modal offset when AI panel is docked / AI 面板停靠时同步抽屉/弹窗偏移 CSS 变量 */
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

        <div
          data-testid="ai-panel-toolbar-row"
          class="w-full shrink-0 px-3 pb-2 pt-1"
          :class="hasPageAI ? '' : 'flex justify-end'"
        >
          <PageAIRail
            v-if="hasPageAI"
            data-testid="ai-panel-page-ai-row"
            :diagnostics="pageAIDiagnostics"
            :fallback-only="pageAIFallbackOnly"
            :has-page-a-i="hasPageAI"
            :has-expandable-details="hasExpandablePageAIDetails"
            :details-expanded="pageAIDetailsExpanded"
            :page-a-i-rail-tooltip="pageAIRailTooltip"
            :operation-count="pageAIOperationCount"
            :page-a-i-summary="pageAISummary"
            :page-a-i-stat-badges="pageAIStatBadges"
            :page-a-i-visible-operations="pageAIVisibleOperations"
            :page-a-i-remaining-operation-count="pageAIRemainingOperationCount"
            :resolved-page-a-i-title="resolvedPageAITitle"
            @toggle-details="togglePageAIDetails"
            @expand-all-operations="expandAllPageAIOperations"
          >
            <template #actions>
              <AIChatPanelUtilityActions
                :can-force-reroute="canForceReroute"
                compact
                :force-reroute-next-turn="forceRerouteNextTurn"
                :has-header-variable-values="hasHeaderVariableValues"
                :header-more-has-attention="headerMoreHasAttention"
                :header-more-menu-items="headerMoreMenuItems"
                :show-header-more-menu="showHeaderMoreMenu"
                :show-header-vars-button="showHeaderVarsButton"
                :show-history="showHistory"
                :show-reroute-button="!!activeConversationId && !isPinned"
                @edit-vars="onEditHeaderVars"
                @new-chat="onStartNewChat"
                @toggle-history="toggleHistory"
                @toggle-reroute="onToggleForceReroute"
              />
            </template>
          </PageAIRail>

          <AIChatPanelUtilityActions
            v-else
            :can-force-reroute="canForceReroute"
            :force-reroute-next-turn="forceRerouteNextTurn"
            :has-header-variable-values="hasHeaderVariableValues"
            :header-more-has-attention="headerMoreHasAttention"
            :header-more-menu-items="headerMoreMenuItems"
            :show-header-more-menu="showHeaderMoreMenu"
            :show-header-vars-button="showHeaderVarsButton"
            :show-history="showHistory"
            :show-reroute-button="!!activeConversationId && !isPinned"
            @edit-vars="onEditHeaderVars"
            @new-chat="onStartNewChat"
            @toggle-history="toggleHistory"
            @toggle-reroute="onToggleForceReroute"
          />
        </div>

        <!-- Streaming progress bar (T5) -->
        <div
          v-if="streaming"
          class="h-0.5 w-full overflow-hidden bg-primary/10"
        >
          <div class="streaming-bar h-full bg-primary/60"></div>
        </div>

        <!-- Memory panel (redesigned) -->
        <Transition name="fade">
          <div
            v-if="showMemoryPanel && !showHistory"
            class="shrink-0 border-b border-border/30 bg-muted/5 px-4 py-3"
          >
            <div class="mb-2.5 flex items-center justify-between">
              <div
                class="flex items-center gap-1.5 text-xs font-medium text-foreground"
              >
                <IconifyIcon
                  icon="lucide:brain"
                  class="size-3.5 text-primary"
                />
                {{ $t('common.globalAiChat.memoryUpdated') }}
              </div>
              <Tooltip :title="$t('common.globalAiChat.clearMemory')">
                <button
                  class="flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-40"
                  :disabled="clearingMemory"
                  @click="onClearMemory"
                >
                  <Spin v-if="clearingMemory" size="small" />
                  <IconifyIcon v-else icon="lucide:eraser" class="size-3" />
                  {{ $t('common.globalAiChat.clearMemory') }}
                </button>
              </Tooltip>
            </div>

            <div v-if="memoryLoading" class="py-3 text-center">
              <Spin size="small" />
            </div>
            <div
              v-else-if="
                !memoryState ||
                (memoryState.preferences.length === 0 &&
                  memoryState.constraints.length === 0 &&
                  memoryState.task_states.length === 0 &&
                  memoryState.verified_facts.length === 0)
              "
              class="py-2 text-center text-xs text-muted-foreground"
            >
              {{ $t('common.globalAiChat.clearMemoryEmpty') }}
            </div>
            <div v-else class="space-y-2">
              <div
                v-for="section in [
                  {
                    key: 'preferences',
                    icon: 'lucide:heart',
                    label: $t('common.globalAiChat.memoryPreferences'),
                    items: memoryState.preferences,
                  },
                  {
                    key: 'constraints',
                    icon: 'lucide:shield',
                    label: $t('common.globalAiChat.memoryConstraints'),
                    items: memoryState.constraints,
                  },
                  {
                    key: 'task_states',
                    icon: 'lucide:list-checks',
                    label: $t('common.globalAiChat.memoryTaskStates'),
                    items: memoryState.task_states,
                  },
                  {
                    key: 'verified_facts',
                    icon: 'lucide:check-circle',
                    label: $t('common.globalAiChat.memoryVerifiedFacts'),
                    items: memoryState.verified_facts,
                  },
                ].filter((s) => s.items.length > 0)"
                :key="section.key"
                class="rounded-lg bg-background/60 px-2.5 py-2"
              >
                <div
                  class="mb-1 flex items-center gap-1 text-[11px] font-medium text-muted-foreground"
                >
                  <IconifyIcon :icon="section.icon" class="size-3" />
                  {{ section.label }}
                </div>
                <ul class="space-y-0.5 text-[11px] text-foreground/80">
                  <li
                    v-for="(item, ii) in section.items"
                    :key="ii"
                    class="flex items-start gap-1.5 pl-1"
                  >
                    <span
                      class="mt-1.5 size-1 shrink-0 rounded-full bg-primary/40"
                    ></span>
                    {{ item }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </Transition>

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
            @select-mention-candidate="onComposerSelectMentionCandidate"
            @send="handleSendMessage"
            @stop="stopGeneration"
          />
        </template>
      </div>
    </Transition>

    <!-- Minimized bubble -->
    <Transition name="bubble">
      <div
        v-if="aiPanelStore.minimized && !aiPanelStore.visible"
        class="fixed bottom-6 right-6 z-[2001] flex cursor-pointer items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-primary-foreground shadow-lg transition-all hover:shadow-xl hover:brightness-110"
        @click="aiPanelStore.restore()"
      >
        <IconifyIcon icon="lucide:sparkles" class="size-5" />
        <span class="text-sm font-medium">
          {{ $t('common.aiPanel.title') }}
        </span>
        <span
          v-if="aiPanelStore.hasUnread"
          class="size-2 rounded-full bg-destructive"
        ></span>
        <IconifyIcon
          icon="lucide:x"
          class="ml-1 size-3.5 opacity-60 hover:opacity-100"
          @click.stop="aiPanelStore.close()"
        />
      </div>
    </Transition>

    <Drawer
      v-model:open="showContextDrawer"
      :title="$t('common.globalAiChat.contextDiagnostics')"
      width="520"
    >
      <div class="space-y-4">
        <div class="rounded-2xl border border-border/60 bg-muted/10 p-3">
          <div class="text-xs font-medium text-muted-foreground">
            {{ $t('common.globalAiChat.interactionModeLabel') }}
          </div>
          <div class="mt-1 text-sm font-semibold text-foreground">
            {{ interactionModeLabel }}
          </div>
          <div
            v-if="interactionModeDowngraded"
            class="mt-2 rounded-xl border border-amber-300/50 bg-amber-50 px-3 py-2 text-xs text-amber-800"
          >
            <div class="font-medium">
              {{ $t('common.globalAiChat.trustedAutoDowngraded') }}
            </div>
            <div class="mt-1">
              {{ interactionModeRequested }} -> {{ interactionModeLabel }}
            </div>
            <div v-if="interactionModeDowngradeText" class="mt-1 text-[11px]">
              {{ interactionModeDowngradeText }}
            </div>
          </div>
        </div>
        <div
          v-if="conversationContextDiagnostics"
          class="rounded-2xl border border-border/60 bg-muted/10 p-3"
        >
          <div class="mb-2 text-xs font-medium text-muted-foreground">
            {{ $t('common.detail') }}
          </div>
          <pre
            class="overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-foreground"
            >{{ JSON.stringify(conversationContextDiagnostics, null, 2) }}</pre
          >
        </div>
        <div
          v-if="lastRunSummary"
          class="rounded-2xl border border-border/60 bg-muted/10 p-3"
        >
          <div class="mb-2 text-xs font-medium text-muted-foreground">
            {{ $t('common.globalAiChat.lastRunSummary') }}
          </div>
          <pre
            class="overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-foreground"
            >{{ JSON.stringify(lastRunSummary, null, 2) }}</pre
          >
        </div>
      </div>
    </Drawer>

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
