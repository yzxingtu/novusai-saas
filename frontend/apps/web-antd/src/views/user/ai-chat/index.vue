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
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Drawer,
  Dropdown,
  Input,
  Menu,
  Modal,
  Spin,
  Tooltip,
  message,
} from 'ant-design-vue';

import type { InputVariable } from '#/components/business/ai-chat-panel/types';

import ChatMessageItem from '#/components/business/ai-chat-panel/ChatMessageItem.vue';
import { useAIChat } from '#/components/business/ai-chat-panel/use-ai-chat';
import { $t } from '#/locales';
import { getFileIcon } from '#/utils/file';

defineOptions({ name: 'UserAIChat' });

const API_PREFIX = '/api/user';
const UPLOAD_URL = '/api/user/attachments/upload';

// ============ Chat Logic ============

const chat = useAIChat({
  apiPrefix: API_PREFIX,
  uploadUrl: UPLOAD_URL,
  onVariablesMissing: () => {
    const agent = selectedAgent.value;
    if (agent?.input_variables?.length) {
      pendingVarsSend.value = true;
      openVarsModal(agent.input_variables, agent.id, agent.name);
    }
  },
});

const {
  agents,
  agentsLoading,
  selectedAgentId,
  selectedAgent,
  loadAgents,
  selectAgent,
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
  agentKBBindings,
  loadAgentKBBindings,
  allAgentsVariables,
  ensureAgentVarsLoaded,
  applyVariables,
} = chat;

// Template ref bindings / 模板 ref 绑定
void messagesContainer;
void fileInput;
void handleMessagesScroll;
void showScrollToBottom;
void showScrollToTop;
void scrollToBottom;
void scrollToTop;

// ============ Sidebar ============

const mobileSidebarOpen = ref(false);
const conversationSearch = ref('');

const filteredConversations = computed(() => {
  const keyword = conversationSearch.value.trim().toLowerCase();
  if (!keyword) return conversations.value;
  return conversations.value.filter((c) =>
    (c.title || '').toLowerCase().includes(keyword),
  );
});

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

// ============ Conversation handlers ============

function onSelectConversation(convId: number) {
  loadConversationMessages(convId);
  mobileSidebarOpen.value = false;
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
  mobileSidebarOpen.value = false;
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

// ============ Welcome & Suggested Questions ============

const effectiveWelcomeMessage = computed(
  () => selectedAgent.value?.welcome_message || '',
);

const effectiveSuggestedQuestions = computed<string[]>(() => {
  const raw = selectedAgent.value?.suggested_questions;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (q): q is string => typeof q === 'string' && q.trim() !== '',
  );
});

function askSuggested(question: string) {
  inputMessage.value = question;
  sendMessage();
}

// ============ Image Preview ============

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

// ============ Send (no routing for user side) ============

function handleSendClick() {
  sendMessage();
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    sendMessage();
    return;
  }
  handleInputKeyDown(e);
}

// ============ Agent Switch Detection ============

function isAgentSwitch(idx: number): boolean {
  const msg = chatMessages.value[idx];
  if (!msg || msg.role !== 'assistant' || !msg.agent_id) return false;
  for (let i = idx - 1; i >= 0; i--) {
    const prev = chatMessages.value[i];
    if (prev?.role === 'assistant') {
      return prev.agent_id !== msg.agent_id;
    }
  }
  return false;
}

// ============ Input Variables Modal ============

const varsModalVisible = ref(false);
const varsFormValues = reactive<Record<string, string>>({});
const varsModalAgent = ref<null | { id: number; name: string; vars: InputVariable[] }>(null);
const varsPersist = ref(false);
const pendingVarsSend = ref(false);

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
  // Validate required fields / 校验必填字段
  const required = varsModalAgent.value?.vars.filter((v) => v.required) ?? [];
  const missing = required.filter((v) => !varsFormValues[v.name]?.trim());
  if (missing.length > 0) {
    message.warning(
      missing.map((v) => v.label || v.name).join('、') +
        ' ' +
        $t('common.required'),
    );
    return;
  }
  applyVariables(varsModalAgent.value!.id, { ...varsFormValues }, varsPersist.value);
  varsModalVisible.value = false;
  if (pendingVarsSend.value) {
    pendingVarsSend.value = false;
    sendMessage();
  }
}

function onVarsCancel() {
  varsModalVisible.value = false;
  pendingVarsSend.value = false;
}

// ============ Watchers ============

watch(selectedAgentId, (agentId) => {
  if (agentId) {
    loadAgentKBBindings(agentId);
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

// ============ Lifecycle ============

onMounted(async () => {
  await loadAgents();
  await loadConversations();
});

onUnmounted(() => {
  cleanup();
});
</script>

<template>
  <div class="flex h-[calc(100vh-9rem)] overflow-hidden rounded-xl border border-border bg-card">
    <!-- ═══ Input Variables Modal ═══ -->
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

    <!-- ═══ Desktop Sidebar ═══ -->
    <aside
      class="hidden w-[280px] shrink-0 flex-col border-r border-border/50 md:flex"
    >
      <!-- Agent Selector -->
      <div class="shrink-0 border-b border-border/40 p-3">
        <div class="mb-2 flex items-center justify-between">
          <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {{ $t('user.aiChat.agents') }}
          </span>
          <Spin v-if="agentsLoading" size="small" />
        </div>
        <div v-if="agents.length > 0" class="space-y-1">
          <button
            v-for="agent in agents"
            :key="agent.id"
            class="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-all duration-150"
            :class="
              selectedAgentId === agent.id
                ? 'bg-primary/8 text-foreground shadow-sm ring-1 ring-primary/15'
                : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
            "
            @click="selectAgent(agent.id)"
          >
            <div
              class="flex size-8 shrink-0 items-center justify-center rounded-lg text-xs font-medium"
              :class="
                selectedAgentId === agent.id
                  ? 'bg-primary/15 text-primary'
                  : 'bg-muted/60 text-muted-foreground'
              "
            >
              <img
                v-if="agent.avatar"
                :src="agent.avatar"
                :alt="agent.name"
                class="size-8 rounded-lg object-cover"
              />
              <span v-else>{{ agent.name.charAt(0).toUpperCase() }}</span>
            </div>
            <div class="min-w-0 flex-1">
              <div
                class="truncate text-sm"
                :class="selectedAgentId === agent.id ? 'font-medium' : ''"
              >
                {{ agent.name }}
              </div>
              <div
                v-if="agent.description"
                class="truncate text-[11px] text-muted-foreground/60"
              >
                {{ agent.description }}
              </div>
            </div>
          </button>
        </div>
        <div
          v-else-if="!agentsLoading"
          class="py-4 text-center text-xs text-muted-foreground"
        >
          {{ $t('user.aiChat.noAgents') }}
        </div>
      </div>

      <!-- Conversation History -->
      <div class="flex flex-1 flex-col overflow-hidden">
        <div class="shrink-0 px-3 py-2">
          <div class="mb-2 flex items-center justify-between">
            <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
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
        <div class="flex-1 overflow-y-auto px-3 pb-2">
          <Spin :spinning="conversationsLoading">
            <div
              v-if="groupedConversations.length === 0 && !conversationsLoading"
              class="py-6 text-center text-sm text-muted-foreground"
            >
              {{ $t('common.globalAiChat.noHistory') }}
            </div>
            <div
              v-for="group in groupedConversations"
              :key="group.label"
              class="mb-2"
            >
              <div class="mb-1 px-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
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
                  <div
                    v-if="activeConversationId === conv.id && editingConversationId !== conv.id"
                    class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r-full bg-primary"
                  ></div>
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
                      <span
                        class="truncate text-[13px]"
                        :class="activeConversationId === conv.id ? 'font-medium' : ''"
                      >
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
    </aside>

    <!-- ═══ Chat Area ═══ -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <!-- Chat Header -->
      <div class="flex shrink-0 items-center justify-between border-b border-border/40 px-4 py-2">
        <div class="flex min-w-0 items-center gap-2">
          <!-- Mobile sidebar toggle -->
          <button
            class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:hidden"
            @click="mobileSidebarOpen = true"
          >
            <IconifyIcon icon="lucide:panel-left" class="size-4" />
          </button>
          <!-- Current agent info -->
          <div v-if="selectedAgent" class="flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-xs font-medium text-primary"
            >
              <img
                v-if="selectedAgent.avatar"
                :src="selectedAgent.avatar"
                :alt="selectedAgent.name"
                class="size-8 rounded-lg object-cover"
              />
              <span v-else>{{ selectedAgent.name.charAt(0).toUpperCase() }}</span>
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ selectedAgent.name }}
              </div>
              <div
                v-if="selectedAgent.description"
                class="max-w-[300px] truncate text-[11px] text-muted-foreground"
              >
                {{ selectedAgent.description }}
              </div>
            </div>
          </div>
          <span v-else class="text-sm font-semibold text-foreground">
            {{ $t('user.aiChat.title') }}
          </span>
        </div>

        <!-- Right actions -->
        <div class="flex items-center gap-0.5">
          <!-- Edit variables button (shown when agent has input_variables) -->
          <Tooltip
            v-if="selectedAgent?.input_variables?.length"
            :title="$t('user.aiChat.varsModal.editVars')"
          >
            <button
              class="flex h-7 items-center gap-1 rounded-lg px-2 text-xs font-medium text-primary transition-colors hover:bg-primary/8"
              @click="openVarsModal(selectedAgent!.input_variables!, selectedAgent!.id, selectedAgent!.name)"
            >
              <IconifyIcon icon="lucide:sliders-horizontal" class="size-3.5" />
              <span class="hidden sm:inline">{{ $t('user.aiChat.varsModal.editVars') }}</span>
              <span
                v-if="Object.keys(allAgentsVariables[selectedAgent?.id ?? 0] ?? {}).length > 0"
                class="size-1.5 rounded-full bg-green-500"
              />
            </button>
          </Tooltip>
          <Tooltip :title="$t('common.aiPanel.newChat')">
            <button
              class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              @click="onStartNewChat"
            >
              <IconifyIcon icon="lucide:plus" class="size-4" />
            </button>
          </Tooltip>
          <Tooltip
            v-if="activeConversationId"
            :title="$t('common.globalAiChat.memoryUpdated')"
          >
            <button
              class="flex size-8 items-center justify-center rounded-lg transition-colors hover:bg-muted disabled:opacity-40"
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
              <IconifyIcon v-else icon="lucide:brain" class="size-4" />
            </button>
          </Tooltip>
        </div>
      </div>

      <!-- Streaming progress bar -->
      <div v-if="streaming" class="h-0.5 w-full overflow-hidden bg-primary/10">
        <div class="streaming-bar h-full bg-primary/60" />
      </div>

      <!-- Memory panel -->
      <Transition name="fade">
        <div
          v-if="showMemoryPanel"
          class="shrink-0 border-b border-border/30 bg-muted/5 px-4 py-3"
        >
          <div class="mb-2.5 flex items-center justify-between">
            <div class="flex items-center gap-1.5 text-xs font-medium text-foreground">
              <IconifyIcon icon="lucide:brain" class="size-3.5 text-primary" />
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
              <div class="mb-1 flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                <IconifyIcon :icon="section.icon" class="size-3" />
                {{ section.label }}
              </div>
              <ul class="space-y-0.5 text-[11px] text-foreground/80">
                <li
                  v-for="(item, ii) in section.items"
                  :key="ii"
                  class="flex items-start gap-1.5 pl-1"
                >
                  <span class="mt-1.5 size-1 shrink-0 rounded-full bg-primary/40"></span>
                  {{ item }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Messages -->
      <div
        ref="messagesContainer"
        class="flex-1 overflow-y-auto px-4 py-4 sm:px-6"
        @scroll="handleMessagesScroll"
      >
        <!-- Empty state -->
        <div
          v-if="chatMessages.length === 0 && !sending"
          class="flex h-full items-center justify-center"
        >
          <div class="max-w-md text-center">
            <div class="relative mx-auto mb-5 size-16">
              <div
                class="absolute inset-0 animate-pulse rounded-2xl bg-gradient-to-br from-primary/25 to-primary/5 blur-lg"
              ></div>
              <div
                class="relative flex size-16 animate-float items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 shadow-lg shadow-primary/10 ring-1 ring-primary/10"
              >
                <IconifyIcon icon="lucide:sparkles" class="size-8 text-primary" />
              </div>
            </div>
            <div class="text-base font-semibold text-foreground">
              {{
                effectiveWelcomeMessage ||
                $t('user.aiChat.welcomeTitle')
              }}
            </div>
            <div class="mt-2 text-sm text-muted-foreground">
              {{ $t('user.aiChat.welcomeDesc') }}
            </div>
            <!-- Suggested questions -->
            <div
              v-if="effectiveSuggestedQuestions.length > 0"
              class="mt-6 flex flex-col gap-2"
            >
              <button
                v-for="(q, qi) in effectiveSuggestedQuestions"
                :key="qi"
                class="group/sq flex items-center gap-3 rounded-xl border border-border/30 bg-accent/15 px-4 py-3 text-left text-sm text-foreground transition-all hover:border-primary/30 hover:bg-accent/40 hover:shadow-sm"
                @click="askSuggested(q)"
              >
                <IconifyIcon
                  icon="lucide:message-circle"
                  class="size-4 shrink-0 text-primary/50 transition-colors group-hover/sq:text-primary"
                />
                <span class="flex-1 truncate">{{ q }}</span>
                <IconifyIcon
                  icon="lucide:arrow-right"
                  class="size-3.5 shrink-0 text-muted-foreground/30 transition-transform group-hover/sq:translate-x-0.5 group-hover/sq:text-primary/60"
                />
              </button>
            </div>
          </div>
        </div>

        <!-- Message list -->
        <div class="mx-auto max-w-3xl space-y-3">
          <ChatMessageItem
            v-for="(msg, idx) in chatMessages"
            :key="idx"
            :msg="msg"
            :index="idx"
            :api-prefix="API_PREFIX"
            :agents="agents"
            :selected-agent="selectedAgent"
            :show-agent-switch="isAgentSwitch(idx)"
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

      <!-- Token usage -->
      <div
        v-if="totalTokensUsed > 0 && !streaming"
        class="flex items-center justify-center gap-1.5 border-t border-border/50 px-4 py-1 text-[11px] text-muted-foreground"
      >
        <IconifyIcon icon="lucide:activity" class="size-3" />
        <span>
          {{ chatMessages.length }}
          {{ $t('common.globalAiChat.messages') }} ·
          {{ totalTokensUsed.toLocaleString() }}
          {{ $t('common.globalAiChat.tokens') }}
        </span>
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
        class="shrink-0 border-t border-border px-4 py-3 sm:px-6"
        @dragover="handleDragOver"
        @drop="handleDrop"
      >
        <!-- Pending attachments -->
        <TransitionGroup
          v-if="pendingAttachments.length > 0"
          name="att-pop"
          tag="div"
          class="mb-2 flex flex-wrap gap-1.5"
        >
          <div
            v-for="(att, ai) in pendingAttachments"
            :key="att.url || ai"
            class="group relative"
          >
            <div
              v-if="att.type === 'image'"
              class="relative size-14 overflow-hidden rounded-lg border border-border"
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
              class="flex items-center gap-1.5 rounded-lg border border-border bg-accent/50 px-2 py-1.5"
            >
              <IconifyIcon
                :icon="getFileIcon(att.name || '', att.mime_type)"
                class="size-4 shrink-0 text-muted-foreground"
              />
              <span class="max-w-[100px] truncate text-xs text-foreground">
                {{ att.name }}
              </span>
              <button
                class="flex size-4 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-destructive"
                @click="removePendingAttachment(ai)"
              >
                <IconifyIcon icon="lucide:x" class="size-3" />
              </button>
            </div>
          </div>
          <div
            v-if="uploading"
            class="flex size-14 items-center justify-center rounded-lg border border-dashed border-border"
          >
            <Spin size="small" />
          </div>
        </TransitionGroup>
        <div
          v-if="pendingAttachments.length > 0"
          class="mb-1 text-[10px] text-muted-foreground/70"
        >
          {{ $t('common.globalAiChat.attachmentCount', { count: pendingAttachments.length, max: 5 }) }}
        </div>

        <!-- Trust session toggle -->
        <div
          v-if="chatMessages.length > 0"
          class="mb-1.5 flex items-center justify-between"
        >
          <label class="flex cursor-pointer items-center gap-1 text-[11px] text-muted-foreground/60 hover:text-muted-foreground">
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
          <span class="text-[11px] text-muted-foreground/40">
            {{ $t('common.globalAiChat.shiftEnterHint') }}
          </span>
        </div>

        <!-- Bound KB indicator -->
        <div
          v-if="agentKBBindings.length > 0"
          class="mb-1.5 flex flex-wrap items-center gap-1"
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

        <!-- Input row -->
        <div
          class="flex items-end gap-2 rounded-xl border border-border/40 bg-muted/20 px-3 py-2 transition-all focus-within:border-primary/40 focus-within:bg-background focus-within:shadow-sm focus-within:shadow-primary/5"
        >
          <Tooltip :title="$t('common.globalAiChat.addAttachment')">
            <button
              class="flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
              :disabled="agents.length === 0 || sending"
              @click="fileInput?.click()"
            >
              <IconifyIcon icon="lucide:paperclip" class="size-4" />
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
            :placeholder="$t('user.aiChat.inputPlaceholder')"
            :auto-size="{ minRows: 1, maxRows: 4 }"
            :maxlength="32000"
            :show-count="true"
            :disabled="agents.length === 0 || sending"
            class="flex-1 !border-0 !bg-transparent !text-sm !shadow-none !outline-none !ring-0"
            @keydown="handleKeyDown"
            @paste="handlePaste"
          />
          <button
            :class="[
              'flex size-8 shrink-0 items-center justify-center rounded-full shadow-sm transition-all hover:scale-110 hover:shadow-md active:scale-95 disabled:opacity-40 disabled:hover:scale-100',
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
            @click="streaming ? stopGeneration() : handleSendClick()"
          >
            <Spin v-if="!streaming && sending" size="small" />
            <IconifyIcon
              v-else
              :icon="streaming ? 'lucide:square' : 'lucide:arrow-up'"
              class="size-4"
            />
          </button>
        </div>
      </div>
    </div>

    <!-- ═══ Mobile Sidebar Drawer ═══ -->
    <Drawer
      v-model:open="mobileSidebarOpen"
      placement="left"
      :width="300"
      :closable="true"
      class="md:hidden"
    >
      <template #title>
        <div class="flex items-center gap-2">
          <IconifyIcon icon="lucide:sparkles" class="size-4 text-primary" />
          <span class="font-semibold">{{ $t('user.aiChat.title') }}</span>
        </div>
      </template>

      <!-- Agent selector (mobile) -->
      <div class="mb-4">
        <div class="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {{ $t('user.aiChat.agents') }}
        </div>
        <div v-if="agents.length > 0" class="space-y-1">
          <button
            v-for="agent in agents"
            :key="agent.id"
            class="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-all"
            :class="
              selectedAgentId === agent.id
                ? 'bg-primary/8 text-foreground ring-1 ring-primary/15'
                : 'text-muted-foreground hover:bg-accent/50'
            "
            @click="selectAgent(agent.id); mobileSidebarOpen = false;"
          >
            <div
              class="flex size-7 shrink-0 items-center justify-center rounded-lg text-[10px] font-medium"
              :class="
                selectedAgentId === agent.id
                  ? 'bg-primary/15 text-primary'
                  : 'bg-muted/60'
              "
            >
              <img
                v-if="agent.avatar"
                :src="agent.avatar"
                :alt="agent.name"
                class="size-7 rounded-lg object-cover"
              />
              <span v-else>{{ agent.name.charAt(0).toUpperCase() }}</span>
            </div>
            <span class="truncate text-sm">{{ agent.name }}</span>
          </button>
        </div>
      </div>

      <!-- Conversation list (mobile) -->
      <div>
        <div class="mb-2 flex items-center justify-between">
          <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {{ $t('common.globalAiChat.history') }}
          </span>
          <button
            class="flex items-center gap-1 text-xs text-primary"
            @click="onStartNewChat"
          >
            <IconifyIcon icon="lucide:plus" class="size-3" />
            {{ $t('common.aiPanel.newChat') }}
          </button>
        </div>
        <Spin :spinning="conversationsLoading">
          <div
            v-if="groupedConversations.length === 0 && !conversationsLoading"
            class="py-4 text-center text-sm text-muted-foreground"
          >
            {{ $t('common.globalAiChat.noHistory') }}
          </div>
          <div
            v-for="group in groupedConversations"
            :key="group.label"
            class="mb-2"
          >
            <div class="mb-1 text-[11px] font-medium text-muted-foreground/60">
              {{ group.label }}
            </div>
            <div class="space-y-0.5">
              <div
                v-for="conv in group.items"
                :key="conv.id"
                class="group relative flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 transition-all"
                :class="
                  activeConversationId === conv.id && editingConversationId !== conv.id
                    ? 'bg-primary/8 text-foreground'
                    : 'text-muted-foreground hover:bg-accent/50'
                "
                @click="editingConversationId !== conv.id && onSelectConversation(conv.id)"
                @dblclick.stop="startEditTitle(conv)"
              >
                <IconifyIcon v-if="editingConversationId !== conv.id" icon="lucide:message-square" class="size-3.5 shrink-0" />
                <template v-if="editingConversationId === conv.id">
                  <Input
                    v-model:value="editingTitle"
                    size="small"
                    :placeholder="$t('common.globalAiChat.conversationTitlePlaceholder')"
                    class="flex-1 text-sm"
                    @blur="commitEditTitle"
                    @keydown.enter="commitEditTitle"
                    @keydown.esc="cancelEditTitle"
                    @click.stop
                  />
                </template>
                <span v-else class="flex-1 truncate text-sm">
                  {{ conv.title || `#${conv.id}` }}
                </span>
                <button
                  v-if="editingConversationId !== conv.id"
                  class="flex size-5 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 hover:text-destructive group-hover:opacity-100"
                  @click.stop="onDeleteConversation(conv.id)"
                >
                  <IconifyIcon icon="lucide:trash-2" class="size-3" />
                </button>
              </div>
            </div>
          </div>
        </Spin>
      </div>
    </Drawer>

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
  </div>
</template>

<style scoped>
/* Fade transition / 淡入淡出 */
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

/* Float animation for empty state / 空状态浮动动画 */
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

/* Attachment pop transition */
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

/* Streaming progress bar / 流式进度条 */
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
</style>
