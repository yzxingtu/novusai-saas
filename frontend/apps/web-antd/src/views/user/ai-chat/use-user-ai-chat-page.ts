import type { ConversationGroup } from './modules/ai-chat-context';

import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { message, Modal } from 'ant-design-vue';

import { useAIChat } from '#/components/business/ai-chat-panel/use-ai-chat';
import { $t } from '#/locales';
import { getAgentInputVariables } from '#/types/ai-chat';
import { normalizeStarterQuestions } from '#/utils/ai-starter-questions';

import { provideUserAIChatContext } from './modules/ai-chat-context';
import { useUserAIChatVarsModal } from './use-user-ai-chat-vars-modal';
import {
  parsePositiveQueryNumber,
  parseQueryText,
} from './user-ai-chat-route-query';

const API_PREFIX = '/api/user';
const UPLOAD_URL = '/api/user/attachments/upload';

export function useUserAIChatPage() {
  const route = useRoute();
  const router = useRouter();
  const initialAgentId = ref<number | undefined>(
    parsePositiveQueryNumber(route.query.agentId),
  );
  const initialConversationId = ref<number | undefined>(
    parsePositiveQueryNumber(route.query.conversationId),
  );
  const lastAppliedPrompt = ref('');
  const routeReady = ref(false);
  const mobileSidebarOpen = ref(false);
  const conversationSearch = ref('');
  const showMemoryPanel = ref(false);

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
        };
        openVarsModal(inputVariables, agent.id, agent.name);
      }
    },
  });

  const {
    agentsWithVarsInConversation,
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
    fetchConversationMemory,
    exportAsMarkdown,
    exportAsPlainText,
    agentKBBindings,
    allAgentsVariables,
    ensureAgentVarsLoaded,
    applyVariables,
  } = chat;

  const {
    headerVariablesConfigured,
    multiVarsFormValues,
    multiVarsModalVisible,
    multiVarsPersist,
    onMultiPersistChange,
    onMultiVarValueChange,
    onMultiVarsCancel,
    onMultiVarsConfirm,
    onSinglePersistChange,
    onSingleVarValueChange,
    openHeaderVarsModal,
    openSelectedAgentVarsModal,
    openVarsModal,
    onVarsCancel,
    onVarsConfirm,
    pendingSendState,
    showHeaderVarsButton,
    varsFormValues,
    varsModalAgent,
    varsModalVisible,
    varsPersist,
  } = useUserAIChatVarsModal({
    agentsWithVarsInConversation,
    allAgentsVariables,
    applyVariables,
    ensureAgentVarsLoaded,
    selectedAgent,
    sendMessage,
  });

  const filteredConversations = computed(() => {
    const keyword = conversationSearch.value.trim().toLowerCase();
    if (!keyword) return conversations.value;
    return conversations.value.filter((conversation) =>
      (conversation.title || '').toLowerCase().includes(keyword),
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
    const today = [];
    const yesterday = [];
    const earlier = [];

    for (const conversation of list) {
      const timestamp = new Date(conversation.created_at).getTime();
      if (timestamp >= todayStart) today.push(conversation);
      else if (timestamp >= yesterdayStart) yesterday.push(conversation);
      else earlier.push(conversation);
    }

    const groups: ConversationGroup[] = [];
    if (today.length > 0) {
      groups.push({ label: $t('common.globalAiChat.today'), items: today });
    }
    if (yesterday.length > 0) {
      groups.push({
        label: $t('common.globalAiChat.yesterday'),
        items: yesterday,
      });
    }
    if (earlier.length > 0) {
      groups.push({
        label: $t('common.globalAiChat.earlier'),
        items: earlier,
      });
    }
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

  const editingConversationId = ref<null | number>(null);
  const editingTitle = ref('');

  function onSelectConversation(conversationId: number) {
    showMemoryPanel.value = false;
    void loadConversationMessages(conversationId);
    const conversation = conversations.value.find(
      (item) => item.id === conversationId,
    );
    void router.replace({
      path: '/ai-chat',
      query: {
        ...(conversation?.agent_id
          ? { agentId: String(conversation.agent_id) }
          : {}),
        conversationId: String(conversationId),
      },
    });
    mobileSidebarOpen.value = false;
  }

  function onDeleteConversation(conversationId: number) {
    Modal.confirm({
      title: $t('common.globalAiChat.confirmDelete'),
      onOk: () => deleteConversation(conversationId),
    });
  }

  function startEditTitle(conv: { id: number; title?: null | string }) {
    editingConversationId.value = conv.id;
    editingTitle.value = conv.title || '';
  }

  function commitEditTitle() {
    const conversationId = editingConversationId.value;
    if (conversationId === null || conversationId === undefined) return;
    const nextTitle = editingTitle.value.trim().slice(0, 200);
    editingConversationId.value = null;
    editingTitle.value = '';
    updateConversationTitle(conversationId, nextTitle);
  }

  function cancelEditTitle() {
    editingConversationId.value = null;
    editingTitle.value = '';
  }

  function onStartNewChat() {
    showMemoryPanel.value = false;
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
    showMemoryPanel.value = false;
    selectAgent(agentId);
    void router.replace({
      path: '/ai-chat',
      query: { agentId: String(agentId) },
    });
  }

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
        const success = await clearConversationMemory();
        if (success) {
          message.success($t('common.globalAiChat.clearMemorySuccess'));
          showMemoryPanel.value = false;
        } else {
          message.error($t('common.globalAiChat.clearMemoryFailed'));
        }
      },
    });
  }

  const starterAgent = computed(() => selectedAgent.value ?? null);
  const effectiveWelcomeMessage = computed(
    () => starterAgent.value?.welcome_message || '',
  );
  const effectiveSuggestedQuestions = computed<string[]>(() =>
    normalizeStarterQuestions(starterAgent.value?.suggested_questions),
  );
  const activeConversation = computed(
    () =>
      conversations.value.find(
        (item) => item.id === activeConversationId.value,
      ) ?? null,
  );
  const workspaceHighlights = computed(() => [
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
  ]);
  const showWorkspaceHero = computed(
    () =>
      !(
        chatMessages.value.length > 0 ||
        !!activeConversationId.value ||
        sending.value ||
        streaming.value
      ),
  );
  const chatHeaderSubtitle = computed(() => {
    if (showWorkspaceHero.value) return '';
    if (activeConversation.value?.title?.trim()) {
      return activeConversation.value.title;
    }
    if (selectedAgent.value?.description?.trim()) {
      return selectedAgent.value.description;
    }
    return $t('user.aiChat.workspace.noAgentSelected');
  });

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
    agentsWithVarsInConversation,
    headerHasVariables: showHeaderVarsButton,
    headerVarsConfigured: headerVariablesConfigured,
    multiVarsModalVisible,
    multiVarsFormValues,
    multiVarsPersist,
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
    onMultiPersistChange,
    onMultiVarValueChange,
    onMultiVarsCancel,
    onMultiVarsConfirm,
    onSinglePersistChange,
    onSingleVarValueChange,
    openHeaderVarsModal,
    openSelectedAgentVarsModal,
    onVarsConfirm,
    onVarsCancel,
  });

  watch(selectedAgentId, (agentId) => {
    if (!agentId) return;
    const agent = agents.value.find((item) => item.id === agentId);
    const vars = agent?.input_variables;
    if (!vars || vars.length === 0) return;
    ensureAgentVarsLoaded(agentId);
    const savedVars = allAgentsVariables.value[agentId] ?? {};
    const missingRequired = vars.filter(
      (item) => item.required && !savedVars[item.name]?.trim(),
    );
    if (missingRequired.length > 0) {
      openVarsModal(vars, agentId, agent?.name ?? '');
    }
  });

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
      if (!routeReady.value) return;
      await applyRouteIntent();
    },
    { deep: true },
  );
}
