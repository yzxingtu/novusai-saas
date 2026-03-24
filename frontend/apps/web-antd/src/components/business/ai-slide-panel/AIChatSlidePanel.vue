<script lang="ts" setup>
import type { ItemType } from 'ant-design-vue/es/menu';

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

import type { PageOperation } from './page-operation-registry';

import type { InputVariable } from '#/components/business/ai-chat-panel/types';

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

import {
  Dropdown,
  Input,
  Menu,
  message,
  Modal,
  Spin,
  Tooltip,
} from 'ant-design-vue';

import ChatMessageItem from '#/components/business/ai-chat-panel/ChatMessageItem.vue';
import { getAgentInputVariables } from '#/components/business/ai-chat-panel/types';
import { useAIChat } from '#/components/business/ai-chat-panel/use-ai-chat';
import { formStateTracker } from '#/composables/use-form-state-tracker';
import { useModalDetector } from '#/composables/use-modal-detector';
import {
  DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS,
  usePageScreenshot,
} from '#/composables/use-page-screenshot';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';
import { usePublicConfigStore } from '#/store/shared/public-config';
import {
  canExposePageOperations,
  filterPageOperationsByPolicy,
  normalizePageAIMode,
  shouldDisablePageContext,
} from '#/utils/ai-page-capabilities';
import { getErrorMessage } from '#/utils/error-helpers';
import { normalizeStarterQuestions } from '#/utils/ai-starter-questions';
import { getFileIcon } from '#/utils/file';

import {
  pageContextVersion,
  resolvePageContext,
} from './page-context-registry';
import { normalizePageKey } from './page-key-utils';
import {
  listPageOperations,
  pageOperationVersion,
} from './page-operation-registry';
import { useAgentRouter } from './use-agent-router';

defineOptions({ name: 'AIChatSlidePanel' });

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

/** Ticking now for 60s confirm countdown / 用于 60s 确认倒计时的计时 */
const countdownNow = ref(Date.now());
const hasUnresolvedPageOps = computed(() =>
  aiPanelStore.pendingPageOps.some((op) => !op.resolved),
);
let countdownInterval: null | ReturnType<typeof setInterval> = null;
watch(
  hasUnresolvedPageOps,
  (has) => {
    if (has && !countdownInterval) {
      countdownInterval = setInterval(() => {
        countdownNow.value = Date.now();
      }, 1000);
    } else if (!has && countdownInterval) {
      clearInterval(countdownInterval);
      countdownInterval = null;
    }
  },
  { immediate: true },
);
onUnmounted(() => {
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
});

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
  loadConversations,
  startNewConversation,
  deleteConversation,
  updateConversationTitle,
  loadConversationMessages,
  chatMessages,
  inputMessage,
  mentionedAgent,
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
  selectMentionAgent,
  selectMentionKnowledgeBase,
  removeSelectedKnowledgeBase,
  selectedKBIds,
  clearMentionedAgent,
  cleanup,
  pendingAttachments,
  uploading,
  fileInput,
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
  trustSession,
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
  totalTokensUsed,
  supportsVision,
  agentKBBindings,
  allAgentsVariables,
  ensureAgentVarsLoaded,
  agentsWithVarsInConversation,
  applyVariables,
} = chat;

/** All tool call IDs across messages (for filtering unassociated ops) / 所有消息中的工具调用 ID */
const allToolCallIds = computed(() => {
  const ids = new Set<string>();
  for (const msg of chatMessages.value ?? []) {
    for (const tc of msg.toolCalls || []) {
      if (tc.id) ids.add(tc.id);
    }
  }
  return ids;
});

/** Pending ops that belong to a specific message (by toolCallId) / 归属于某条消息的待确认操作 */
function getPendingOpsForMessage(msg: { toolCalls?: { id?: string }[] }) {
  const ids = new Set<string>();
  for (const tc of msg.toolCalls || []) {
    if (tc.id) ids.add(tc.id);
  }
  return aiPanelStore.pendingPageOps.filter(
    (op) => !op.resolved && op.toolCallId && ids.has(op.toolCallId),
  );
}

/** Pending ops with no toolCallId or not matched to any message (fallback bottom render) / 未关联到消息的待确认操作（底部兜底） */
const unassociatedPendingOps = computed(() =>
  aiPanelStore.pendingPageOps.filter(
    (op) =>
      !op.resolved &&
      (!op.toolCallId || !allToolCallIds.value.has(op.toolCallId)),
  ),
);

// ============ Input Variables Modal / 输入变量弹窗 ============

/** Single-agent prompt modal (when routing detects missing required vars) / 单智能体变量弹窗（路由检测到必填变量缺失时） */
const varsModalVisible = ref(false);
const varsFormValues = reactive<Record<string, string>>({});
const varsModalAgent = ref<null | {
  id: number;
  name: string;
  vars: InputVariable[];
}>(null);
const varsPersist = ref(false);
/** Pending send context: deferred until vars are filled / 待发送上下文（变量填写后发送） */
const pendingSendContext = ref<null | {
  agentId: number;
  consumeMention?: boolean;
  pageContext: ReturnType<typeof resolvePageContext>;
  routeSource?: string;
}>(null);

function openVarsModal(
  vars: InputVariable[],
  agentId: number,
  agentName: string,
) {
  varsModalAgent.value = { id: agentId, name: agentName, vars };
  ensureAgentVarsLoaded(agentId);
  vars.forEach((v) => {
    varsFormValues[v.name] =
      allAgentsVariables.value[agentId]?.[v.name] ?? v.default ?? '';
  });
  varsPersist.value = false;
  varsModalVisible.value = true;
}

function onVarsConfirm() {
  const required = varsModalAgent.value?.vars.filter((v) => v.required) ?? [];
  const missing = required.filter((v) => !varsFormValues[v.name]?.trim());
  if (missing.length > 0) {
    message.warning(
      $t('user.aiChat.varsModal.fillRequired', {
        fields: missing.map((v) => v.label || v.name).join('、'),
      }),
    );
    return;
  }
  const agentId = varsModalAgent.value!.id;
  applyVariables(agentId, { ...varsFormValues }, varsPersist.value);
  varsModalVisible.value = false;
  // Execute deferred send if this modal was triggered by missing vars / 若弹窗由缺失变量触发则执行延迟发送
  if (pendingSendContext.value) {
    const {
      agentId: pendingAgentId,
      consumeMention,
      pageContext,
      routeSource,
    } = pendingSendContext.value;
    pendingSendContext.value = null;
    if (consumeMention) {
      clearMentionedAgent();
    }
    sendMessage({ agentId: pendingAgentId, pageContext, routeSource });
  }
}

function onVarsCancel() {
  varsModalVisible.value = false;
  pendingSendContext.value = null;
}

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

// Template ref bindings / 模板 ref 绑定
void messagesContainer;
void fileInput;
void handleMessagesScroll;
void showScrollToBottom;
void scrollToBottom;

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
const forceRerouteNextTurn = ref(false);
const manualNewConversationAgentId = ref<null | number>(null);
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

const switchAgentMenuItems = computed(() =>
  agents.value.map((agent) => ({
    key: String(agent.id),
    label: agent.name,
    onClick: () => onStartNewChatWithAgent(agent.id),
  })),
);

function clearRoutingIntent() {
  forceRerouteNextTurn.value = false;
  manualNewConversationAgentId.value = null;
}

function onToggleForceReroute() {
  forceRerouteNextTurn.value = !forceRerouteNextTurn.value;
}

// ============ Page AI Capability Indicator / 页面 AI 能力指示 ============

const FALLBACK_PAGE_CONTEXT_SOURCES = new Set([
  'dom_snapshot',
  'minimal_fallback',
]);

function getPageContextSource(
  ctx: ReturnType<typeof resolvePageContext>,
): null | string {
  const source = ctx?.page_data?.source;
  return typeof source === 'string' ? source : null;
}

function isFallbackOnlyPageContext(
  ctx: ReturnType<typeof resolvePageContext>,
): boolean {
  const source = getPageContextSource(ctx);
  return !!source && FALLBACK_PAGE_CONTEXT_SOURCES.has(source);
}

/** Current page context (reactive to route changes AND registry mutations) / 当前页面上下文 */
const rawPageContext = computed(() => {
  void pageContextVersion.value;
  return resolvePageContext(props.pageContextKey);
});

/** Resolved page key (prefer context, fallback to route key) / 解析后的页面 key */
const resolvedPageKey = computed(() => {
  return (
    rawPageContext.value?.page_key ??
    (props.pageContextKey ? normalizePageKey(props.pageContextKey) : undefined)
  );
});

/** Current page operations list / 当前页面操作列表 */
const currentPageOperations = computed(() => {
  void pageOperationVersion.value;
  const pageKey = resolvedPageKey.value;
  if (!pageKey) return [];
  return filterPageOperationsByPolicy(
    listPageOperations(pageKey),
    pageAIPolicy.value,
  );
});

/** Current page context with runtime AI policy applied / 应用运行时 AI 策略后的当前页面上下文 */
const currentPageContext = computed(() =>
  enrichPageContextWithOperations(
    rawPageContext.value,
    currentPageOperations.value,
  ),
);

const hasFormalPageAIContext = computed(
  () =>
    !!rawPageContext.value && !isFallbackOnlyPageContext(rawPageContext.value),
);

/** Whether the current page has registered AI context / 当前页是否已注册 AI 上下文 */
const hasPageAI = computed(
  () => hasFormalPageAIContext.value || currentPageOperations.value.length > 0,
);

const writablePageOperations = computed(() =>
  currentPageOperations.value.filter((operation) => !operation.readonly),
);

const readonlyPageOperations = computed(() =>
  currentPageOperations.value.filter((operation) => operation.readonly),
);

const PAGE_AI_PREVIEW_LIMIT = 4;
const pageAIDetailsExpanded = ref(false);
const pageAIShowAllOperations = ref(false);

watch(
  () => props.pageContextKey,
  () => {
    pageAIDetailsExpanded.value = false;
    pageAIShowAllOperations.value = false;
  },
);

watch(
  () => hasPageAI.value,
  (hasValue) => {
    if (!hasValue) {
      pageAIDetailsExpanded.value = false;
      pageAIShowAllOperations.value = false;
    }
  },
);

watch(
  () => currentPageOperations.value.length,
  (operationCount) => {
    if (operationCount <= PAGE_AI_PREVIEW_LIMIT) {
      pageAIShowAllOperations.value = false;
    }
  },
);

const pageAIStatBadges = computed(() => {
  const badges: Array<{
    className: string;
    key: string;
    label: string;
  }> = [];

  if (currentPageOperations.value.length > 0) {
    badges.push({
      className: 'bg-primary/8 text-primary/80',
      key: 'total',
      label: $t('common.aiPanel.pageAiOperationCount', {
        count: currentPageOperations.value.length,
      }),
    });
  }

  if (writablePageOperations.value.length > 0) {
    badges.push({
      className: 'bg-amber-500/10 text-amber-700',
      key: 'writable',
      label: $t('common.aiPanel.pageAiWritableCount', {
        count: writablePageOperations.value.length,
      }),
    });
  }

  if (readonlyPageOperations.value.length > 0) {
    badges.push({
      className: 'bg-blue-500/10 text-blue-700',
      key: 'readonly',
      label: $t('common.aiPanel.pageAiReadonlyCount', {
        count: readonlyPageOperations.value.length,
      }),
    });
  }

  return badges;
});

const hasExpandablePageAIDetails = computed(
  () => currentPageOperations.value.length > 0,
);

const pageAIVisibleOperations = computed(() =>
  pageAIShowAllOperations.value
    ? currentPageOperations.value
    : currentPageOperations.value.slice(0, PAGE_AI_PREVIEW_LIMIT),
);

const pageAIRemainingOperationCount = computed(() =>
  Math.max(
    currentPageOperations.value.length - pageAIVisibleOperations.value.length,
    0,
  ),
);

const pageAISummary = computed(() => {
  if (currentPageOperations.value.length > 0) {
    return $t('common.aiPanel.pageAiSummary', {
      count: currentPageOperations.value.length,
    });
  }
  return $t('common.aiPanel.pageAiNoOperations');
});

const resolvedPageAITitle = computed(() => {
  const rawTitle = currentPageContext.value?.page_title?.trim();
  if (!rawTitle) {
    return $t('common.aiPanel.pageAiCurrentPage');
  }

  const translatedTitle = $t(rawTitle);
  if (translatedTitle !== rawTitle) {
    return translatedTitle;
  }

  return rawTitle.includes('.') ? translatedTitle : rawTitle;
});

const pageAIRailTooltip = computed(
  () => `${resolvedPageAITitle.value} · ${pageAISummary.value}`,
);

function togglePageAIDetails() {
  if (pageAIDetailsExpanded.value) {
    pageAIDetailsExpanded.value = false;
    pageAIShowAllOperations.value = false;
    return;
  }

  pageAIDetailsExpanded.value = true;
}

function expandAllPageAIOperations() {
  pageAIDetailsExpanded.value = true;
  pageAIShowAllOperations.value = true;
}

// ============ Send message (routing + streaming) / 发送消息（路由 + 流式） ============

/**
 * Collect lightweight visual state from the current page DOM/window.
 * 从当前页面 DOM/window 收集轻量视觉状态。
 * Uses useModalDetector for structured modal/drawer info.
 */
function collectVisualState() {
  const modals = Array.isArray(modalState.value) ? modalState.value : [];
  return {
    url: window.location.pathname,
    viewport: { w: window.innerWidth, h: window.innerHeight },
    scroll_y: Math.round(window.scrollY),
    has_modal: modals.some((m) => m.type === 'modal'),
    has_drawer: modals.some((m) => m.type === 'drawer'),
    ...(modals.length > 0 ? { open_overlays: modals } : {}),
  };
}

/**
 * Limit form_fields to MAX_FORM_FIELDS entries; append truncation note.
 * 将 form_fields 限制为 MAX_FORM_FIELDS 条并追加截断说明。
 * Return value is safe to spread into page_data.
 */
const MAX_FORM_FIELDS = 20;
// Runtime fallback only; actual admin-configurable limit comes from ai_page_context_max_bytes / 仅运行时兜底；实际可配置上限来自 ai_page_context_max_bytes
const DEFAULT_PAGE_CONTEXT_MAX_BYTES_FALLBACK = 8192;
const PAGE_CONTEXT_SOFT_RESERVE_BYTES = 1024;

function getPageContextHardLimitBytes(): number {
  return (
    publicConfigStore.platformConfig?.runtimeLimits?.pageContextMaxBytes ||
    publicConfigStore.tenantConfig?.runtimeLimits?.pageContextMaxBytes ||
    DEFAULT_PAGE_CONTEXT_MAX_BYTES_FALLBACK
  );
}

function getPageContextSoftLimitBytes(): number {
  return Math.max(
    getPageContextHardLimitBytes() - PAGE_CONTEXT_SOFT_RESERVE_BYTES,
    1024,
  );
}

function getSerializedPageDataBytes(pageData: Record<string, unknown>): number {
  return new TextEncoder().encode(JSON.stringify(pageData)).length;
}

function truncateTextByBytes(text: string, maxBytes: number): string {
  const encoder = new TextEncoder();
  const encoded = encoder.encode(text);
  if (encoded.length <= maxBytes) return text;
  return new TextDecoder().decode(encoded.slice(0, maxBytes));
}

function truncateFormFields(
  pageData: Record<string, unknown>,
): Record<string, unknown> {
  const ff = pageData.form_fields;
  if (!ff || typeof ff !== 'object') return pageData;
  const entries = Object.entries(ff as Record<string, unknown>);
  if (entries.length <= MAX_FORM_FIELDS) return pageData;
  const truncated = Object.fromEntries(entries.slice(0, MAX_FORM_FIELDS));
  (truncated as Record<string, unknown>)._truncated =
    `Showing ${MAX_FORM_FIELDS} of ${entries.length} fields`;
  return { ...pageData, form_fields: truncated };
}

function compactAvailableOperations(
  operations: unknown[],
  options: {
    includeDescriptions: boolean;
    includeParams: boolean;
    maxOps: number;
    maxParamsPerOp: number;
  },
): unknown[] {
  return operations.slice(0, options.maxOps).map((operation) => {
    if (!operation || typeof operation !== 'object') {
      return operation;
    }

    const source = operation as Record<string, unknown>;
    const compact: Record<string, unknown> = {
      name: source.name,
      label: source.label,
      readonly: source.readonly,
    };

    if (options.includeDescriptions && typeof source.description === 'string') {
      compact.description = source.description;
    }

    if (
      options.includeParams &&
      source.params &&
      typeof source.params === 'object'
    ) {
      const paramEntries = Object.entries(
        source.params as Record<string, unknown>,
      ).slice(0, options.maxParamsPerOp);
      compact.params = Object.fromEntries(
        paramEntries.map(([paramName, rawSchema]) => {
          if (!rawSchema || typeof rawSchema !== 'object') {
            return [paramName, rawSchema];
          }
          const schema = rawSchema as Record<string, unknown>;
          return [
            paramName,
            {
              type: schema.type,
              required: schema.required,
              ...(Array.isArray(schema.enum) && schema.enum.length > 0
                ? { enum: schema.enum.slice(0, 5) }
                : {}),
            },
          ];
        }),
      );
    }

    return compact;
  });
}

function compactFormFieldsForBudget(
  formFields: Record<string, unknown>,
  options: {
    includeConstraints: boolean;
    includeOptions: boolean;
    maxFields: number;
  },
): Record<string, unknown> {
  const entries = Object.entries(formFields).filter(
    ([fieldName]) => fieldName !== '_truncated',
  );
  const compact = Object.fromEntries(
    entries.slice(0, options.maxFields).map(([fieldName, rawDescriptor]) => {
      if (!rawDescriptor || typeof rawDescriptor !== 'object') {
        return [fieldName, rawDescriptor];
      }
      const descriptor = rawDescriptor as Record<string, unknown>;
      const nextDescriptor: Record<string, unknown> = {
        type: descriptor.type,
        component: descriptor.component,
        description: descriptor.description,
      };
      if (descriptor.required) {
        nextDescriptor.required = descriptor.required;
      }
      if (descriptor.optionsSource) {
        nextDescriptor.optionsSource = descriptor.optionsSource;
      }
      if (options.includeConstraints && descriptor.constraints) {
        nextDescriptor.constraints = descriptor.constraints;
      }
      if (
        options.includeOptions &&
        Array.isArray(descriptor.options) &&
        descriptor.options.length > 0
      ) {
        nextDescriptor.options = descriptor.options.slice(0, 4);
      }
      return [fieldName, nextDescriptor];
    }),
  );
  if (entries.length > options.maxFields) {
    compact._truncated = `Showing ${options.maxFields} of ${entries.length} fields`;
  }
  return compact;
}

/**
 * Ensure total page_data stays under the runtime soft budget.
 * 确保 page_data 总大小不超过运行时软预算。
 * Prefer trimming list rows and operation verbosity before dropping form_fields.
 * 优先裁剪列表样本和操作描述，最后才丢弃 form_fields。
 */
function guardPageDataSize(
  pageData: Record<string, unknown>,
): Record<string, unknown> {
  const maxPageDataBytes = getPageContextSoftLimitBytes();
  let data = { ...pageData };
  let size = getSerializedPageDataBytes(data);
  if (size <= maxPageDataBytes) return data;

  // Step 1: reduce list_summary sample_rows / 步骤 1：精简 list_summary sample_rows
  const ls = data.list_summary as Record<string, unknown> | undefined;
  if (
    ls?.sample_rows &&
    Array.isArray(ls.sample_rows) &&
    ls.sample_rows.length > 0
  ) {
    data = {
      ...data,
      list_summary: {
        ...ls,
        sample_rows: (ls.sample_rows as unknown[]).slice(0, 2),
      },
    };
    size = getSerializedPageDataBytes(data);
    if (size <= maxPageDataBytes) return data;
    data = { ...data, list_summary: { ...ls, sample_rows: [] } };
    size = getSerializedPageDataBytes(data);
    if (size <= maxPageDataBytes) return data;
  }

  // Step 2: slim available_operations in stages / 步骤 2：分阶段精简 available_operations
  const aops = data.available_operations;
  if (Array.isArray(aops) && aops.length > 0) {
    const operationVariants = [
      compactAvailableOperations(aops, {
        includeDescriptions: true,
        includeParams: true,
        maxOps: 12,
        maxParamsPerOp: 4,
      }),
      compactAvailableOperations(aops, {
        includeDescriptions: true,
        includeParams: false,
        maxOps: 10,
        maxParamsPerOp: 0,
      }),
      compactAvailableOperations(aops, {
        includeDescriptions: false,
        includeParams: false,
        maxOps: 8,
        maxParamsPerOp: 0,
      }),
    ];

    for (const compactOperations of operationVariants) {
      data = {
        ...data,
        available_operations: compactOperations,
      };
      size = getSerializedPageDataBytes(data);
      if (size <= maxPageDataBytes) return data;
    }

    const { available_operations: _ao, ...rest } = data;
    data = rest;
    size = getSerializedPageDataBytes(data);
    if (size <= maxPageDataBytes) return data;
  }

  // Step 3: truncate document_body_text (NovusDoc / DocumentEditor) / 步骤 3：截断 document_body_text
  const body = data.document_body_text;
  if (typeof body === 'string' && body.length > 0) {
    for (const maxBodyBytes of [2400, 1600, 800]) {
      data = {
        ...data,
        document_body_text: truncateTextByBytes(body, maxBodyBytes),
      };
      size = getSerializedPageDataBytes(data);
      if (size <= maxPageDataBytes) return data;
    }
    data = { ...data, document_body_text: truncateTextByBytes(body, 400) };
    size = getSerializedPageDataBytes(data);
    if (size <= maxPageDataBytes) return data;
  }

  // Step 4: compact form_fields progressively, drop only as last resort / 步骤 4：逐步压缩 form_fields，最后才移除
  const formFields = data.form_fields;
  if (formFields && typeof formFields === 'object') {
    const compactVariants = [
      compactFormFieldsForBudget(formFields as Record<string, unknown>, {
        includeConstraints: true,
        includeOptions: true,
        maxFields: 16,
      }),
      compactFormFieldsForBudget(formFields as Record<string, unknown>, {
        includeConstraints: true,
        includeOptions: false,
        maxFields: 12,
      }),
      compactFormFieldsForBudget(formFields as Record<string, unknown>, {
        includeConstraints: false,
        includeOptions: false,
        maxFields: 8,
      }),
      compactFormFieldsForBudget(formFields as Record<string, unknown>, {
        includeConstraints: false,
        includeOptions: false,
        maxFields: 4,
      }),
    ];

    for (const compactFields of compactVariants) {
      data = { ...data, form_fields: compactFields };
      size = getSerializedPageDataBytes(data);
      if (size <= maxPageDataBytes) return data;
    }

    const { form_fields: _ff, ...rest } = data;
    data = rest;
  }

  return data;
}

/**
 * Enrich page_context with available_operations and visual_state
 * 为 page_context 注入 available_operations 与 visual_state，
 * so LLM can discover operations and current visual state (modals, drawers, scroll).
 * 并执行 form_fields 条数限制与 page_data 总大小限制。
 */
function enrichPageContextWithOperations(
  ctx: ReturnType<typeof resolvePageContext>,
  ops: readonly PageOperation[] = [],
): ReturnType<typeof resolvePageContext> {
  if (!ctx) return ctx;
  if (
    normalizedPageMode.value === 'disabled' ||
    shouldDisablePageContext(props.disabledCapabilities)
  ) {
    return null;
  }

  // When form is open, prefer live fieldDescriptors from formStateTracker / 表单打开时优先使用 formStateTracker 的实时 fieldDescriptors
  // (refreshed each time the drawer opens) over the static version registered
  // at page mount. This handles dynamic schemas (conditional fields, permissions) / 页面挂载时；处理动态 schema（条件字段、权限）
  // 表单打开时，优先使用 formStateTracker 的实时字段描述（每次 drawer 打开时刷新），
  // 而非页面挂载时注册的静态版本，以支持动态 schema（条件字段、权限变化）。
  let liveFormFields = ctx.page_data?.form_fields;
  if (formStateTracker.isOpenWithFallback(ctx.page_key)) {
    const descriptors = formStateTracker.getFieldDescriptors(ctx.page_key);
    if (descriptors && Object.keys(descriptors).length > 0) {
      liveFormFields = descriptors;
    }
  }

  const {
    available_operations: _availableOperations,
    visual_state: _visualState,
    ...basePageData
  } = ctx.page_data ?? {};

  let pageData: Record<string, unknown> = {
    ...basePageData,
    ...(liveFormFields ? { form_fields: liveFormFields } : {}),
    visual_state: collectVisualState(),
    ...(canExposePageOperations(normalizedPageMode.value) && ops.length > 0
      ? {
          available_operations: ops.map((op) => ({
            name: op.name,
            label: op.label,
            description: op.description,
            readonly: op.readonly,
            ...(op.params ? { params: op.params } : {}),
          })),
        }
      : {}),
  };
  pageData = truncateFormFields(pageData);
  pageData = guardPageDataSize(pageData);
  return { ...ctx, page_data: pageData };
}

async function handleSendMessage() {
  const text = inputMessage.value.trim();
  if (!text && pendingAttachments.value.length === 0) return;

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

  const mentionTarget = mentionedAgent.value;
  if (mentionTarget) {
    const mentionRequired = getAgentInputVariables(mentionTarget).filter(
      (variable) => variable.required,
    );
    if (mentionRequired.length > 0) {
      ensureAgentVarsLoaded(mentionTarget.id);
      const mentionVars = allAgentsVariables.value[mentionTarget.id] ?? {};
      const mentionMissing = mentionRequired.filter(
        (variable) => !mentionVars[variable.name]?.trim(),
      );
      if (mentionMissing.length > 0) {
        pendingSendContext.value = {
          agentId: mentionTarget.id,
          consumeMention: true,
          pageContext,
          routeSource: 'mention',
        };
        openVarsModal(
          getAgentInputVariables(mentionTarget),
          mentionTarget.id,
          mentionTarget.name,
        );
        return;
      }
    }
    showRouteNotice(
      $t('common.aiPanel.routedTo', { agent: mentionTarget.name }),
    );
    clearMentionedAgent();
    sendMessage({
      agentId: mentionTarget.id,
      pageContext,
      routeSource: 'mention',
    });
    return;
  }

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
        pendingSendContext.value = { agentId: pinnedId, pageContext };
        openVarsModal(pinnedInputVariables, pinnedId, pinnedAgent!.name);
        return;
      }
    }
    sendMessage({ agentId: pinnedId, pageContext });
    return;
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
    sendMessage({ agentId: explicitAgentId, pageContext });
    return;
  }

  if (activeConversationId.value && selectedAgentId.value && !forceReroute) {
    sendMessage({ pageContext });
    return;
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

    // On @mention routing, replace input with cleaned message (remove @name prefix) / @mention 路由时，用清理后的消息替换输入（去除 @name 前缀）
    if (result.routedBy === 'mention' && result.cleanedMessage !== undefined) {
      inputMessage.value = result.cleanedMessage;
    }

    // Show route notice (pinned and default don't show) / 显示路由提示（pinned 和 default 不显示）
    if (result.routedBy === 'router' || result.routedBy === 'mention') {
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
        pendingSendContext.value = {
          agentId: result.agentId,
          pageContext: routedPageContext,
          ...(result.routedBy === 'mention' ? { routeSource: 'mention' } : {}),
        };
        openVarsModal(routedInputVariables, result.agentId, routedAgent!.name);
        return;
      }
    }

    // Send message (using routed agent ID) / 发送消息（使用路由后的智能体 ID）
    sendMessage({
      agentId: result.agentId,
      pageContext: routedPageContext,
      ...(result.routedBy === 'mention' ? { routeSource: 'mention' } : {}),
    });
  } catch (error: unknown) {
    if (selectedAgentId.value && !hasCapabilitySensitiveAttachments) {
      message.warning($t('common.globalAiChat.routeFailedFallback'));
      sendMessage({ pageContext });
      return;
    }

    const baseMsg = getErrorMessage(error, 'common.http.internalServerError');
    message.error(`${baseMsg} ${$t('common.globalAiChat.routeFailedHint')}`);
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

const showHistory = ref(false);
const conversationSearch = ref('');

const filteredConversations = computed(() => {
  const keyword = conversationSearch.value.trim().toLowerCase();
  if (!keyword) return conversations.value;
  return conversations.value.filter((c) =>
    (c.title || '').toLowerCase().includes(keyword),
  );
});

function toggleHistory() {
  showHistory.value = !showHistory.value;
  if (!showHistory.value) {
    conversationSearch.value = '';
  }
}

interface ConversationGroup {
  label: string;
  items: typeof conversations.value;
}

const groupedConversations = computed<ConversationGroup[]>(() => {
  const list = filteredConversations.value;
  if (list.length === 0) return [];

  const now = new Date();
  const todayStart = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  ).getTime();
  const yesterdayStart = todayStart - 86_400_000;

  const today: typeof list = [];
  const yesterday: typeof list = [];
  const earlier: typeof list = [];

  for (const c of list) {
    const t = new Date(c.created_at).getTime();
    if (t >= todayStart) today.push(c);
    else if (t >= yesterdayStart) yesterday.push(c);
    else earlier.push(c);
  }

  const groups: ConversationGroup[] = [];
  if (today.length > 0)
    groups.push({ label: $t('common.globalAiChat.today'), items: today });
  if (yesterday.length > 0)
    groups.push({
      label: $t('common.globalAiChat.yesterday'),
      items: yesterday,
    });
  if (earlier.length > 0)
    groups.push({ label: $t('common.globalAiChat.earlier'), items: earlier });
  return groups;
});

function onSelectConversation(convId: number) {
  clearRoutingIntent();
  aiPanelStore.clearResolvedPageOps?.();
  loadConversationMessages(convId);
  showHistory.value = false;
  showMemoryPanel.value = false;
  conversationSearch.value = '';
}

function onDeleteConversation(convId: number) {
  Modal.confirm({
    title: $t('common.globalAiChat.confirmDelete'),
    onOk: () => deleteConversation(convId),
  });
}

const editingConversationId = ref<null | number>(null);
const editingTitle = ref('');

function startEditTitle(conv: { id: number; title?: null | string }) {
  editingConversationId.value = conv.id;
  editingTitle.value = conv.title || '';
}

function commitEditTitle() {
  const id = editingConversationId.value;
  if (id === null) return;
  const title = editingTitle.value.trim().slice(0, 200);
  editingConversationId.value = null;
  editingTitle.value = '';
  updateConversationTitle(id, title);
}

function cancelEditTitle() {
  editingConversationId.value = null;
  editingTitle.value = '';
}

function onStartNewChat() {
  clearRoutingIntent();
  aiPanelStore.clearResolvedPageOps?.();
  startNewConversation();
  showHistory.value = false;
  showMemoryPanel.value = false;
}

function onStartNewChatWithAgent(agentId: number) {
  const targetAgent = agents.value.find((agent) => agent.id === agentId);
  if (!targetAgent) return;

  if (aiPanelStore.pinnedAgentId && aiPanelStore.pinnedAgentId !== agentId) {
    aiPanelStore.unpinAgent();
  }

  selectedAgentId.value = agentId;
  manualNewConversationAgentId.value = agentId;
  forceRerouteNextTurn.value = false;
  aiPanelStore.clearResolvedPageOps?.();
  startNewConversation(true);
  showHistory.value = false;
  showMemoryPanel.value = false;
  conversationSearch.value = '';
  showRouteNotice(
    $t('common.globalAiChat.newConversationWithAgent', {
      agent: targetAgent.name,
    }),
  );
}

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

// ============ Memory / 会话记忆 ============

const showMemoryPanel = ref(false);

async function onToggleMemory() {
  if (showMemoryPanel.value) {
    showMemoryPanel.value = false;
    return;
  }
  await fetchConversationMemory();
  showMemoryPanel.value = true;
}

function onClearMemory() {
  Modal.confirm({
    title: $t('common.globalAiChat.clearMemoryConfirm'),
    onOk: async () => {
      const ok = await clearConversationMemory();
      if (ok) {
        message.success($t('common.globalAiChat.clearMemorySuccess'));
        showMemoryPanel.value = false;
      } else {
        message.error($t('common.globalAiChat.clearMemoryFailed'));
      }
    },
  });
}

const showHeaderVarsButton = computed(() => {
  return (
    agentsWithVarsInConversation.value.length > 0 ||
    getAgentInputVariables(selectedAgent.value).length > 0
  );
});

const hasHeaderVariableValues = computed(() =>
  agentsWithVarsInConversation.value.some(
    (agent) => Object.keys(allAgentsVariables.value[agent.id] ?? {}).length > 0,
  ),
);

const headerConversationSummary = computed(() => {
  if (activeConversationId.value && currentConversationAgentName.value) {
    return $t('common.globalAiChat.currentConversationAgent', {
      agent: currentConversationAgentName.value,
    });
  }
  return selectedAgent.value?.name ?? '';
});

const headerMoreMenuItems = computed(() => {
  const items: ItemType[] = [];

  if (isPinned.value) {
    items.push({
      key: 'unpin-agent',
      label: $t('common.aiPanel.unpinAgent'),
      onClick: () => {
        unpinAgent();
      },
    });
  }

  if (switchAgentMenuItems.value.length > 1) {
    items.push({
      children: switchAgentMenuItems.value,
      key: 'switch-agent',
      label: $t('common.globalAiChat.switchAgentNewConversation'),
    });
  }

  if (activeConversationId.value) {
    items.push({
      key: 'memory',
      label: $t('common.aiPanel.memory'),
      onClick: () => {
        void onToggleMemory();
      },
    });
  }

  return items;
});

const showHeaderMoreMenu = computed(() => headerMoreMenuItems.value.length > 0);

const headerMoreHasAttention = computed(
  () =>
    isPinned.value ||
    forceRerouteNextTurn.value ||
    !!(
      activeConversationId.value &&
      (showMemoryPanel.value || lastMemoryUpdated.value)
    ),
);

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
  return mentionedAgent.value ?? selectedAgent.value ?? null;
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

// ============ Copy / 复制消息 ============

async function onCopyMessage(content: string) {
  await copyMessage(content);
}

// ============ Panel width / 面板宽度 ============

const STORAGE_KEY = 'ai-slide-panel-width';
const MIN_WIDTH = 400;
const MAX_WIDTH = 800;
const DEFAULT_WIDTH = 460;

const panelWidth = ref(DEFAULT_WIDTH);
const dragging = ref(false);

const isFullMode = computed(() => aiPanelStore.mode === 'full');

const effectivePanelStyle = computed(() => ({
  width: isFullMode.value ? '100vw' : `${panelWidth.value}px`,
}));

function loadSavedWidth() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const w = Number.parseInt(saved, 10);
      if (w >= MIN_WIDTH && w <= MAX_WIDTH) panelWidth.value = w;
    }
  } catch {
    /* ignore / 忽略 */
  }
  aiPanelStore.panelWidth = panelWidth.value;
}

function saveWidth() {
  try {
    localStorage.setItem(STORAGE_KEY, String(panelWidth.value));
  } catch {
    /* ignore / 忽略 */
  }
}

function onDragStart(e: MouseEvent) {
  e.preventDefault();
  dragging.value = true;
  const startX = e.clientX;
  const startWidth = panelWidth.value;

  function onMouseMove(ev: MouseEvent) {
    const diff = startX - ev.clientX;
    panelWidth.value = Math.min(
      MAX_WIDTH,
      Math.max(MIN_WIDTH, startWidth + diff),
    );
    aiPanelStore.panelWidth = panelWidth.value;
  }

  function onMouseUp() {
    dragging.value = false;
    saveWidth();
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

// ============ External message handling / 外部消息处理 ============

const hasQueuedConversationRestore = computed(
  () =>
    typeof props.pendingConversationId === 'number' &&
    Number.isFinite(props.pendingConversationId),
);

const hasQueuedExternalContext = computed(() => {
  const queuedMessage = props.pendingMessage?.trim();
  return hasQueuedConversationRestore.value || Boolean(queuedMessage);
});

const applyingExternalContext = ref(false);

async function applyExternalContext(): Promise<void> {
  if (!aiPanelStore.visible || applyingExternalContext.value) {
    return;
  }

  const queuedConversationId =
    typeof props.pendingConversationId === 'number' &&
    Number.isFinite(props.pendingConversationId)
      ? props.pendingConversationId
      : null;
  const queuedMessage = props.pendingMessage?.trim() || '';

  if (!queuedConversationId && !queuedMessage) {
    return;
  }

  applyingExternalContext.value = true;
  try {
    if (queuedConversationId) {
      showHistory.value = false;
      showMemoryPanel.value = false;
      if (activeConversationId.value !== queuedConversationId) {
        await loadConversationMessages(queuedConversationId);
      }
      emit('conversationRestored');
    }

    if (queuedMessage) {
      inputMessage.value = queuedMessage;
      await handleSendMessage();
      emit('messageSent');
    }
  } finally {
    applyingExternalContext.value = false;
  }
}

watch(
  [() => props.pendingConversationId, () => props.pendingMessage, () => aiPanelStore.visible],
  () => {
    void applyExternalContext();
  },
);

// ============ Load data on panel open / 面板打开时加载数据 ============

watch(
  () => aiPanelStore.visible,
  async (visible) => {
    if (visible) {
      aiPanelStore.clearResolvedPageOps?.();
      const pendingId = aiPanelStore.consumePendingAgentId();
      forceRerouteNextTurn.value = false;
      const shouldResumeExistingConversation =
        !pendingId &&
        !hasQueuedExternalContext.value &&
        (activeConversationId.value !== null || chatMessages.value.length > 0);

      if (
        shouldResumeExistingConversation ||
        hasQueuedConversationRestore.value
      ) {
        manualNewConversationAgentId.value = null;
      } else {
        manualNewConversationAgentId.value = pendingId ?? null;
        // Only clear state when this open action is explicitly starting a
        // fresh routed conversation; queued conversation restore will own
        // the state transition to avoid clearing restored history in a race.
        // 仅在显式开启全新路由会话时清空状态；恢复排队会话由恢复逻辑接管，避免竞态下把历史清空
        startNewConversation(true);
      }
      showHistory.value = false;
      showMemoryPanel.value = false;
      await loadAgents(pendingId ?? selectedAgentId.value ?? undefined);
      await loadConversations();
      await applyExternalContext();
    }
  },
);

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
  if (aiPanelStore.visible) {
    aiPanelStore.clearResolvedPageOps?.();
    void (async () => {
      await loadAgents();
      await loadConversations();
      await applyExternalContext();
    })();
  }
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

        <!-- Single-agent Input Variables Modal (triggered on missing vars) -->
        <Modal
          v-model:open="varsModalVisible"
          :title="
            $t('user.aiChat.varsModal.title', {
              name: varsModalAgent?.name ?? '',
            })
          "
          :mask-closable="false"
          :ok-text="$t('user.aiChat.varsModal.confirm')"
          :cancel-text="$t('common.cancel')"
          @ok="onVarsConfirm"
          @cancel="onVarsCancel"
        >
          <p class="mb-4 text-sm text-muted-foreground">
            {{ $t('user.aiChat.varsModal.desc') }}
          </p>
          <div v-if="varsModalAgent" class="space-y-4">
            <div
              v-for="v in varsModalAgent.vars"
              :key="v.name"
              class="flex flex-col gap-1"
            >
              <label class="text-sm font-medium">
                {{ v.label || v.name }}
                <span v-if="v.required" class="ml-0.5 text-destructive">*</span>
              </label>
              <Input
                v-model:value="varsFormValues[v.name]"
                :placeholder="v.default || v.label || v.name"
                allow-clear
              />
            </div>
            <label
              class="flex cursor-pointer items-center gap-2 pt-1 text-xs text-muted-foreground"
            >
              <input
                v-model="varsPersist"
                type="checkbox"
                class="size-3.5 cursor-pointer rounded accent-primary"
              />
              <span class="font-medium text-foreground/70">{{
                $t('user.aiChat.varsModal.persistLabel')
              }}</span>
              <span class="text-[11px]">{{
                $t('user.aiChat.varsModal.persistHint')
              }}</span>
            </label>
          </div>
        </Modal>

        <!-- Multi-agent vars editor (edit button) -->
        <Modal
          v-model:open="multiVarsModalVisible"
          :title="$t('user.aiChat.varsModal.editVars')"
          :ok-text="$t('common.save')"
          :cancel-text="$t('common.cancel')"
          @ok="onMultiVarsConfirm"
          @cancel="multiVarsModalVisible = false"
        >
          <div class="space-y-6">
            <div v-for="a in agentsWithVarsInConversation" :key="a.id">
              <div class="mb-3 flex items-center gap-2">
                <IconifyIcon icon="lucide:bot" class="size-4 text-primary" />
                <span class="text-sm font-semibold">{{ a.name }}</span>
              </div>
              <div class="space-y-3 pl-6">
                <div
                  v-for="v in a.input_variables"
                  :key="v.name"
                  class="flex flex-col gap-1"
                >
                  <label class="text-sm font-medium">
                    {{ v.label || v.name }}
                    <span v-if="v.required" class="ml-0.5 text-destructive"
                      >*</span
                    >
                  </label>
                  <Input
                    v-if="multiVarsFormValues[a.id]"
                    v-model:value="multiVarsFormValues[a.id]![v.name]"
                    :placeholder="v.default || v.label || v.name"
                    allow-clear
                  />
                </div>
              </div>
            </div>
            <label
              class="flex cursor-pointer items-center gap-2 border-t border-border/40 pt-3 text-xs text-muted-foreground"
            >
              <input
                v-model="multiVarsPersist"
                type="checkbox"
                class="size-3.5 cursor-pointer rounded accent-primary"
              />
              <span class="font-medium text-foreground/70">{{
                $t('user.aiChat.varsModal.persistLabel')
              }}</span>
              <span class="text-[11px]">{{
                $t('user.aiChat.varsModal.persistHint')
              }}</span>
            </label>
          </div>
        </Modal>

        <!-- Header -->
        <div
          class="flex shrink-0 flex-col gap-2 border-b border-border/40 px-3 py-2"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="flex min-w-0 flex-1 items-start gap-2.5">
              <div
                class="flex size-8 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"
              >
                <IconifyIcon icon="lucide:sparkles" class="size-4 shrink-0" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-1.5">
                  <span class="truncate text-sm font-semibold text-foreground">
                    {{ panelTitle }}
                  </span>
                  <span
                    v-if="routing"
                    class="routing-badge relative inline-flex items-center gap-1 overflow-hidden rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary"
                  >
                    <span
                      class="routing-dot size-1.5 rounded-full bg-primary"
                    ></span>
                    {{ $t('common.globalAiChat.routingAgent') }}
                    <span class="routing-shimmer absolute inset-0"></span>
                  </span>
                </div>
                <div
                  v-if="headerConversationSummary"
                  class="mt-0.5 truncate text-[11px] text-muted-foreground"
                >
                  {{ headerConversationSummary }}
                </div>
              </div>
            </div>

            <div
              class="flex shrink-0 items-center gap-0.5 rounded-xl border border-border/40 bg-background/80 px-1 py-1"
            >
              <Tooltip
                :title="
                  aiPanelStore.docked
                    ? $t('common.aiPanel.undock')
                    : $t('common.aiPanel.dock')
                "
              >
                <button
                  class="flex size-7 items-center justify-center rounded-lg transition-colors hover:bg-muted"
                  :class="
                    aiPanelStore.docked
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  "
                  @click="handleToggleDock"
                >
                  <IconifyIcon
                    :icon="
                      aiPanelStore.docked ? 'lucide:lock' : 'lucide:lock-open'
                    "
                    class="size-3.5"
                  />
                </button>
              </Tooltip>
              <Tooltip
                :title="
                  aiPanelStore.mode === 'full'
                    ? $t('common.aiPanel.exitFullscreen')
                    : $t('common.aiPanel.fullscreen')
                "
              >
                <button
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  @click="handleToggleMode"
                >
                  <IconifyIcon
                    :icon="
                      aiPanelStore.mode === 'full'
                        ? 'lucide:minimize-2'
                        : 'lucide:maximize-2'
                    "
                    class="size-3.5"
                  />
                </button>
              </Tooltip>
              <Tooltip :title="$t('common.aiPanel.minimize')">
                <button
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  @click="handleMinimize"
                >
                  <IconifyIcon icon="lucide:minus" class="size-3.5" />
                </button>
              </Tooltip>
              <Tooltip :title="$t('common.aiPanel.close')">
                <button
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-destructive"
                  @click="handleClose"
                >
                  <IconifyIcon icon="lucide:x" class="size-3.5" />
                </button>
              </Tooltip>
            </div>
          </div>

          <div class="flex flex-wrap items-start justify-between gap-2">
            <div
              data-testid="ai-panel-header-status"
              class="flex min-w-0 flex-1 flex-wrap items-center gap-1"
            >
              <span
                v-if="forceRerouteNextTurn"
                class="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-700"
              >
                <IconifyIcon icon="lucide:compass" class="size-2.5" />
                {{ $t('common.globalAiChat.rerouteArmed') }}
              </span>
            </div>

            <div
              v-if="hasPageAI"
              data-testid="ai-panel-page-ai-card"
              class="relative flex h-9 min-w-0 flex-[1_1_260px] items-center overflow-hidden rounded-xl border border-primary/15 bg-gradient-to-r from-primary/[0.08] via-background to-primary/[0.02] px-2 py-1 transition-colors"
              :class="
                hasExpandablePageAIDetails
                  ? 'cursor-pointer hover:border-primary/25 hover:bg-primary/[0.06]'
                  : ''
              "
              :aria-expanded="
                hasExpandablePageAIDetails ? pageAIDetailsExpanded : undefined
              "
              :aria-label="
                hasExpandablePageAIDetails ? pageAIRailTooltip : undefined
              "
              :role="hasExpandablePageAIDetails ? 'button' : undefined"
              :tabindex="hasExpandablePageAIDetails ? 0 : undefined"
              @click="
                hasExpandablePageAIDetails ? togglePageAIDetails() : undefined
              "
              @keydown.enter.prevent="
                hasExpandablePageAIDetails ? togglePageAIDetails() : undefined
              "
              @keydown.space.prevent="
                hasExpandablePageAIDetails ? togglePageAIDetails() : undefined
              "
            >
              <div
                class="flex min-w-0 flex-1 items-center justify-between gap-2"
              >
                <Tooltip :title="pageAIRailTooltip">
                  <div class="flex min-w-0 flex-1 items-center gap-2">
                    <div
                      class="bg-primary/12 flex size-6 shrink-0 items-center justify-center rounded-lg text-primary"
                    >
                      <IconifyIcon icon="lucide:cpu" class="size-3" />
                    </div>
                    <span
                      class="shrink-0 text-[10px] font-semibold uppercase tracking-[0.14em] text-primary/75"
                    >
                      {{ $t('common.aiPanel.pageAiSupported') }}
                    </span>
                    <span
                      v-if="currentPageOperations.length > 0"
                      class="inline-flex shrink-0 items-center rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary"
                    >
                      {{ currentPageOperations.length }}
                    </span>
                  </div>
                </Tooltip>
                <Tooltip
                  v-if="hasExpandablePageAIDetails"
                  :title="
                    pageAIDetailsExpanded
                      ? $t('common.aiPanel.pageAiCollapse')
                      : $t('common.aiPanel.pageAiExpand')
                  "
                >
                  <button
                    data-testid="ai-panel-page-ai-toggle"
                    class="inline-flex size-7 shrink-0 items-center justify-center rounded-lg border border-border/45 bg-background/85 text-foreground transition-colors hover:border-primary/20 hover:bg-primary/[0.05]"
                    :aria-expanded="pageAIDetailsExpanded"
                    :aria-label="
                      pageAIDetailsExpanded
                        ? $t('common.aiPanel.pageAiCollapse')
                        : $t('common.aiPanel.pageAiExpand')
                    "
                    type="button"
                    @click.stop="togglePageAIDetails"
                  >
                    <IconifyIcon
                      icon="lucide:chevron-down"
                      class="size-3 transition-transform duration-200"
                      :class="pageAIDetailsExpanded ? 'rotate-180' : ''"
                    />
                  </button>
                </Tooltip>
              </div>
            </div>

            <div
              data-testid="ai-panel-header-actions"
              class="flex shrink-0 items-center gap-0.5 rounded-xl border border-border/40 bg-muted/15 px-1 py-1"
            >
              <Tooltip
                v-if="showHeaderVarsButton"
                :title="$t('user.aiChat.varsModal.editVars')"
              >
                <button
                  class="hover:bg-primary/8 relative flex h-7 items-center gap-1 rounded-lg px-1.5 text-xs font-medium text-primary transition-colors"
                  @click="
                    agentsWithVarsInConversation.length > 0
                      ? openMultiVarsEditor()
                      : openVarsModal(
                          getAgentInputVariables(selectedAgent),
                          selectedAgent!.id,
                          selectedAgent!.name,
                        )
                  "
                >
                  <IconifyIcon
                    icon="lucide:sliders-horizontal"
                    class="size-3.5"
                  />
                  <span
                    v-if="hasHeaderVariableValues"
                    class="absolute right-1 top-1 size-1.5 rounded-full bg-green-500"
                  ></span>
                </button>
              </Tooltip>
              <Tooltip
                v-if="activeConversationId && !isPinned"
                :title="$t('common.globalAiChat.rerouteThisTurn')"
              >
                <button
                  class="flex size-7 items-center justify-center rounded-lg transition-colors disabled:opacity-40"
                  :class="
                    forceRerouteNextTurn
                      ? 'bg-amber-500/12 text-amber-700'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  "
                  :aria-label="$t('common.globalAiChat.rerouteThisTurn')"
                  :disabled="!canForceReroute"
                  @click="onToggleForceReroute"
                >
                  <IconifyIcon icon="lucide:compass" class="size-3.5" />
                </button>
              </Tooltip>
              <Tooltip :title="$t('common.aiPanel.newChat')">
                <button
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  @click="onStartNewChat"
                >
                  <IconifyIcon icon="lucide:plus" class="size-3.5" />
                </button>
              </Tooltip>
              <Tooltip :title="$t('common.aiPanel.history')">
                <button
                  class="flex size-7 items-center justify-center rounded-lg transition-colors hover:bg-muted"
                  :class="
                    showHistory
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  "
                  @click="toggleHistory"
                >
                  <IconifyIcon icon="lucide:history" class="size-3.5" />
                </button>
              </Tooltip>
              <Dropdown
                v-if="showHeaderMoreMenu"
                :trigger="['click']"
                placement="bottomRight"
              >
                <Tooltip :title="$t('common.aiPanel.moreActions')">
                  <button
                    class="relative flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    :aria-label="$t('common.aiPanel.moreActions')"
                    type="button"
                  >
                    <IconifyIcon icon="lucide:ellipsis" class="size-3.5" />
                    <span
                      v-if="headerMoreHasAttention"
                      class="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-primary"
                    ></span>
                  </button>
                </Tooltip>
                <template #overlay>
                  <Menu :items="headerMoreMenuItems" />
                </template>
              </Dropdown>
            </div>

            <Transition name="page-ai-details">
              <div
                v-if="pageAIDetailsExpanded && hasExpandablePageAIDetails"
                data-testid="ai-panel-page-ai-details"
                class="order-last basis-full rounded-xl border border-primary/15 bg-background/85 px-2.5 py-2"
              >
                <div class="flex flex-col gap-2">
                  <div class="flex min-w-0 items-start justify-between gap-2">
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center gap-1.5">
                        <span
                          class="text-[10px] font-semibold uppercase tracking-[0.14em] text-primary/75"
                        >
                          {{ $t('common.aiPanel.pageAiSupported') }}
                        </span>
                        <span
                          v-if="currentPageOperations.length > 0"
                          class="inline-flex items-center rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary"
                        >
                          {{ currentPageOperations.length }}
                        </span>
                      </div>
                      <Tooltip :title="resolvedPageAITitle">
                        <div
                          class="mt-1 truncate text-[11px] font-medium text-foreground"
                          :title="resolvedPageAITitle"
                        >
                          {{ resolvedPageAITitle }}
                        </div>
                      </Tooltip>
                      <Tooltip :title="pageAISummary">
                        <div
                          class="mt-0.5 truncate text-[10px] leading-4 text-muted-foreground"
                          :title="pageAISummary"
                        >
                          {{ pageAISummary }}
                        </div>
                      </Tooltip>
                    </div>
                  </div>

                  <div
                    v-if="pageAIStatBadges.length > 0"
                    class="flex flex-wrap gap-1.5"
                  >
                    <span
                      v-for="badge in pageAIStatBadges"
                      :key="badge.key"
                      class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
                      :class="badge.className"
                    >
                      {{ badge.label }}
                    </span>
                  </div>

                  <div
                    v-if="pageAIVisibleOperations.length > 0"
                    class="max-h-[208px] overflow-y-auto pr-1"
                  >
                    <div class="grid gap-1.5 sm:grid-cols-2">
                      <div
                        v-for="operation in pageAIVisibleOperations"
                        :key="operation.name"
                        data-testid="ai-panel-page-ai-preview-item"
                        class="bg-background/78 rounded-lg border border-border/45 px-2.5 py-2 shadow-sm shadow-black/[0.03]"
                      >
                        <div class="flex items-start justify-between gap-2">
                          <div class="min-w-0 flex-1">
                            <Tooltip :title="operation.label">
                              <div
                                class="truncate text-[11px] font-medium text-foreground"
                                :title="operation.label"
                              >
                                {{ operation.label }}
                              </div>
                            </Tooltip>
                            <Tooltip
                              :title="operation.description || operation.name"
                            >
                              <div
                                class="mt-0.5 truncate text-[10px] leading-4 text-muted-foreground"
                                :title="operation.description || operation.name"
                              >
                                {{ operation.description || operation.name }}
                              </div>
                            </Tooltip>
                          </div>
                          <span
                            class="shrink-0 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em]"
                            :class="
                              operation.readonly
                                ? 'bg-blue-500/10 text-blue-700'
                                : 'bg-amber-500/10 text-amber-700'
                            "
                          >
                            {{
                              operation.readonly
                                ? $t('common.aiPanel.pageAiReadonlyLabel')
                                : $t('common.aiPanel.pageAiWritableLabel')
                            }}
                          </span>
                        </div>
                      </div>
                      <button
                        v-if="pageAIRemainingOperationCount > 0"
                        data-testid="ai-panel-page-ai-more"
                        class="flex min-h-[64px] items-center justify-center rounded-lg border border-dashed border-primary/20 bg-primary/[0.04] px-3 py-2 text-center transition-colors hover:border-primary/35 hover:bg-primary/[0.08]"
                        type="button"
                        @click.stop="expandAllPageAIOperations"
                      >
                        <div>
                          <div
                            class="text-sm font-semibold leading-none text-primary"
                          >
                            +{{ pageAIRemainingOperationCount }}
                          </div>
                          <div
                            class="mt-1 text-[10px] font-medium uppercase tracking-[0.14em] text-primary/70"
                          >
                            {{ $t('common.aiPanel.pageAiPreviewMore') }}
                          </div>
                        </div>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <Transition name="fade">
            <div
              v-if="routeNotice"
              data-testid="ai-panel-route-banner"
              class="flex items-start gap-2 rounded-xl border border-primary/15 bg-primary/5 px-3 py-2"
            >
              <div
                class="bg-primary/12 mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-lg text-primary"
              >
                <IconifyIcon icon="lucide:route" class="size-3" />
              </div>
              <div class="min-w-0 flex-1">
                <div
                  class="truncate text-[11px] font-medium text-foreground/85"
                >
                  {{ routeNotice }}
                </div>
              </div>
            </div>
          </Transition>
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

        <!-- History panel -->
        <div v-if="showHistory" class="flex flex-1 flex-col overflow-hidden">
          <!-- Search + New Chat -->
          <div class="shrink-0 px-3 py-2">
            <div class="mb-2 flex items-center justify-between">
              <span
                class="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
              >
                {{ $t('common.globalAiChat.history') }}
              </span>
              <button
                class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-primary transition-colors hover:bg-primary/10"
                @click="onStartNewChat"
              >
                <IconifyIcon icon="lucide:plus" class="size-3" />
                {{ $t('common.aiPanel.newChat') }}
              </button>
            </div>
            <Input
              v-if="conversations.length > 3"
              v-model:value="conversationSearch"
              :placeholder="$t('common.globalAiChat.searchHistory')"
              size="small"
              allow-clear
              class="!rounded-lg"
            >
              <template #prefix>
                <IconifyIcon
                  icon="lucide:search"
                  class="size-3 text-muted-foreground"
                />
              </template>
            </Input>
          </div>

          <!-- Grouped conversation list -->
          <div class="flex-1 overflow-y-auto px-3 pb-2">
            <Spin :spinning="conversationsLoading">
              <div
                v-if="
                  groupedConversations.length === 0 && !conversationsLoading
                "
                class="py-6 text-center text-sm text-muted-foreground"
              >
                {{ $t('common.globalAiChat.noHistory') }}
              </div>
              <div
                v-for="group in groupedConversations"
                :key="group.label"
                class="mb-2"
              >
                <div
                  class="mb-1 px-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60"
                >
                  {{ group.label }}
                </div>
                <div class="space-y-0.5">
                  <div
                    v-for="conv in group.items"
                    :key="conv.id"
                    class="group relative flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 transition-all duration-150"
                    :class="
                      activeConversationId === conv.id &&
                      editingConversationId !== conv.id
                        ? 'bg-primary/8 text-foreground shadow-sm shadow-primary/5 ring-1 ring-primary/15'
                        : 'text-muted-foreground hover:bg-accent/50'
                    "
                    @click="
                      editingConversationId !== conv.id &&
                      onSelectConversation(conv.id)
                    "
                    @dblclick.stop="startEditTitle(conv)"
                  >
                    <!-- Active indicator bar -->
                    <div
                      v-if="
                        activeConversationId === conv.id &&
                        editingConversationId !== conv.id
                      "
                      class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r-full bg-primary"
                    ></div>
                    <!-- Agent avatar or icon -->
                    <div
                      v-if="editingConversationId !== conv.id"
                      class="flex size-7 shrink-0 items-center justify-center rounded-lg text-[10px] font-medium"
                      :class="
                        activeConversationId === conv.id
                          ? 'bg-primary/15 text-primary'
                          : 'bg-muted/60 text-muted-foreground'
                      "
                    >
                      <span v-if="conv.agent_name">{{
                        conv.agent_name.charAt(0).toUpperCase()
                      }}</span>
                      <IconifyIcon
                        v-else
                        icon="lucide:message-square"
                        class="size-3"
                      />
                    </div>
                    <div class="flex min-w-0 flex-1 flex-col">
                      <template v-if="editingConversationId === conv.id">
                        <Input
                          v-model:value="editingTitle"
                          size="small"
                          :placeholder="
                            $t(
                              'common.globalAiChat.conversationTitlePlaceholder',
                            )
                          "
                          class="!h-7 text-[13px]"
                          @blur="commitEditTitle"
                          @keydown.enter="commitEditTitle"
                          @keydown.esc="cancelEditTitle"
                          @click.stop
                        />
                      </template>
                      <template v-else>
                        <span
                          class="truncate text-[13px]"
                          :class="
                            activeConversationId === conv.id
                              ? 'font-medium'
                              : ''
                          "
                        >
                          {{ conv.title || `#${conv.id}` }}
                        </span>
                        <span
                          class="truncate text-[10px] text-muted-foreground/50"
                        >
                          {{ conv.agent_name || '' }}
                        </span>
                      </template>
                    </div>
                    <button
                      v-if="editingConversationId !== conv.id"
                      class="absolute right-2 flex size-5 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                      @click.stop="onDeleteConversation(conv.id)"
                    >
                      <IconifyIcon icon="lucide:trash-2" class="size-3" />
                    </button>
                  </div>
                </div>
              </div>
            </Spin>
          </div>
        </div>

        <!-- Chat area (when not showing history) -->
        <template v-if="!showHistory">
          <!-- Messages -->
          <div
            ref="messagesContainer"
            class="flex-1 overflow-y-auto px-3 py-3"
            @scroll="handleMessagesScroll"
          >
            <!-- Empty state -->
            <div
              v-if="chatMessages.length === 0 && !sending && !routing"
              class="flex h-full items-center justify-center"
            >
              <div class="max-w-sm text-center">
                <!-- Animated gradient avatar -->
                <div class="relative mx-auto mb-4 size-14">
                  <div
                    class="absolute inset-0 animate-pulse rounded-2xl bg-gradient-to-br from-primary/25 to-primary/5 blur-lg"
                  ></div>
                  <div
                    class="relative flex size-14 animate-float items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 shadow-lg shadow-primary/10 ring-1 ring-primary/10"
                  >
                    <IconifyIcon
                      icon="lucide:sparkles"
                      class="size-7 text-primary"
                    />
                  </div>
                </div>
                <div class="text-sm font-semibold text-foreground">
                  {{
                    effectiveWelcomeMessage ||
                    $t('common.globalAiChat.welcomeDesc')
                  }}
                </div>
                <div class="mt-1.5 text-[11px] text-muted-foreground/60">
                  {{ $t('common.globalAiChat.welcomeFirstTime') }}
                </div>
                <!-- Suggested questions as icon cards -->
                <div
                  v-if="effectiveSuggestedQuestions.length > 0"
                  class="mt-5 flex flex-col gap-1.5"
                >
                  <button
                    v-for="(q, qi) in effectiveSuggestedQuestions"
                    :key="qi"
                    class="group/sq flex items-center gap-2.5 rounded-xl border border-border/30 bg-accent/15 px-3.5 py-2.5 text-left text-xs text-foreground transition-all hover:border-primary/30 hover:bg-accent/40 hover:shadow-sm"
                    @click="askSuggested(q)"
                  >
                    <IconifyIcon
                      icon="lucide:message-circle"
                      class="size-3.5 shrink-0 text-primary/50 transition-colors group-hover/sq:text-primary"
                    />
                    <span class="truncate">{{ q }}</span>
                    <IconifyIcon
                      icon="lucide:arrow-right"
                      class="ml-auto size-3 shrink-0 text-muted-foreground/30 transition-transform group-hover/sq:translate-x-0.5 group-hover/sq:text-primary/60"
                    />
                  </button>
                </div>
              </div>
            </div>

            <!-- Message list -->
            <div class="space-y-2">
              <ChatMessageItem
                v-for="(msg, idx) in chatMessages"
                :key="idx"
                :msg="msg"
                :index="idx"
                :api-prefix="props.apiPrefix"
                :agents="agents"
                :selected-agent="selectedAgent"
                :show-agent-switch="isAgentSwitch(idx)"
                :pending-ops="getPendingOpsForMessage(msg)"
                :countdown-now="countdownNow"
                compact
                @copy="onCopyMessage"
                @confirm="confirmAction"
                @reject="rejectAction"
                @consent-confirm="confirmConsent"
                @consent-reject="rejectConsent"
                @open-url="openImagePreview"
                @action-click="clickActionButton"
                @regenerate="regenerateMessage"
                @edit="editAndResend"
                @retry="retryLastMessage"
              />
            </div>

            <!-- Pending page operation confirmations (unassociated fallback at bottom) -->
            <div
              v-for="op in unassociatedPendingOps"
              :key="op.invokeId"
              class="overflow-hidden rounded-lg border"
              :class="
                op.resolved
                  ? 'border-border/20 bg-accent/10'
                  : 'border-warning/30 bg-warning/5'
              "
            >
              <!-- Resolved state -->
              <div
                v-if="op.resolved"
                class="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px]"
              >
                <IconifyIcon
                  :icon="op.allowed ? 'lucide:check-circle' : 'lucide:x-circle'"
                  class="size-3 shrink-0"
                  :class="op.allowed ? 'text-green-600' : 'text-red-500'"
                />
                <span class="truncate text-muted-foreground">
                  <span class="font-medium text-foreground/60">{{
                    op.operationLabel
                  }}</span>
                  <span
                    v-if="op.operationDescription"
                    class="ml-1 text-muted-foreground/60"
                    >{{ op.operationDescription }}</span
                  >
                </span>
                <span
                  class="ml-auto shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium"
                  :class="
                    op.allowed
                      ? 'bg-green-50 text-green-600 dark:bg-green-950/30'
                      : 'bg-red-50 text-red-600 dark:bg-red-950/30'
                  "
                >
                  {{
                    op.allowed
                      ? $t('shared.pageOperation.confirmOk')
                      : $t('shared.pageOperation.confirmCancel')
                  }}
                </span>
              </div>

              <!-- Pending state -->
              <template v-else>
                <div class="flex items-center gap-1.5 px-2.5 py-1.5">
                  <IconifyIcon
                    icon="lucide:shield-alert"
                    class="size-3.5 shrink-0 text-warning"
                  />
                  <div class="min-w-0 flex-1">
                    <div
                      class="truncate text-[11px] font-medium text-foreground/80"
                    >
                      {{ op.operationLabel }}
                    </div>
                    <div
                      v-if="op.operationDescription"
                      class="truncate text-[10px] text-muted-foreground/60"
                    >
                      {{ op.operationDescription }}
                    </div>
                    <div class="mt-0.5 text-[10px] text-muted-foreground/50">
                      {{
                        $t('shared.pageOperation.confirmCountdown', {
                          seconds: Math.max(
                            0,
                            60 -
                              Math.floor(
                                (countdownNow - (op.startedAt || 0)) / 1000,
                              ),
                          ),
                        })
                      }}
                    </div>
                  </div>
                  <div class="flex shrink-0 items-center gap-1">
                    <button
                      class="inline-flex items-center gap-0.5 rounded-md bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                      @click="aiPanelStore.resolvePageOp(op.invokeId, true)"
                    >
                      <IconifyIcon icon="lucide:check" class="size-3" />
                      {{ $t('shared.pageOperation.confirmOk') }}
                    </button>
                    <button
                      class="inline-flex items-center gap-0.5 rounded-md border border-border/60 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
                      @click="aiPanelStore.resolvePageOp(op.invokeId, false)"
                    >
                      <IconifyIcon icon="lucide:x" class="size-3" />
                      {{ $t('shared.pageOperation.confirmCancel') }}
                    </button>
                  </div>
                </div>

                <!-- Collapsible params -->
                <details
                  v-if="op.params && Object.keys(op.params).length > 0"
                  class="[&>summary::-webkit-details-marker]:hidden [&>summary]:list-none"
                >
                  <summary
                    class="flex cursor-pointer items-center gap-1 border-t border-border/20 px-2.5 py-0.5 text-[10px] text-muted-foreground/60 hover:text-muted-foreground"
                  >
                    <IconifyIcon icon="lucide:code" class="size-2.5" />
                    {{ $t('common.globalAiChat.args') }}
                    <IconifyIcon
                      icon="lucide:chevron-down"
                      class="size-2.5 transition-transform duration-200 [details[open]>&]:rotate-180"
                    />
                  </summary>
                  <div class="border-t border-border/20 px-2.5 py-1">
                    <pre
                      class="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-[10px] text-muted-foreground"
                      >{{ JSON.stringify(op.params, null, 2) }}</pre
                    >
                  </div>
                </details>
              </template>
            </div>

            <!-- Routing loading indicator -->
            <Transition name="fade">
              <div
                v-if="routing"
                class="routing-card relative overflow-hidden rounded-xl border border-border/30 bg-accent/30 px-4 py-3 backdrop-blur-sm"
              >
                <div class="relative z-[1] flex items-center gap-2.5">
                  <div
                    class="relative flex size-6 items-center justify-center rounded-lg bg-primary/10"
                  >
                    <IconifyIcon
                      icon="lucide:route"
                      class="size-3.5 text-primary"
                    />
                    <span
                      class="routing-dot absolute -right-0.5 -top-0.5 size-2 rounded-full bg-primary"
                    ></span>
                  </div>
                  <div class="flex flex-col gap-0.5">
                    <span class="text-xs font-medium text-foreground/80">
                      {{ $t('common.globalAiChat.routingAgent') }}
                    </span>
                    <div class="flex items-center gap-1">
                      <span
                        class="routing-dot size-1 rounded-full bg-primary/60"
                      ></span>
                      <span
                        class="routing-dot size-1 rounded-full bg-primary/60"
                        style="animation-delay: 0.15s"
                      ></span>
                      <span
                        class="routing-dot size-1 rounded-full bg-primary/60"
                        style="animation-delay: 0.3s"
                      ></span>
                    </div>
                  </div>
                </div>
                <div class="routing-shimmer absolute inset-0"></div>
              </div>
            </Transition>

            <!-- Floating action buttons (scroll-to-top + scroll-to-bottom) -->
            <div class="sticky bottom-2 z-10 flex justify-center gap-2">
              <Transition name="fade">
                <button
                  v-if="showScrollToTop && !streaming"
                  class="inline-flex size-8 items-center justify-center rounded-full border border-border/60 bg-background/95 text-muted-foreground shadow-lg backdrop-blur-sm transition-all hover:bg-primary hover:text-white hover:shadow-xl"
                  :aria-label="$t('common.globalAiChat.scrollToTop')"
                  @click="scrollToTop()"
                >
                  <IconifyIcon icon="lucide:arrow-up" class="size-4" />
                </button>
              </Transition>
              <Transition name="fade">
                <button
                  v-if="showScrollToBottom && !streaming"
                  class="inline-flex size-8 items-center justify-center rounded-full border border-border/60 bg-background/95 text-muted-foreground shadow-lg backdrop-blur-sm transition-all hover:bg-primary hover:text-white hover:shadow-xl"
                  @click="scrollToBottom(true)"
                >
                  <IconifyIcon icon="lucide:arrow-down" class="size-4" />
                </button>
              </Transition>
            </div>
          </div>

          <!-- Token usage indicator -->
          <div
            v-if="totalTokensUsed > 0 && !streaming"
            class="flex items-center justify-center gap-1.5 border-t border-border/50 px-4 py-1 text-[11px] text-muted-foreground"
          >
            <IconifyIcon icon="lucide:activity" class="size-3" />
            <span
              >{{ chatMessages.length }}
              {{ $t('common.globalAiChat.messages') }} ·
              {{ totalTokensUsed.toLocaleString() }}
              {{ $t('common.globalAiChat.tokens') }}</span
            >
            <span class="text-border">|</span>
            <Dropdown :trigger="['click']" placement="bottomRight">
              <button class="hover:text-foreground" type="button">
                <IconifyIcon icon="lucide:download" class="size-3" />
              </button>
              <template #overlay>
                <Menu :items="exportMenuItems" />
              </template>
            </Dropdown>
          </div>

          <!-- Input area -->
          <div
            class="shrink-0 border-t border-border px-3 py-2"
            @dragover="handleDragOver"
            @drop="handleDrop"
          >
            <!-- Pending attachments -->
            <TransitionGroup
              v-if="
                mentionedAgent ||
                (showAttachments && pendingAttachments.length > 0)
              "
              name="att-pop"
              tag="div"
              class="mb-1.5 flex flex-wrap gap-1.5"
            >
              <div
                v-if="mentionedAgent"
                :key="`mention-${mentionedAgent.id}`"
                class="bg-primary/8 inline-flex items-center gap-1 rounded-full border border-primary/20 px-2 py-1 text-[11px] text-primary"
              >
                <span class="font-semibold">@</span>
                <span class="max-w-[140px] truncate font-medium">
                  {{ mentionedAgent.name }}
                </span>
                <button
                  class="hover:bg-primary/12 flex size-4 items-center justify-center rounded-full text-primary/70 transition-colors hover:text-primary"
                  @click="clearMentionedAgent"
                >
                  <IconifyIcon icon="lucide:x" class="size-2.5" />
                </button>
              </div>
              <div
                v-for="(att, ai) in pendingAttachments"
                :key="att.url || ai"
                class="group relative"
              >
                <div
                  v-if="att.type === 'image'"
                  class="relative size-12 overflow-hidden rounded border border-border"
                >
                  <img
                    :src="att.preview || att.url"
                    class="size-full object-cover"
                  />
                  <button
                    class="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-destructive text-white opacity-0 transition-opacity group-hover:opacity-100"
                    @click="removePendingAttachment(ai)"
                  >
                    <IconifyIcon icon="lucide:x" class="size-2.5" />
                  </button>
                </div>
                <div
                  v-else
                  class="flex items-center gap-1 rounded border border-border bg-accent/50 px-1.5 py-1"
                >
                  <IconifyIcon
                    :icon="getFileIcon(att.name || '', att.mime_type)"
                    class="size-3.5 shrink-0 text-muted-foreground"
                  />
                  <span
                    class="max-w-[80px] truncate text-[11px] text-foreground"
                  >
                    {{ att.name }}
                  </span>
                  <button
                    class="flex size-3.5 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-destructive"
                    @click="removePendingAttachment(ai)"
                  >
                    <IconifyIcon icon="lucide:x" class="size-2.5" />
                  </button>
                </div>
              </div>
              <div
                v-if="uploading"
                class="flex size-12 items-center justify-center rounded border border-dashed border-border"
              >
                <Spin size="small" />
              </div>
            </TransitionGroup>
            <div
              v-if="showAttachments && pendingAttachments.length > 0"
              class="mb-1 text-[10px] text-muted-foreground/70"
            >
              {{
                $t('common.globalAiChat.attachmentCount', {
                  count: pendingAttachments.length,
                  max: 5,
                })
              }}
            </div>

            <!-- Trust session toggle -->
            <div
              v-if="chatMessages.length > 0"
              class="mb-1 flex items-center justify-between"
            >
              <label
                class="flex cursor-pointer items-center gap-1 text-[10px] text-muted-foreground/60 hover:text-muted-foreground"
              >
                <input
                  v-model="trustSession"
                  type="checkbox"
                  class="size-3 cursor-pointer rounded accent-primary"
                />
                <span>{{ $t('common.globalAiChat.consentTrustSession') }}</span>
                <Tooltip
                  :title="$t('common.globalAiChat.consentTrustSessionHint')"
                >
                  <IconifyIcon icon="lucide:info" class="size-2.5" />
                </Tooltip>
              </label>
              <span class="text-[10px] text-muted-foreground/40">
                {{ $t('common.globalAiChat.shiftEnterHint') }}
              </span>
            </div>

            <!-- Bound KB list (available for this agent) / 当前智能体已绑定知识库 -->
            <div
              v-if="agentKBBindings.length > 0"
              class="mb-1 flex flex-wrap items-center gap-1"
            >
              <IconifyIcon
                icon="lucide:book-open"
                class="size-3 shrink-0 text-muted-foreground/50"
              />
              <span
                v-for="kb in agentKBBindings"
                :key="kb.knowledge_base_id"
                class="bg-primary/8 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] leading-tight text-primary/70"
              >
                {{ kb.kb_name || `KB#${kb.knowledge_base_id}` }}
              </span>
            </div>
            <!-- @-selected KBs for this turn (RAG subset) / 本回合 @ 选中的检索范围 -->
            <div
              v-if="selectedKBIds.length > 0"
              class="mb-1 flex flex-wrap items-center gap-1"
            >
              <span class="text-[10px] text-muted-foreground/70">{{
                $t('common.globalAiChat.selectedKbForTurn')
              }}</span>
              <span
                v-for="kid in selectedKBIds"
                :key="kid"
                class="inline-flex items-center gap-0.5 rounded-full border border-primary/25 bg-background px-1.5 py-0.5 text-[10px] text-primary"
              >
                {{
                  agentKBBindings.find((b) => b.knowledge_base_id === kid)
                    ?.kb_name || `KB#${kid}`
                }}
                <button
                  type="button"
                  class="rounded p-0 leading-none text-muted-foreground hover:text-destructive"
                  :aria-label="$t('common.globalAiChat.removeKbFromTurn')"
                  @click="removeSelectedKnowledgeBase(kid)"
                >
                  <IconifyIcon icon="lucide:x" class="size-2.5" />
                </button>
              </span>
            </div>

            <!-- Input row: 字数统计移出 TextArea，避免导致图标与输入框对齐失调 -->
            <div
              class="overflow-hidden rounded-xl border border-border/40 bg-muted/20 transition-all focus-within:border-primary/40 focus-within:bg-background focus-within:shadow-sm focus-within:shadow-primary/5"
            >
              <Transition name="mention-panel">
                <div
                  v-if="mentionOpen"
                  class="border-b border-border/30 bg-background/70 px-2 py-1.5"
                >
                  <div
                    class="mb-1 flex items-center gap-1 text-[10px] text-muted-foreground/70"
                  >
                    <IconifyIcon icon="lucide:at-sign" class="size-3" />
                    <span>{{
                      $t('common.globalAiChat.mentionMixedHint')
                    }}</span>
                  </div>
                  <div
                    v-if="agentsLoading"
                    class="flex items-center gap-2 px-1 py-2"
                  >
                    <Spin size="small" />
                    <span class="text-[11px] text-muted-foreground">
                      {{ $t('common.globalAiChat.mentionAgentLoading') }}
                    </span>
                  </div>
                  <div
                    v-else-if="mentionCandidates.length === 0"
                    class="space-y-1 px-1 py-2 text-[11px] text-muted-foreground"
                  >
                    <p>{{ $t('common.globalAiChat.mentionAgentEmpty') }}</p>
                    <p
                      v-if="agentKBBindings.length === 0 && !agentsLoading"
                      class="text-[10px] text-muted-foreground/80"
                    >
                      {{ $t('common.globalAiChat.mentionKbNoneBound') }}
                    </p>
                  </div>
                  <div v-else class="max-h-48 space-y-2 overflow-y-auto">
                    <template
                      v-for="(c, candidateIndex) in mentionCandidates"
                      :key="
                        c.kind === 'agent'
                          ? `a-${c.agent.id}`
                          : `kb-${c.binding.knowledge_base_id}`
                      "
                    >
                      <div
                        v-if="
                          candidateIndex === 0 ||
                          mentionCandidates[candidateIndex - 1]!.kind !== c.kind
                        "
                        class="px-0.5 pt-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60"
                      >
                        {{
                          c.kind === 'agent'
                            ? $t('common.globalAiChat.mentionSectionAgents')
                            : $t('common.globalAiChat.mentionSectionKbs')
                        }}
                      </div>
                      <button
                        v-if="c.kind === 'agent'"
                        class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors"
                        :class="
                          candidateIndex === mentionActiveIndex
                            ? 'bg-primary/10 text-foreground'
                            : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground'
                        "
                        @mousedown.prevent
                        @click="selectMentionAgent(c.agent)"
                      >
                        <div
                          class="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-[10px] font-medium text-primary"
                        >
                          <img
                            v-if="c.agent.avatar"
                            :src="c.agent.avatar"
                            :alt="c.agent.name"
                            class="size-7 rounded-lg object-cover"
                          />
                          <span v-else>{{
                            c.agent.name.charAt(0).toUpperCase()
                          }}</span>
                        </div>
                        <div class="min-w-0 flex-1">
                          <div class="truncate text-[12px] font-medium">
                            {{ c.agent.name }}
                          </div>
                          <div
                            v-if="c.agent.description"
                            class="truncate text-[10px] text-muted-foreground/70"
                          >
                            {{ c.agent.description }}
                          </div>
                        </div>
                      </button>
                      <button
                        v-else
                        class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors"
                        :class="
                          candidateIndex === mentionActiveIndex
                            ? 'bg-primary/10 text-foreground'
                            : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground'
                        "
                        @mousedown.prevent
                        @click="selectMentionKnowledgeBase(c.binding)"
                      >
                        <div
                          class="flex size-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 text-amber-700 dark:text-amber-400"
                        >
                          <IconifyIcon icon="lucide:library" class="size-4" />
                        </div>
                        <div class="min-w-0 flex-1">
                          <div class="truncate text-[12px] font-medium">
                            {{
                              c.binding.kb_name ||
                              `KB#${c.binding.knowledge_base_id}`
                            }}
                          </div>
                          <div
                            class="truncate text-[10px] text-muted-foreground/70"
                          >
                            {{ $t('common.globalAiChat.mentionKbPickHint') }}
                          </div>
                        </div>
                      </button>
                    </template>
                  </div>
                </div>
              </Transition>
              <div class="flex min-h-[2.5rem] items-end gap-1.5 px-2 py-2">
                <Tooltip
                  v-if="showAttachments"
                  :title="$t('common.globalAiChat.addAttachment')"
                >
                  <button
                    class="flex size-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
                    :disabled="agents.length === 0 || sending"
                    @click="fileInput?.click()"
                  >
                    <IconifyIcon icon="lucide:paperclip" class="size-3.5" />
                  </button>
                </Tooltip>
                <Tooltip
                  v-if="showAttachments && supportsVision"
                  :title="
                    capturing
                      ? $t('common.globalAiChat.screenshotCapturing')
                      : $t('common.globalAiChat.screenshot')
                  "
                >
                  <button
                    class="flex size-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
                    :disabled="agents.length === 0 || sending || capturing"
                    @click="handleScreenshot"
                  >
                    <Spin v-if="capturing" size="small" />
                    <IconifyIcon v-else icon="lucide:camera" class="size-3.5" />
                  </button>
                </Tooltip>
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  :accept="chatAcceptAttribute"
                  class="hidden"
                  @change="handleFileSelect"
                />
                <Input.TextArea
                  v-model:value="inputMessage"
                  :placeholder="$t('common.globalAiChat.inputPlaceholder')"
                  :auto-size="{ minRows: 2, maxRows: 6 }"
                  :maxlength="32000"
                  :disabled="agents.length === 0 || sending"
                  class="ai-chat-textarea min-w-0 flex-1 !border-0 !bg-transparent !text-sm !shadow-none !outline-none !ring-0"
                  @keydown="handleKeyDown"
                  @paste="handlePaste"
                />
                <button
                  class="send-btn flex size-7 shrink-0 items-center justify-center rounded-full shadow-sm transition-all hover:scale-110 hover:shadow-md active:scale-95 disabled:opacity-40 disabled:hover:scale-100"
                  :class="[
                    streaming
                      ? 'bg-destructive text-destructive-foreground'
                      : 'bg-primary text-primary-foreground',
                  ]"
                  :aria-label="
                    streaming
                      ? $t('common.globalAiChat.stop')
                      : $t('common.commandBar.send')
                  "
                  :disabled="
                    !streaming &&
                    ((!inputMessage.trim() &&
                      pendingAttachments.length === 0) ||
                      agents.length === 0 ||
                      sending)
                  "
                  @click="streaming ? stopGeneration() : handleSendMessage()"
                >
                  <Spin
                    v-if="!streaming && (sending || routing)"
                    size="small"
                  />
                  <IconifyIcon
                    v-else
                    :icon="streaming ? 'lucide:square' : 'lucide:arrow-up'"
                    class="size-3.5"
                  />
                </button>
              </div>
              <!-- 字数统计单独一行，不影响输入框与图标的垂直对齐 -->
              <div class="flex justify-end px-1 pb-0.5">
                <span class="text-[10px] text-muted-foreground/60">
                  {{ inputMessage.length }} / 32000
                </span>
              </div>
            </div>
          </div>
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

    <!-- Image preview lightbox -->
    <Modal
      v-model:open="previewImageVisible"
      :footer="null"
      width="auto"
      :style="{ maxWidth: '90vw' }"
      centered
      destroy-on-close
    >
      <img
        :src="previewImageUrl"
        alt=""
        class="max-h-[80vh] max-w-full object-contain"
      />
    </Modal>
  </Teleport>
</template>

<style scoped>
/* Slide panel transition / 滑出面板过渡 */
.slide-panel-enter-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-panel-leave-active {
  transition: transform 0.2s ease-in;
}

.slide-panel-enter-from,
.slide-panel-leave-to {
  transform: translateX(100%);
}

/* Fade transition for route notice / 路由提示淡入淡出 */
.fade-enter-active {
  transition: opacity 0.2s ease-out;
}

.fade-leave-active {
  transition: opacity 0.3s ease-in;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Mention dropdown transition / @ 智能体下拉过渡 */
.mention-panel-enter-active,
.mention-panel-leave-active {
  overflow: hidden;
  transition:
    opacity 0.2s ease,
    max-height 0.24s ease,
    transform 0.24s ease;
}

.mention-panel-enter-from,
.mention-panel-leave-to {
  opacity: 0;
  max-height: 0;
  transform: translateY(-6px);
}

.mention-panel-enter-to,
.mention-panel-leave-from {
  opacity: 1;
  max-height: 240px;
  transform: translateY(0);
}

.page-ai-details-enter-active,
.page-ai-details-leave-active {
  overflow: hidden;
  transition:
    opacity 0.2s ease,
    max-height 0.26s ease,
    transform 0.26s ease;
}

.page-ai-details-enter-from,
.page-ai-details-leave-to {
  opacity: 0;
  max-height: 0;
  transform: translateY(-6px);
}

.page-ai-details-enter-to,
.page-ai-details-leave-from {
  opacity: 1;
  max-height: 320px;
  transform: translateY(0);
}

/* Bubble transition / 气泡过渡 */
.bubble-enter-active {
  animation: bubble-in 0.3s ease-out;
}

.bubble-leave-active {
  animation: bubble-in 0.2s ease-in reverse;
}

@keyframes bubble-in {
  0% {
    opacity: 0;
    transform: scale(0.6) translateY(20px);
  }

  100% {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

/* Float animation for empty state avatar / 空状态头像浮动动画 */
@keyframes float {
  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(-6px);
  }
}

.animate-float {
  animation: float 3s ease-in-out infinite;
}

/* Attachment pop transition / 附件弹出过渡 */
.att-pop-enter-active {
  animation: att-in 0.25s ease-out;
}

.att-pop-leave-active {
  animation: att-in 0.15s ease-in reverse;
}

@keyframes att-in {
  0% {
    opacity: 0;
    transform: scale(0.5);
  }

  100% {
    opacity: 1;
    transform: scale(1);
  }
}

/* Routing shimmer effect / 路由闪烁效果 */
.routing-shimmer {
  background: linear-gradient(
    90deg,
    transparent 0%,
    hsl(var(--primary) / 0.06) 50%,
    transparent 100%
  );
  animation: shimmer-slide 2s ease-in-out infinite;
}

@keyframes shimmer-slide {
  0% {
    transform: translateX(-100%);
  }

  100% {
    transform: translateX(100%);
  }
}

/* Routing dots animation / 路由点点动画 */
.routing-dot {
  animation: routing-pulse 0.8s ease-in-out infinite;
}

@keyframes routing-pulse {
  0%,
  100% {
    opacity: 0.3;
    transform: scale(0.8);
  }

  50% {
    opacity: 1;
    transform: scale(1.2);
  }
}

/* Streaming progress bar animation (T5) / 流式进度条动画 */
.streaming-bar {
  width: 30%;
  background: linear-gradient(
    90deg,
    transparent,
    hsl(var(--primary) / 0.6),
    hsl(var(--primary)),
    hsl(var(--primary) / 0.6),
    transparent
  );
  border-radius: 9999px;
  animation: streaming-slide 1.5s ease-in-out infinite;
}

@keyframes streaming-slide {
  0% {
    transform: translateX(-100%);
  }

  50% {
    transform: translateX(233%);
  }

  100% {
    transform: translateX(-100%);
  }
}

/* 输入框多行文本域：保证与图标垂直对齐 */
.ai-chat-textarea :deep(.ant-input) {
  resize: none;
}
</style>
