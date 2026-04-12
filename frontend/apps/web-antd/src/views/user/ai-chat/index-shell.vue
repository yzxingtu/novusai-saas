<script lang="ts" setup>
/**
 * User AI Chat - Full Page
 * 用户端 AI 对话 — 全页
 *
 * Desktop: left sidebar (agent selector + conversation history) + right chat area
 * Mobile: single column chat, sidebar in Drawer
 * 桌面：左侧栏（智能体+会话历史）+ 右侧对话区；移动端：单列对话，侧栏在 Drawer 中。
 * Reuses useAIChat composable with /user API prefix
 */
import type { LocationQuery } from 'vue-router';

import type { InputVariable } from '#/types/ai-chat';

import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { message, Modal } from 'ant-design-vue';

import { formatLocalizedList } from '#/components/business/ai-chat-panel/display-formatters';
import { useAIChat } from '#/components/business/ai-chat-panel/use-ai-chat';
import { $t } from '#/locales';
import { getAgentInputVariables } from '#/types/ai-chat';
import { normalizeStarterQuestions } from '#/utils/ai-starter-questions';

import { provideUserAIChatContext, type ConversationGroup } from './modules/ai-chat-context';
import UserAIChatMobileDrawer from './modules/UserAIChatMobileDrawer.vue';
import UserAIChatSidebar from './modules/UserAIChatSidebar.vue';
import UserAIChatVarsModal from './modules/UserAIChatVarsModal.vue';
import UserAIChatWorkspace from './modules/UserAIChatWorkspace.vue';
import UserAIChatWorkspaceHero from './modules/UserAIChatWorkspaceHero.vue';

defineOptions({ name: 'UserAIChat' });

const API_PREFIX = '/api/user';
const UPLOAD_URL = '/api/user/attachments/upload';
const route = useRoute();
const router = useRouter();

function parsePositiveQueryNumber(
  value: LocationQuery[string] | undefined,
): number | undefined {
  const rawValue = Array.isArray(value) ? value[0] : value;
  if (typeof rawValue !== 'string') {
    return undefined;
  }
  const parsed = Number.parseInt(rawValue, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}

function parseQueryText(
  value: LocationQuery[string] | undefined,
): string | undefined {
  const rawValue = Array.isArray(value) ? value[0] : value;
  if (typeof rawValue !== 'string') {
    return undefined;
  }
  const normalized = rawValue.trim();
  return normalized.length > 0 ? normalized : undefined;
}

const initialAgentId = ref<number | undefined>(
  parsePositiveQueryNumber(route.query.agentId),
);
const initialConversationId = ref<number | undefined>(
  parsePositiveQueryNumber(route.query.conversationId),
);
const lastAppliedPrompt = ref('');
const routeReady = ref(false);

// ============ Chat Logic / 对话逻辑 ============

const chat = useAIChat({
  apiPrefix: API_PREFIX,
  initialAgentId,
  initialConversationId,
  uploadUrl: UPLOAD_URL,
  onVariablesMissing: () => {
    const agent = selectedAgent.value;
    if (!agent) return;
    const inputVariables = getAgentInputVariables(agent);
    if (inputVariables.length > 0) {
      pendingSendState.value = {
        agentId: agent.id,
        routeSource: null,
      };
      openVarsModal(inputVariables, agent.id, agent.name);
    }
  },
});

const {
  agents,
  selectedAgentId,
  selectedAgent,
  loadAgents,
  selectAgent,
  conversations,
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
  sendMessage,
  cleanup,
  clearConversationMemory,
  clearingMemory,
  fetchConversationMemory,
  exportAsMarkdown,
  exportAsPlainText,
  agentKBBindings,
  allAgentsVariables,
  ensureAgentVarsLoaded,
  applyVariables,
} = chat;

// ============ Sidebar / 侧栏 ============

const mobileSidebarOpen = ref(false);
const conversationSearch = ref('');

const filteredConversations = computed(() => {
  const keyword = conversationSearch.value.trim().toLowerCase();
  if (!keyword) return conversations.value;
  return conversations.value.filter((c) =>
    (c.title || '').toLowerCase().includes(keyword),
  );
});

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

// ============ Conversation handlers / 会话操作 ============

function onSelectConversation(convId: number) {
  void loadConversationMessages(convId);
  const conversation = conversations.value.find((item) => item.id === convId);
  void router.replace({
    path: '/ai-chat',
    query: {
      ...(conversation?.agent_id
        ? { agentId: String(conversation.agent_id) }
        : {}),
      conversationId: String(convId),
    },
  });
  mobileSidebarOpen.value = false;
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
  if (id === null || id === undefined) return;
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
  void router.replace({
    path: '/ai-chat',
    query: selectedAgentId.value
      ? { agentId: String(selectedAgentId.value) }
      : {},
  });
  mobileSidebarOpen.value = false;
}

function onSelectAgent(agentId: number) {
  selectAgent(agentId);
  void router.replace({
    path: '/ai-chat',
    query: { agentId: String(agentId) },
  });
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

// ============ Welcome & Suggested Questions / 欢迎语与推荐问 ============

const starterAgent = computed(() => selectedAgent.value ?? null);

const effectiveWelcomeMessage = computed(
  () => starterAgent.value?.welcome_message || '',
);

const effectiveSuggestedQuestions = computed<string[]>(() => {
  return normalizeStarterQuestions(starterAgent.value?.suggested_questions);
});

const activeConversation = computed(() => {
  return (
    conversations.value.find(
      (item) => item.id === activeConversationId.value,
    ) ?? null
  );
});

const workspaceHighlights = computed(() => {
  return [
    {
      icon: 'lucide:book-open',
      key: 'knowledge',
      label: $t('user.aiChat.workspace.signals.knowledge'),
      value:
        agentKBBindings.value.length > 0
          ? $t('user.aiChat.workspace.signals.knowledgeValue', {
              count: agentKBBindings.value.length,
            })
          : $t('user.aiChat.workspace.signals.knowledgeEmpty'),
    },
    {
      icon: 'lucide:history',
      key: 'history',
      label: $t('user.aiChat.workspace.signals.history'),
      value: $t('user.aiChat.workspace.signals.historyValue', {
        count: conversations.value.length,
      }),
    },
    {
      icon: 'lucide:image-up',
      key: 'vision',
      label: $t('user.aiChat.workspace.signals.vision'),
      value: selectedAgent.value?.model_capabilities?.supports_vision
        ? $t('user.aiChat.workspace.signals.visionReady')
        : $t('user.aiChat.workspace.signals.visionStandard'),
    },
  ];
});

const showWorkspaceHero = computed(() => {
  return !(
    chatMessages.value.length > 0 ||
    !!activeConversationId.value ||
    sending.value ||
    streaming.value
  );
});

const chatHeaderSubtitle = computed(() => {
  if (showWorkspaceHero.value) {
    return '';
  }
  if (activeConversation.value?.title?.trim()) {
    return activeConversation.value.title;
  }
  if (selectedAgent.value?.description?.trim()) {
    return selectedAgent.value.description;
  }
  return $t('user.aiChat.workspace.noAgentSelected');
});

const selectedAgentInputVariables = computed(() =>
  getAgentInputVariables(selectedAgent.value),
);

const selectedAgentHasVariables = computed(
  () => selectedAgentInputVariables.value.length > 0,
);

const selectedAgentVarsConfigured = computed(() => {
  return (
    Object.keys(allAgentsVariables.value[selectedAgent.value?.id ?? 0] ?? {})
      .length > 0
  );
});

function openSelectedAgentVarsModal() {
  const agent = selectedAgent.value;
  if (!agent) {
    return;
  }
  openVarsModal(selectedAgentInputVariables.value, agent.id, agent.name);
}

async function applyRouteIntent() {
  const conversationId = parsePositiveQueryNumber(route.query.conversationId);
  const agentId = parsePositiveQueryNumber(route.query.agentId);
  const prompt = parseQueryText(route.query.prompt);

  if (conversationId && conversationId !== activeConversationId.value) {
    await loadConversationMessages(conversationId);
  } else if (
    agentId &&
    agentId !== selectedAgentId.value &&
    agents.value.some((agent) => agent.id === agentId)
  ) {
    selectAgent(agentId);
  }

  if (prompt && lastAppliedPrompt.value !== prompt) {
    inputMessage.value = prompt;
    lastAppliedPrompt.value = prompt;
  }
  if (!prompt) {
    lastAppliedPrompt.value = '';
  }
}

// ============ Input Variables Modal / 输入变量弹窗 ============

const varsModalVisible = ref(false);
const varsFormValues = reactive<Record<string, string>>({});
const varsModalAgent = ref<null | {
  id: number;
  name: string;
  vars: InputVariable[];
}>(null);
const varsPersist = ref(false);
const pendingSendState = ref<null | {
  agentId: number;
  routeSource: null | string;
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
  // Validate required fields / 校验必填字段
  const required = varsModalAgent.value?.vars.filter((v) => v.required) ?? [];
  const missing = required.filter((v) => !varsFormValues[v.name]?.trim());
  if (missing.length > 0) {
    message.warning(
      $t('user.aiChat.varsModal.fillRequired', {
        fields: formatLocalizedList(missing.map((v) => v.label || v.name)),
      }),
    );
    return;
  }
  applyVariables(
    varsModalAgent.value!.id,
    { ...varsFormValues },
    varsPersist.value,
  );
  varsModalVisible.value = false;
  if (pendingSendState.value) {
    const { agentId: targetAgentId, routeSource } = pendingSendState.value;
    pendingSendState.value = null;
    sendMessage({ agentId: targetAgentId, routeSource });
  }
}

function onVarsCancel() {
  varsModalVisible.value = false;
  pendingSendState.value = null;
}

provideUserAIChatContext({
  apiPrefix: API_PREFIX,
  chat,
  mobileSidebarOpen,
  conversationSearch,
  groupedConversations,
  exportMenuItems,
  editingConversationId,
  editingTitle,
  showMemoryPanel,
  showWorkspaceHero,
  workspaceHighlights,
  effectiveWelcomeMessage,
  effectiveSuggestedQuestions,
  chatHeaderSubtitle,
  selectedAgentHasVariables,
  selectedAgentVarsConfigured,
  varsModalVisible,
  varsFormValues,
  varsModalAgent,
  varsPersist,
  onSelectConversation,
  onDeleteConversation,
  onStartNewChat,
  onSelectAgent,
  startEditTitle,
  commitEditTitle,
  cancelEditTitle,
  onToggleMemory,
  onClearMemory,
  openSelectedAgentVarsModal,
  onVarsConfirm,
  onVarsCancel,
});

// ============ Watchers / 侦听器 ============

watch(selectedAgentId, (agentId) => {
  if (agentId) {
    const agent = agents.value.find((a) => a.id === agentId);
    const vars = agent?.input_variables;
    if (vars && vars.length > 0) {
      // Load saved vars from localStorage / 从 localStorage 加载已保存变量
      ensureAgentVarsLoaded(agentId);
      const savedVars = allAgentsVariables.value[agentId] ?? {};
      const missingRequired = vars.filter(
        (v) => v.required && !savedVars[v.name]?.trim(),
      );
      // Only open modal if there are required vars not yet filled / 仅当有必填变量未填时打开弹窗
      if (missingRequired.length > 0) {
        openVarsModal(vars, agentId, agent?.name ?? '');
      }
    }
  }
});

// ============ Lifecycle / 生命周期 ============

onMounted(async () => {
  initialAgentId.value = parsePositiveQueryNumber(route.query.agentId);
  initialConversationId.value = parsePositiveQueryNumber(
    route.query.conversationId,
  );
  await loadAgents(initialAgentId.value);
  await loadConversations();
  await applyRouteIntent();
  routeReady.value = true;
});

onUnmounted(() => {
  cleanup();
});

watch(
  () => route.query,
  async () => {
    initialAgentId.value = parsePositiveQueryNumber(route.query.agentId);
    initialConversationId.value = parsePositiveQueryNumber(
      route.query.conversationId,
    );
    if (!routeReady.value) {
      return;
    }
    await applyRouteIntent();
  },
  { deep: true },
);
</script>

<template>
  <div class="space-y-4">
    <UserAIChatWorkspaceHero />
    <div
      class="flex min-h-[72vh] overflow-hidden rounded-xl border border-border bg-card"
    >
      <UserAIChatVarsModal />
      <UserAIChatSidebar />
      <UserAIChatWorkspace />
      <UserAIChatMobileDrawer />
    </div>
  </div>
</template>
