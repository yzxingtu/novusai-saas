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
import { computed, onMounted, onUnmounted, reactive, ref, toRef, watch, watchEffect } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Dropdown,
  Input,
  Menu,
  message,
  Modal,
  Popover,
  Spin,
  Tooltip,
} from 'ant-design-vue';

import type { InputVariable } from '#/components/business/ai-chat-panel/types';

import ChatMessageItem from '#/components/business/ai-chat-panel/ChatMessageItem.vue';
import { useAIChat } from '#/components/business/ai-chat-panel/use-ai-chat';
import { formStateTracker } from '#/composables/use-form-state-tracker';
import { useModalDetector } from '#/composables/use-modal-detector';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { usePageScreenshot } from '#/composables/use-page-screenshot';
import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';
import { usePublicConfigStore } from '#/store/shared/public-config';
import { getFileIcon } from '#/utils/file';

import { pageContextVersion, resolvePageContext } from './page-context-registry';
import { listPageOperations, pageOperationVersion } from './page-operation-registry';
import { useAgentRouter } from './use-agent-router';

defineOptions({ name: 'AIChatSlidePanel' });

const props = withDefaults(
  defineProps<{
    /** API prefix / API 前缀 */
    apiPrefix: string;
    /** Page-level pageContextKey (from route.meta.ai) / 页面级 pageContextKey（来自 route.meta.ai） */
    pageContextKey?: string;
    /** External pending message (from CommandBar) / 外部传入的消息（来自 CommandBar） */
    pendingMessage?: null | string;
    /** External pending conversation ID to restore (from CommandBar) / 外部传入的待恢复对话 ID（来自 CommandBar） */
    pendingConversationId?: null | number;
    /** Whether to show attachment button / 是否显示附件按钮 */
    showAttachments?: boolean;
    /** Upload URL / 上传地址 */
    uploadUrl: string;
  }>(),
  {
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
let countdownInterval: ReturnType<typeof setInterval> | null = null;
watch(hasUnresolvedPageOps, (has) => {
  if (has && !countdownInterval) {
    countdownInterval = setInterval(() => {
      countdownNow.value = Date.now();
    }, 1000);
  } else if (!has && countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
}, { immediate: true });
onUnmounted(() => {
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
});

// ============ Chat Logic (reuse useAIChat) ============

const chat = useAIChat({
  apiPrefix: toRef(props, 'apiPrefix'),
  uploadUrl: toRef(props, 'uploadUrl'),
  onToolCall: (name: string, output: string) => {
    aiPanelStore.dispatchToolCall(name, output);
  },
  onStreamComplete: () => {
    aiPanelStore.markUnread();
  },
  pageContextResolver: () =>
    enrichPageContextWithOperations(resolvePageContext(props.pageContextKey)),
  pageSessionIdGetter: getActivePageSessionId,
  onVariablesMissing: () => {
    const agent = selectedAgent.value;
    if (agent?.input_variables?.length) {
      openVarsModal(agent.input_variables as InputVariable[], agent.id, agent.name);
    }
  },
});

const {
  agents,
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
  loadAgentKBBindings,
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
    (op) => op.toolCallId && ids.has(op.toolCallId),
  );
}

/** Pending ops with no toolCallId or not matched to any message (fallback bottom render) / 未关联到消息的待确认操作（底部兜底） */
const unassociatedPendingOps = computed(() =>
  aiPanelStore.pendingPageOps.filter(
    (op) => !op.toolCallId || !allToolCallIds.value.has(op.toolCallId),
  ),
);

// ============ Input Variables Modal ============

/** Single-agent prompt modal (when routing detects missing required vars) / 单智能体变量弹窗（路由检测到必填变量缺失时） */
const varsModalVisible = ref(false);
const varsFormValues = reactive<Record<string, string>>({});
const varsModalAgent = ref<null | { id: number; name: string; vars: InputVariable[] }>(null);
const varsPersist = ref(false);
/** Pending send context: deferred until vars are filled / 待发送上下文（变量填写后发送） */
const pendingSendContext = ref<null | { agentId: number; pageContext: ReturnType<typeof resolvePageContext> }>(null);

function openVarsModal(vars: InputVariable[], agentId: number, agentName: string) {
  varsModalAgent.value = { id: agentId, name: agentName, vars };
  ensureAgentVarsLoaded(agentId);
  vars.forEach((v) => {
    varsFormValues[v.name] = allAgentsVariables.value[agentId]?.[v.name] ?? v.default ?? '';
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
    const { agentId: pendingAgentId, pageContext } = pendingSendContext.value;
    pendingSendContext.value = null;
    sendMessage({ agentId: pendingAgentId, pageContext });
  }
}

function onVarsCancel() {
  varsModalVisible.value = false;
  pendingSendContext.value = null;
}

/** Multi-agent vars editor (edit button in header) / 多智能体变量编辑（头部编辑按钮） */
const multiVarsModalVisible = ref(false);
const multiVarsFormValues = reactive<Record<number, Record<string, string>>>({});
const multiVarsPersist = ref(false);

function openMultiVarsEditor() {
  for (const a of agentsWithVarsInConversation.value) {
    ensureAgentVarsLoaded(a.id);
    multiVarsFormValues[a.id] = { ...allAgentsVariables.value[a.id] };
    // Fill defaults for any vars not yet set / 为未设置的变量填充默认值
    for (const v of (a.input_variables ?? [])) {
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

// ============ Agent Router ============

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

// ============ Page AI Capability Indicator ============

/** Current page context (reactive to route changes AND registry mutations) / 当前页面上下文 */
const currentPageContext = computed(() => {
  void pageContextVersion.value;
  return resolvePageContext(props.pageContextKey);
});

/** Current page operations list / 当前页面操作列表 */
const currentPageOperations = computed(() => {
  void pageOperationVersion.value;
  const ctx = currentPageContext.value;
  if (!ctx) return [];
  return listPageOperations(ctx.page_key);
});

/** Whether the current page has registered AI context / 当前页是否已注册 AI 上下文 */
const hasPageAI = computed(() => !!currentPageContext.value);

// ============ Send message (routing + streaming) / 发送消息（路由 + 流式） ============

/**
 * Collect lightweight visual state from the current page DOM/window.
 * 从当前页面 DOM/window 收集轻量视觉状态。
 * Uses useModalDetector for structured modal/drawer info.
 */
function collectVisualState() {
  const modals = modalState.value;
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
const MAX_PAGE_DATA_BYTES = 7168; // 7KB budget (backend limit is 8KB)

function truncateFormFields(
  pageData: Record<string, unknown>,
): Record<string, unknown> {
  const ff = pageData.form_fields;
  if (!ff || typeof ff !== 'object') return pageData;
  const entries = Object.entries(ff as Record<string, unknown>);
  if (entries.length <= MAX_FORM_FIELDS) return pageData;
  const truncated = Object.fromEntries(entries.slice(0, MAX_FORM_FIELDS));
  (truncated as Record<string, unknown>)._truncated = `Showing ${MAX_FORM_FIELDS} of ${entries.length} fields`;
  return { ...pageData, form_fields: truncated };
}

/**
 * Ensure total page_data stays under MAX_PAGE_DATA_BYTES.
 * 确保 page_data 总大小不超过 MAX_PAGE_DATA_BYTES。
 * Progressively drops list_summary.sample_rows and form_fields if needed.
 */
function guardPageDataSize(pageData: Record<string, unknown>): Record<string, unknown> {
  let data = { ...pageData };
  let size = new TextEncoder().encode(JSON.stringify(data)).length;
  if (size <= MAX_PAGE_DATA_BYTES) return data;

  // Step 1: reduce list_summary sample_rows / 步骤 1：精简 list_summary sample_rows
  const ls = data.list_summary as Record<string, unknown> | undefined;
  if (ls?.sample_rows && Array.isArray(ls.sample_rows) && ls.sample_rows.length > 0) {
    data = { ...data, list_summary: { ...ls, sample_rows: (ls.sample_rows as unknown[]).slice(0, 2) } };
    size = new TextEncoder().encode(JSON.stringify(data)).length;
    if (size <= MAX_PAGE_DATA_BYTES) return data;
    data = { ...data, list_summary: { ...ls, sample_rows: [] } };
    size = new TextEncoder().encode(JSON.stringify(data)).length;
    if (size <= MAX_PAGE_DATA_BYTES) return data;
  }

  // Step 2: drop form_fields entirely / 步骤 2：完全移除 form_fields
  if (data.form_fields) {
    const { form_fields: _ff, ...rest } = data;
    data = rest;
    size = new TextEncoder().encode(JSON.stringify(data)).length;
    if (size <= MAX_PAGE_DATA_BYTES) return data;
  }

  // Step 3: truncate document_body_text (NovusDoc / DocumentEditor) / 步骤 3：截断 document_body_text
  const body = data.document_body_text;
  if (typeof body === 'string' && body.length > 0) {
    const encoder = new TextEncoder();
    const truncateToBytes = (s: string, maxBytes: number): string => {
      const u8 = encoder.encode(s);
      if (u8.length <= maxBytes) return s;
      return new TextDecoder().decode(u8.slice(0, maxBytes));
    };
    for (const maxBodyBytes of [2400, 1600, 800]) {
      data = { ...data, document_body_text: truncateToBytes(body, maxBodyBytes) };
      size = new TextEncoder().encode(JSON.stringify(data)).length;
      if (size <= MAX_PAGE_DATA_BYTES) return data;
    }
    data = { ...data, document_body_text: truncateToBytes(body, 400) };
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
): ReturnType<typeof resolvePageContext> {
  if (!ctx) return ctx;
  const ops = listPageOperations(ctx.page_key);

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

  let pageData: Record<string, unknown> = {
    ...ctx.page_data,
    ...(liveFormFields ? { form_fields: liveFormFields } : {}),
    visual_state: collectVisualState(),
    ...(ops.length > 0
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

  const pageContext = enrichPageContextWithOperations(
    resolvePageContext(props.pageContextKey),
  );

  // P0: Agent is pinned → skip routing, send directly / 已固定智能体 → 跳过路由，直接发送
  if (isPinned.value && aiPanelStore.pinnedAgentId) {
    const pinnedId = aiPanelStore.pinnedAgentId;
    if (pinnedId !== selectedAgentId.value) {
      selectedAgentId.value = pinnedId;
    }
    const pinnedAgent = agents.value.find((a) => a.id === pinnedId);
    const pinnedRequired = pinnedAgent?.input_variables?.filter((v) => v.required) ?? [];
    if (pinnedRequired.length > 0) {
      ensureAgentVarsLoaded(pinnedId);
      const pinnedVars = allAgentsVariables.value[pinnedId] ?? {};
      const pinnedMissing = pinnedRequired.filter((v) => !pinnedVars[v.name]?.trim());
      if (pinnedMissing.length > 0) {
        pendingSendContext.value = { agentId: pinnedId, pageContext };
        openVarsModal(pinnedAgent!.input_variables!, pinnedId, pinnedAgent!.name);
        return;
      }
    }
    sendMessage({ agentId: pinnedId, pageContext });
    return;
  }

  try {
    const result = await routeMessage(
      text,
      props.pageContextKey,
      pageContext,
    );

    // Update current agent context (don't clear messages/conversations, support multi-agent chat) / 更新当前智能体上下文（不清除消息/对话，支持多智能体对话）
    if (result.agentId !== selectedAgentId.value) {
      selectedAgentId.value = result.agentId;
    }

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
    const requiredVars = routedAgent?.input_variables?.filter((v) => v.required) ?? [];
    if (requiredVars.length > 0) {
      ensureAgentVarsLoaded(result.agentId);
      const agentVars = allAgentsVariables.value[result.agentId] ?? {};
      const missing = requiredVars.filter((v) => !agentVars[v.name]?.trim());
      if (missing.length > 0) {
        // Defer send: open modal and wait for vars to be filled / 延迟发送：打开弹窗等待变量填写
        pendingSendContext.value = { agentId: result.agentId, pageContext };
        openVarsModal(routedAgent!.input_variables!, result.agentId, routedAgent!.name);
        return;
      }
    }

    // Send message (using routed agent ID) / 发送消息（使用路由后的智能体 ID）
    sendMessage({ agentId: result.agentId, pageContext });
  } catch (error: unknown) {
    if (selectedAgentId.value) {
      sendMessage({ pageContext });
      return;
    }

    const responseData =
      typeof error === 'object' && error !== null && 'response' in error
        ? Reflect.get(error, 'response')
        : null;
    const businessData =
      typeof responseData === 'object' &&
      responseData !== null &&
      'data' in responseData
        ? Reflect.get(responseData, 'data')
        : null;
    const errorMessage =
      typeof businessData === 'object' && businessData !== null
        ? Reflect.get(businessData, 'message')
        : null;

    const baseMsg =
      typeof errorMessage === 'string' && errorMessage
        ? errorMessage
        : $t('common.http.internalServerError');
    message.error(
      `${baseMsg} ${$t('common.globalAiChat.routeFailedHint')}`,
    );
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
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    handleSendMessage();
    return;
  }
  handleInputKeyDown(e);
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

const editingConversationId = ref<number | null>(null);
const editingTitle = ref('');

function startEditTitle(conv: { id: number; title?: string | null }) {
  editingConversationId.value = conv.id;
  editingTitle.value = conv.title || '';
}

function commitEditTitle() {
  const id = editingConversationId.value;
  if (id == null) return;
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
  startNewConversation();
  showHistory.value = false;
  showMemoryPanel.value = false;
}

// ============ Panel Controls ============

const panelRef = ref<HTMLElement | null>(null);

function handleClose() {
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

// ============ Click-outside: close when not docked ============

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

// ============ Pin ============

function unpinAgent() {
  aiPanelStore.togglePin(0, '');
}

// ============ Memory ============

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

// ============ Screenshot ============

const { capturing, captureAndUpload } = usePageScreenshot();

async function handleScreenshot() {
  if (capturing.value || !supportsVision.value) return;
  const result = await captureAndUpload({
    uploadUrl: props.uploadUrl,
    extraData: props.apiPrefix.includes('/admin')
      ? { tenant_id: '0' }
      : undefined,
    excludeSelectors: [
      '[data-ai-panel]',
      '.ant-modal-root',
      '.ant-message',
      '.ant-notification',
    ],
  });
  if (result) {
    pendingAttachments.value.push(result.attachment);
  }
}

// ============ Welcome & Suggested Questions ============

const effectiveWelcomeMessage = computed(() => {
  // Use pinned agent's welcome if pinned, otherwise show generic welcome / 置顶时用置顶 agent 的欢迎语，否则通用欢迎
  if (isPinned.value && selectedAgent.value?.welcome_message) {
    return selectedAgent.value.welcome_message;
  }
  return '';
});

const effectiveSuggestedQuestions = computed<string[]>(() => {
  const raw = isPinned.value
    ? selectedAgent.value?.suggested_questions
    : undefined;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (q): q is string => typeof q === 'string' && q.trim() !== '',
  );
});

function askSuggested(question: string) {
  inputMessage.value = question;
  handleSendMessage();
}

// ============ Image preview lightbox ============

const previewImageUrl = ref('');
const previewImageVisible = ref(false);

function openImagePreview(url: string) {
  previewImageUrl.value = url;
  previewImageVisible.value = true;
}

// ============ Copy ============

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

watch(
  () => props.pendingMessage,
  (msg) => {
    if (msg) {
      inputMessage.value = msg;
      handleSendMessage();
      emit('messageSent');
    }
  },
);

// ============ External conversation restore handling / 外部对话恢复处理 ============

watch(
  () => props.pendingConversationId,
  (convId) => {
    if (convId) {
      if (!aiPanelStore.visible) {
        aiPanelStore.open();
      }
      showHistory.value = false;
      showMemoryPanel.value = false;
      loadConversationMessages(convId);
      emit('conversationRestored');
    }
  },
);

// ============ Load data on panel open / 面板打开时加载数据 ============

watch(
  () => aiPanelStore.visible,
  async (visible) => {
    if (visible) {
      const pendingId = aiPanelStore.consumePendingAgentId();
      // On panel open: reset messages/conversation but KEEP session vars
      // (vars only clear when user explicitly clicks "+" new chat)
      startNewConversation(true);
      showHistory.value = false;
      showMemoryPanel.value = false;
      await loadAgents(pendingId);
      loadConversations();
    }
  },
);

// ============ Load KB bindings on agent switch / Agent 切换时加载 KB 绑定 ============

watch(selectedAgentId, (agentId) => {
  if (agentId) {
    loadAgentKBBindings(agentId);
    // Pre-load vars from localStorage (no modal on switch) / 从 localStorage 预加载变量（切换时无需弹窗）
    ensureAgentVarsLoaded(agentId);
  }
});

// ============ Sync conversation state to store / 同步对话状态到 store ============

watch(activeConversationId, (id) => {
  aiPanelStore.setConversation(id, selectedAgentId.value ?? undefined);
});

// ============ Lifecycle ============

/** Sync CSS variable for drawer/modal offset when AI panel is docked / AI 面板停靠时同步抽屉/弹窗偏移 CSS 变量 */
watchEffect(() => {
  const shouldOffset =
    aiPanelStore.visible &&
    !aiPanelStore.minimized &&
    aiPanelStore.mode === 'panel' &&
    aiPanelStore.docked;
  const offset = shouldOffset ? `${aiPanelStore.panelWidth}px` : '0px';
  document.documentElement.style.setProperty(
    '--ai-panel-right-offset',
    offset,
  );
});

onMounted(() => {
  loadSavedWidth();
  if (aiPanelStore.visible) {
    loadAgents();
    loadConversations();
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
          :title="$t('user.aiChat.varsModal.title', { name: varsModalAgent?.name ?? '' })"
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
            <label class="flex cursor-pointer items-center gap-2 pt-1 text-xs text-muted-foreground">
              <input
                v-model="varsPersist"
                type="checkbox"
                class="size-3.5 cursor-pointer rounded accent-primary"
              />
              <span class="font-medium text-foreground/70">{{ $t('user.aiChat.varsModal.persistLabel') }}</span>
              <span class="text-[11px]">{{ $t('user.aiChat.varsModal.persistHint') }}</span>
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
            <div
              v-for="a in agentsWithVarsInConversation"
              :key="a.id"
            >
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
                    <span v-if="v.required" class="ml-0.5 text-destructive">*</span>
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
            <label class="flex cursor-pointer items-center gap-2 border-t border-border/40 pt-3 text-xs text-muted-foreground">
              <input
                v-model="multiVarsPersist"
                type="checkbox"
                class="size-3.5 cursor-pointer rounded accent-primary"
              />
              <span class="font-medium text-foreground/70">{{ $t('user.aiChat.varsModal.persistLabel') }}</span>
              <span class="text-[11px]">{{ $t('user.aiChat.varsModal.persistHint') }}</span>
            </label>
          </div>
        </Modal>

        <!-- Header -->
        <div
          class="flex shrink-0 items-center justify-between border-b border-border/40 px-3 py-1.5"
        >
          <!-- Left: Panel title + agent/route info -->
          <div class="flex min-w-0 flex-1 items-center gap-2">
            <IconifyIcon
              icon="lucide:sparkles"
              class="size-4 shrink-0 text-primary"
            />
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span class="truncate text-sm font-semibold text-foreground">
                  {{ panelTitle }}
                </span>
                <span v-if="routing" class="routing-badge relative inline-flex items-center gap-1 overflow-hidden rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                  <span class="routing-dot size-1.5 rounded-full bg-primary"></span>
                  {{ $t('common.globalAiChat.routingAgent') }}
                  <span class="routing-shimmer absolute inset-0"></span>
                </span>
              </div>
              <div class="flex items-center gap-1.5">
                <!-- Pinned agent indicator -->
                <Tooltip
                  v-if="isPinned"
                  :title="$t('common.aiPanel.unpinAgent')"
                >
                  <button
                    class="inline-flex items-center gap-0.5 rounded-full bg-primary/10 px-1.5 py-px text-[10px] font-medium text-primary transition-colors hover:bg-primary/20"
                    @click="unpinAgent"
                  >
                    <IconifyIcon icon="lucide:pin" class="size-2.5" />
                    {{ aiPanelStore.pinnedAgentName }}
                    <IconifyIcon icon="lucide:x" class="size-2" />
                  </button>
                </Tooltip>
                <!-- Route notice -->
                <Transition name="fade">
                  <span
                    v-if="routeNotice"
                    class="inline-flex items-center gap-0.5 rounded-full bg-success/10 px-1.5 py-px text-[10px] font-medium text-green-700 dark:text-green-400"
                  >
                    <IconifyIcon icon="lucide:route" class="size-2.5" />
                    {{ routeNotice }}
                  </span>
                </Transition>
                <!-- Page AI capability indicator -->
                <Popover
                  v-if="hasPageAI && !routeNotice"
                  placement="bottomLeft"
                  trigger="hover"
                  overlay-class-name="page-ai-popover"
                >
                  <template #content>
                    <div class="min-w-[180px] max-w-[260px]">
                      <div class="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-foreground">
                        <IconifyIcon icon="lucide:cpu" class="size-3.5 text-primary" />
                        {{ currentPageContext?.page_title || $t('common.aiPanel.pageAiSupported') }}
                      </div>
                      <div v-if="currentPageOperations.length > 0" class="space-y-1">
                        <div class="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
                          {{ $t('common.aiPanel.pageAiOperations') }}
                        </div>
                        <div
                          v-for="op in currentPageOperations"
                          :key="op.name"
                          class="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-[11px] hover:bg-accent/50"
                        >
                          <IconifyIcon
                            :icon="op.readonly ? 'lucide:eye' : 'lucide:pencil'"
                            class="size-3 shrink-0"
                            :class="op.readonly ? 'text-blue-500' : 'text-amber-500'"
                          />
                          <span class="flex-1 text-foreground/80">{{ op.label }}</span>
                          <span
                            class="rounded-full px-1 py-px text-[9px]"
                            :class="op.readonly ? 'bg-blue-500/10 text-blue-600' : 'bg-amber-500/10 text-amber-600'"
                          >
                            {{ op.readonly ? $t('common.aiPanel.pageAiReadonly') : $t('common.aiPanel.pageAiWritable') }}
                          </span>
                        </div>
                      </div>
                      <div v-else class="text-[11px] text-muted-foreground">
                        {{ $t('common.aiPanel.pageAiNoOperations') }}
                      </div>
                    </div>
                  </template>
                  <span
                    class="inline-flex cursor-default items-center gap-0.5 rounded-full bg-primary/8 px-1.5 py-px text-[10px] font-medium text-primary/70 transition-colors hover:bg-primary/15 hover:text-primary"
                  >
                    <IconifyIcon icon="lucide:cpu" class="size-2.5" />
                    {{ $t('common.aiPanel.pageAiSupported') }}
                    <span
                      v-if="currentPageOperations.length > 0"
                      class="ml-0.5 inline-flex size-3 items-center justify-center rounded-full bg-primary/15 text-[8px] font-bold"
                    >
                      {{ currentPageOperations.length }}
                    </span>
                  </span>
                </Popover>
              </div>
            </div>
          </div>

          <!-- Right: Grouped action buttons -->
          <div class="flex shrink-0 items-center">
            <!-- Group 1: Chat actions -->
            <div class="flex items-center gap-0.5">
              <Tooltip
                v-if="agentsWithVarsInConversation.length > 0 || selectedAgent?.input_variables?.length"
                :title="$t('user.aiChat.varsModal.editVars')"
              >
                <button
                  class="flex h-7 items-center gap-1 rounded-lg px-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/8"
                  @click="agentsWithVarsInConversation.length > 0 ? openMultiVarsEditor() : openVarsModal(selectedAgent!.input_variables as InputVariable[], selectedAgent!.id, selectedAgent!.name)"
                >
                  <IconifyIcon icon="lucide:sliders-horizontal" class="size-3.5" />
                  <span
                    v-if="agentsWithVarsInConversation.some(a => Object.keys(allAgentsVariables[a.id] ?? {}).length > 0)"
                    class="size-1.5 rounded-full bg-green-500"
                  />
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
              <Tooltip
                v-if="activeConversationId"
                :title="$t('common.globalAiChat.memoryUpdated')"
              >
                <button
                  class="flex size-7 items-center justify-center rounded-lg transition-colors hover:bg-muted disabled:opacity-40"
                  :class="
                    showMemoryPanel
                      ? 'bg-primary/10 text-primary'
                      : lastMemoryUpdated
                        ? 'text-primary'
                        : 'text-muted-foreground hover:text-foreground'
                  "
                  :disabled="clearingMemory"
                  @click="onToggleMemory"
                >
                  <Spin v-if="memoryLoading" size="small" />
                  <IconifyIcon v-else icon="lucide:brain" class="size-3.5" />
                </button>
              </Tooltip>
            </div>

            <!-- Separator -->
            <div class="mx-1 h-4 w-px bg-border/40" />

            <!-- Group 2: Window controls -->
            <div class="flex items-center gap-0.5">
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
            </div>

            <!-- Separator -->
            <div class="mx-1 h-4 w-px bg-border/40" />

            <!-- Group 3: Close actions -->
            <div class="flex items-center gap-0.5">
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
        </div>

        <!-- Streaming progress bar (T5) -->
        <div
          v-if="streaming"
          class="h-0.5 w-full overflow-hidden bg-primary/10"
        >
          <div class="streaming-bar h-full bg-primary/60" />
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
                      activeConversationId === conv.id && editingConversationId !== conv.id
                        ? 'bg-primary/8 text-foreground shadow-sm shadow-primary/5 ring-1 ring-primary/15'
                        : 'text-muted-foreground hover:bg-accent/50'
                    "
                    @click="editingConversationId !== conv.id && onSelectConversation(conv.id)"
                    @dblclick.stop="startEditTitle(conv)"
                  >
                    <!-- Active indicator bar -->
                    <div
                      v-if="activeConversationId === conv.id && editingConversationId !== conv.id"
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
                      <span v-if="conv.agent_name">{{ conv.agent_name.charAt(0).toUpperCase() }}</span>
                      <IconifyIcon v-else icon="lucide:message-square" class="size-3" />
                    </div>
                    <div class="flex min-w-0 flex-1 flex-col">
                      <template v-if="editingConversationId === conv.id">
                        <Input
                          v-model:value="editingTitle"
                          size="small"
                          :placeholder="$t('common.globalAiChat.conversationTitlePlaceholder')"
                          class="!h-7 text-[13px]"
                          @blur="commitEditTitle"
                          @keydown.enter="commitEditTitle"
                          @keydown.esc="cancelEditTitle"
                          @click.stop
                        />
                      </template>
                      <template v-else>
                        <span class="truncate text-[13px]" :class="activeConversationId === conv.id ? 'font-medium' : ''">
                          {{ conv.title || `#${conv.id}` }}
                        </span>
                        <span class="truncate text-[10px] text-muted-foreground/50">
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
                    <IconifyIcon icon="lucide:sparkles" class="size-7 text-primary" />
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
                    <IconifyIcon icon="lucide:message-circle" class="size-3.5 shrink-0 text-primary/50 transition-colors group-hover/sq:text-primary" />
                    <span class="truncate">{{ q }}</span>
                    <IconifyIcon icon="lucide:arrow-right" class="ml-auto size-3 shrink-0 text-muted-foreground/30 transition-transform group-hover/sq:translate-x-0.5 group-hover/sq:text-primary/60" />
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
              :class="op.resolved ? 'border-border/20 bg-accent/10' : 'border-warning/30 bg-warning/5'"
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
                  <span class="font-medium text-foreground/60">{{ op.operationLabel }}</span>
                  <span v-if="op.operationDescription" class="ml-1 text-muted-foreground/60">{{ op.operationDescription }}</span>
                </span>
                <span
                  class="ml-auto shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium"
                  :class="op.allowed ? 'bg-green-50 text-green-600 dark:bg-green-950/30' : 'bg-red-50 text-red-600 dark:bg-red-950/30'"
                >
                  {{ op.allowed ? $t('shared.pageOperation.confirmOk') : $t('shared.pageOperation.confirmCancel') }}
                </span>
              </div>

              <!-- Pending state -->
              <template v-else>
                <div class="flex items-center gap-1.5 px-2.5 py-1.5">
                  <IconifyIcon icon="lucide:shield-alert" class="size-3.5 shrink-0 text-warning" />
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-[11px] font-medium text-foreground/80">
                      {{ op.operationLabel }}
                    </div>
                    <div v-if="op.operationDescription" class="truncate text-[10px] text-muted-foreground/60">
                      {{ op.operationDescription }}
                    </div>
                    <div class="mt-0.5 text-[10px] text-muted-foreground/50">
                      {{ $t('shared.pageOperation.confirmCountdown', { seconds: Math.max(0, 60 - Math.floor((countdownNow - (op.startedAt || 0)) / 1000)) }) }}
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
                  <summary class="flex cursor-pointer items-center gap-1 border-t border-border/20 px-2.5 py-0.5 text-[10px] text-muted-foreground/60 hover:text-muted-foreground">
                    <IconifyIcon icon="lucide:code" class="size-2.5" />
                    {{ $t('common.globalAiChat.args') }}
                    <IconifyIcon icon="lucide:chevron-down" class="size-2.5 transition-transform duration-200 [details[open]>&]:rotate-180" />
                  </summary>
                  <div class="border-t border-border/20 px-2.5 py-1">
                    <pre class="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-[10px] text-muted-foreground">{{ JSON.stringify(op.params, null, 2) }}</pre>
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
                  <div class="relative flex size-6 items-center justify-center rounded-lg bg-primary/10">
                    <IconifyIcon icon="lucide:route" class="size-3.5 text-primary" />
                    <span class="absolute -right-0.5 -top-0.5 size-2 rounded-full bg-primary routing-dot"></span>
                  </div>
                  <div class="flex flex-col gap-0.5">
                    <span class="text-xs font-medium text-foreground/80">
                      {{ $t('common.globalAiChat.routingAgent') }}
                    </span>
                    <div class="flex items-center gap-1">
                      <span class="routing-dot size-1 rounded-full bg-primary/60"></span>
                      <span class="routing-dot size-1 rounded-full bg-primary/60" style="animation-delay: 0.15s"></span>
                      <span class="routing-dot size-1 rounded-full bg-primary/60" style="animation-delay: 0.3s"></span>
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
                <Menu
                  :items="exportMenuItems"
                />
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
              v-if="showAttachments && pendingAttachments.length > 0"
              name="att-pop"
              tag="div"
              class="mb-1.5 flex flex-wrap gap-1.5"
            >
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
              {{ $t('common.globalAiChat.attachmentCount', { count: pendingAttachments.length, max: 5 }) }}
            </div>

            <!-- Trust session toggle -->
            <div
              v-if="chatMessages.length > 0"
              class="mb-1 flex items-center justify-between"
            >
              <label class="flex cursor-pointer items-center gap-1 text-[10px] text-muted-foreground/60 hover:text-muted-foreground">
                <input
                  v-model="trustSession"
                  type="checkbox"
                  class="size-3 cursor-pointer rounded accent-primary"
                />
                <span>{{ $t('common.globalAiChat.consentTrustSession') }}</span>
                <Tooltip :title="$t('common.globalAiChat.consentTrustSessionHint')">
                  <IconifyIcon icon="lucide:info" class="size-2.5" />
                </Tooltip>
              </label>
              <span class="text-[10px] text-muted-foreground/40">
                {{ $t('common.globalAiChat.shiftEnterHint') }}
              </span>
            </div>

            <!-- Bound KB indicator -->
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
                class="inline-flex items-center rounded-full bg-primary/8 px-1.5 py-0.5 text-[10px] leading-tight text-primary/70"
              >
                {{ kb.kb_name || `KB#${kb.knowledge_base_id}` }}
              </span>
            </div>

            <!-- Input row: 字数统计移出 TextArea，避免导致图标与输入框对齐失调 -->
            <div
              class="overflow-hidden rounded-xl border border-border/40 bg-muted/20 transition-all focus-within:border-primary/40 focus-within:bg-background focus-within:shadow-sm focus-within:shadow-primary/5"
            >
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
                  class="ai-chat-textarea flex-1 min-w-0 !border-0 !bg-transparent !text-sm !shadow-none !outline-none !ring-0"
                  @keydown="handleKeyDown"
                  @paste="handlePaste"
                />
                <button
                :class="[
                  'send-btn flex size-7 shrink-0 items-center justify-center rounded-full shadow-sm transition-all hover:scale-110 hover:shadow-md active:scale-95 disabled:opacity-40 disabled:hover:scale-100',
                  streaming
                    ? 'bg-destructive text-destructive-foreground'
                    : 'bg-primary text-primary-foreground',
                ]"
                :aria-label="streaming ? $t('common.globalAiChat.stop') : $t('common.commandBar.send')"
                :disabled="
                  !streaming &&
                  ((!inputMessage.trim() && pendingAttachments.length === 0) ||
                    agents.length === 0 ||
                    sending)
                "
                @click="streaming ? stopGeneration() : handleSendMessage()"
              >
                <Spin v-if="!streaming && (sending || routing)" size="small" />
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
  background: linear-gradient(90deg, transparent, hsl(var(--primary) / 0.6), hsl(var(--primary)), hsl(var(--primary) / 0.6), transparent);
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
