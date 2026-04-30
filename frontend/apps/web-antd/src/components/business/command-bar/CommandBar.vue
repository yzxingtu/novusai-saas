<script lang="ts" setup>
import type { MenuRecordRaw } from '@vben/types';

import type { AgentItem, ConversationItem } from '#/types/ai-chat';
import type { MenuNavigationSearchResult } from '#/utils/menu-navigation';

/**
 * Command Bar Component
 * 全局命令面板
 *
 * Global command panel, supports:
 * 支持：
 * - Quick message input to send to AI / 快速输入消息发送给 AI
 * - @mention to select agents / @mention 选择智能体
 * - Quick restore recent conversations / 最近对话快速恢复
 * - Menu search (smart detection) / 菜单搜索（智能判断）
 * - Ctrl+K shortcut to invoke / Ctrl+K 快捷键唤起
 */
import { computed, nextTick, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Input, Skeleton, Spin, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

import { useCommandBar } from './use-command-bar';

defineOptions({ name: 'CommandBar' });

const props = withDefaults(
  defineProps<{
    /** API prefix / API 前缀 */
    apiPrefix?: string;
    /** Whether has AI chat permission / 是否有 AI 聊天权限 */
    canChat?: boolean;
    /** Menu tree for search / 搜索用菜单树 */
    menus?: MenuRecordRaw[];
  }>(),
  {
    apiPrefix: '/tenant',
    canChat: false,
    menus: () => [],
  },
);

const emit = defineEmits<{
  /** Select historical conversation / 选择历史对话 */
  selectConversation: [conversationId: number];
  /** User submits message / 用户提交消息 */
  submit: [message: string];
}>();

const router = useRouter();
const aiPanelStore = useAIPanelStore();

const apiPrefixRef = computed(() => props.apiPrefix);
const canChatRef = computed(() => props.canChat);
const menusRef = computed(() => props.menus);

const {
  open,
  inputText,
  mode,
  agentsLoading,
  filteredAgents,
  selectedAgent,
  effectiveWelcomeMessage,
  effectiveSuggestedQuestions,
  recentConversations,
  recentLoading,
  menuSearchResults,
  getMenuBreadcrumb,
  show,
  hide,
  toggle,
  loadAgents,
  selectMentionAgent,
  exitMentionMode,
  onInputChange,
  submit,
  updateConversationTitle,
} = useCommandBar({
  apiPrefix: apiPrefixRef,
  canChat: canChatRef,
  menus: menusRef,
});

const inputRef = ref<null | {
  resizableTextArea?: { textArea: HTMLTextAreaElement };
}>(null);
const selectedIndex = ref(0);
const pendingMentionSubmit = ref(false);

watch(open, async (isOpen) => {
  pendingMentionSubmit.value = false;
  if (isOpen) {
    selectedIndex.value = 0;
    editingConversationId.value = null;
    editingTitle.value = '';
    if (clickNavigateTimer) {
      clearTimeout(clickNavigateTimer);
      clickNavigateTimer = null;
    }
    await nextTick();
    const el = inputRef.value?.resizableTextArea?.textArea;
    el?.focus();
  }
});

watch(mode, () => {
  selectedIndex.value = 0;
  if (mode.value !== 'mention') {
    pendingMentionSubmit.value = false;
  }
});

watch(menuSearchResults, () => {
  selectedIndex.value = 0;
});

watch(
  [agentsLoading, filteredAgents, mode],
  async ([loading, agents, currentMode]) => {
    if (
      !pendingMentionSubmit.value ||
      currentMode !== 'mention' ||
      loading ||
      agents.length === 0
    ) {
      return;
    }

    pendingMentionSubmit.value = false;
    await nextTick();
    const safeIndex = Number.isFinite(selectedIndex.value)
      ? selectedIndex.value
      : 0;
    const agent = agents[safeIndex] ?? agents[0];
    if (agent) {
      submitMentionSelection(agent);
    }
  },
);

onUnmounted(() => {
  if (clickNavigateTimer) clearTimeout(clickNavigateTimer);
});

function handleInputChange(value: string) {
  onInputChange(value);
}

const hasMenuResults = computed(() => menuSearchResults.value.length > 0);
const showAgentStarter = computed(
  () =>
    !!selectedAgent.value && mode.value !== 'mention' && !hasMenuResults.value,
);
const showOverviewContent = computed(
  () => showAgentStarter.value || !inputText.value.trim(),
);
const showRecentConversations = computed(
  () =>
    !inputText.value.trim() &&
    (recentConversations.value.length > 0 || recentLoading.value),
);

function handleKeydown(e: KeyboardEvent) {
  if (mode.value === 'mention') {
    const list = filteredAgents.value;
    if (list.length === 0) {
      switch (e.key) {
        case 'ArrowDown':
        case 'ArrowUp': {
          e.preventDefault();

          break;
        }
        case 'Enter': {
          e.preventDefault();
          pendingMentionSubmit.value = agentsLoading.value;

          break;
        }
        case 'Escape': {
          e.preventDefault();
          pendingMentionSubmit.value = false;
          exitMentionMode();

          break;
        }
        // No default
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex.value = (selectedIndex.value + 1) % list.length;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex.value =
        (selectedIndex.value - 1 + list.length) % list.length;
    } else if (e.key === 'Enter' && list.length > 0) {
      e.preventDefault();
      pendingMentionSubmit.value = false;
      const agent = list[selectedIndex.value];
      if (agent) {
        submitMentionSelection(agent);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      pendingMentionSubmit.value = false;
      exitMentionMode();
    }
    return;
  }

  if (hasMenuResults.value) {
    const results = menuSearchResults.value;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex.value = (selectedIndex.value + 1) % results.length;
      scrollSearchIntoView();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex.value =
        (selectedIndex.value - 1 + results.length) % results.length;
      scrollSearchIntoView();
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const item = results[selectedIndex.value];
      if (item) {
        handleMenuItemClick(item);
      } else {
        handleSubmit();
      }
    }
    return;
  }

  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSubmit();
  }
}

function scrollSearchIntoView() {
  nextTick(() => {
    const el = document.querySelector(
      `[data-cmd-search="${selectedIndex.value}"]`,
    );
    el?.scrollIntoView({ block: 'nearest' });
  });
}

function handleMenuItemClick(item: MenuNavigationSearchResult) {
  hide();
  if (item.path.startsWith('http://') || item.path.startsWith('https://')) {
    window.open(item.path, '_blank', 'noopener,noreferrer');
  } else {
    router.push({ path: item.path, replace: true });
  }
}

function handleSubmit() {
  pendingMentionSubmit.value = false;
  const queuedMessage = inputText.value.trim();
  if (queuedMessage) {
    aiPanelStore.queueMessage(queuedMessage);
  }
  const message = submit();
  if (message) {
    emit('submit', message);
  }
}

function submitMentionSelection(agent: AgentItem) {
  pendingMentionSubmit.value = false;
  const message = inputText.value.replace(/^@\S*\s?/, '').trim();
  if (!message) {
    selectMentionAgent(agent);
    return;
  }
  hide();
  aiPanelStore.openWithContext({
    agentId: agent.id,
    message,
  });
}

function handleStarterQuestionClick(question: string) {
  inputText.value = question;
  handleSubmit();
}

function handleMaskClick() {
  hide();
}

function handleAgentClick(agent: AgentItem) {
  submitMentionSelection(agent);
}

function agentInitial(agent: AgentItem): string {
  return agent.name.charAt(0).toUpperCase();
}

let clickNavigateTimer: null | ReturnType<typeof setTimeout> = null;

function handleConversationClick(conv: ConversationItem) {
  if (editingConversationId.value === conv.id) return;
  // Delay navigation to allow dblclick to take precedence / 延迟跳转以区分单击与双击
  if (clickNavigateTimer) clearTimeout(clickNavigateTimer);
  clickNavigateTimer = setTimeout(() => {
    clickNavigateTimer = null;
    hide();
    if (!aiPanelStore.visible) {
      aiPanelStore.open();
    }
    emit('selectConversation', conv.id);
  }, 250);
}

const editingConversationId = ref<null | number>(null);
const editingTitle = ref('');

function startEditTitle(conv: ConversationItem) {
  if (clickNavigateTimer) {
    clearTimeout(clickNavigateTimer);
    clickNavigateTimer = null;
  }
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

const pinnedName = computed(() => aiPanelStore.pinnedAgentName);

defineExpose({
  show,
  hide,
  toggle,
  loadAgents,
});
</script>

<template>
  <Teleport to="body">
    <Transition name="command-bar-mask">
      <div
        v-if="open"
        class="fixed inset-0 z-[1100] bg-black/50"
        @click="handleMaskClick"
      ></div>
    </Transition>

    <Transition name="command-bar">
      <div
        v-if="open"
        class="fixed left-1/2 top-[15%] z-[1101] w-full max-w-[580px] -translate-x-1/2"
      >
        <div
          class="overflow-hidden rounded-2xl border border-border/60 bg-card shadow-2xl"
          @click.stop
        >
          <!-- Input Area -->
          <div
            class="flex items-center gap-3 border-b border-border/40 px-4 py-3"
          >
            <IconifyIcon
              icon="lucide:sparkles"
              class="size-5 shrink-0 text-primary"
            />

            <!-- Pinned Agent Badge (click to unpin) -->
            <button
              v-if="pinnedName"
              class="flex shrink-0 items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary transition-colors hover:bg-destructive/10 hover:text-destructive"
              :title="$t('common.commandBar.clickToUnpin')"
              @click="aiPanelStore.unpinAgent()"
            >
              <IconifyIcon icon="lucide:pin" class="size-3" />
              {{ pinnedName }}
              <IconifyIcon icon="lucide:x" class="size-3" />
            </button>

            <Tooltip
              :title="`${$t('common.globalAiChat.inputPlaceholder')}，${$t('common.globalAiChat.shiftEnterHint')}`"
            >
              <Input.TextArea
                ref="inputRef"
                :value="inputText"
                :placeholder="$t('common.globalAiChat.inputPlaceholder')"
                :auto-size="{ minRows: 1, maxRows: 4 }"
                class="min-w-0 flex-1 resize-none overflow-y-auto !border-0 !bg-transparent !py-1.5 !text-sm !text-foreground !shadow-none !outline-none !ring-0 placeholder:!text-muted-foreground/60"
                @update:value="handleInputChange"
                @keydown="handleKeydown"
              />
            </Tooltip>

            <div class="flex shrink-0 items-center gap-2">
              <kbd
                class="hidden rounded border border-border/60 bg-muted/60 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline-block"
              >
                {{ $t('common.commandBar.shortcut') }}
              </kbd>
              <button
                v-if="inputText.trim()"
                class="flex items-center gap-1 rounded-lg bg-primary px-3 py-1 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                @click="handleSubmit"
              >
                <IconifyIcon icon="lucide:send" class="size-3" />
                {{ $t('common.commandBar.send') }}
              </button>
            </div>
          </div>

          <!-- @mention Dropdown -->
          <div
            v-if="mode === 'mention'"
            class="max-h-[300px] overflow-y-auto p-2"
          >
            <div
              class="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              {{ $t('common.commandBar.mentionHint') }}
            </div>

            <Spin :spinning="agentsLoading">
              <div
                v-if="filteredAgents.length === 0 && !agentsLoading"
                class="py-6 text-center text-sm text-muted-foreground"
              >
                {{ $t('common.commandBar.noAgents') }}
              </div>

              <div class="space-y-0.5">
                <div
                  v-for="(agent, idx) in filteredAgents"
                  :key="agent.id"
                  class="flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 transition-colors"
                  :class="
                    idx === selectedIndex
                      ? 'bg-primary/10 text-primary'
                      : 'text-foreground hover:bg-muted'
                  "
                  @click="handleAgentClick(agent)"
                  @mouseenter="selectedIndex = idx"
                >
                  <div
                    class="flex size-8 shrink-0 items-center justify-center rounded-lg text-xs font-medium"
                    :class="
                      idx === selectedIndex
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground'
                    "
                  >
                    <img
                      v-if="agent.avatar"
                      :src="toAvatarDisplayUrl(agent.avatar)"
                      :alt="agent.name"
                      class="size-full rounded-lg object-cover"
                    />
                    <span v-else>{{ agentInitial(agent) }}</span>
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-sm font-medium">
                      {{ agent.name }}
                    </div>
                    <div
                      v-if="agent.description"
                      class="truncate text-xs text-muted-foreground/70"
                    >
                      {{ agent.description }}
                    </div>
                  </div>
                  <div
                    v-if="aiPanelStore.pinnedAgentId === agent.id"
                    class="flex items-center gap-0.5 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary"
                  >
                    <IconifyIcon icon="lucide:pin" class="size-2.5" />
                    {{ $t('common.commandBar.pinned') }}
                  </div>
                </div>
              </div>
            </Spin>
          </div>

          <!-- Menu search results (smart detection) -->
          <div v-else-if="hasMenuResults" class="flex max-h-[360px] flex-col">
            <div class="max-h-[300px] overflow-y-auto p-2">
              <div class="mb-2 flex items-center justify-between px-2">
                <span
                  class="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60"
                >
                  {{ $t('common.commandBar.searchResults') }}
                </span>
                <span class="text-[10px] tabular-nums text-muted-foreground/50">
                  {{
                    $t('common.commandBar.resultsCount', {
                      count: menuSearchResults.length,
                    })
                  }}
                </span>
              </div>
              <div class="space-y-0.5">
                <div
                  v-for="(item, idx) in menuSearchResults"
                  :key="item.path"
                  :data-cmd-search="idx"
                  class="flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 transition-colors"
                  :class="
                    idx === selectedIndex
                      ? 'bg-primary/10 text-primary'
                      : 'text-foreground hover:bg-muted'
                  "
                  @click="handleMenuItemClick(item)"
                  @mouseenter="selectedIndex = idx"
                >
                  <div
                    class="flex size-8 shrink-0 items-center justify-center rounded-lg text-xs font-medium"
                    :class="
                      idx === selectedIndex
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground'
                    "
                  >
                    <IconifyIcon
                      v-if="item.icon"
                      :icon="item.icon as string"
                      class="size-4"
                    />
                    <IconifyIcon
                      v-else
                      icon="lucide:file-text"
                      class="size-4"
                    />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-sm font-medium">
                      {{ item.title }}
                    </div>
                    <div
                      v-if="getMenuBreadcrumb(item)"
                      class="truncate text-xs text-muted-foreground/70"
                    >
                      {{ getMenuBreadcrumb(item) }}
                    </div>
                  </div>
                  <IconifyIcon
                    v-if="idx === selectedIndex"
                    icon="lucide:corner-down-left"
                    class="size-3.5 shrink-0 text-primary"
                  />
                </div>
              </div>
            </div>

            <!-- Send to AI action -->
            <div class="border-t border-border/30 px-3 py-2">
              <button
                class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground"
                @click="handleSubmit"
              >
                <IconifyIcon
                  icon="lucide:sparkles"
                  class="size-3.5 text-primary"
                />
                <span
                  >{{ $t('common.commandBar.sendToAI') }}: "{{
                    inputText.trim()
                  }}"</span
                >
              </button>
            </div>
          </div>

          <div
            v-else-if="showOverviewContent"
            class="max-h-[360px] overflow-y-auto px-4 py-3"
          >
            <div
              v-if="showAgentStarter"
              class="rounded-2xl border border-primary/15 bg-gradient-to-br from-primary/10 via-accent/20 to-transparent p-4"
            >
              <div class="flex items-start gap-3">
                <div
                  class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-primary/15 text-sm font-semibold text-primary"
                >
                  <img
                    v-if="selectedAgent?.avatar"
                    :src="toAvatarDisplayUrl(selectedAgent.avatar)"
                    :alt="selectedAgent.name"
                    class="size-full object-cover"
                  />
                  <span v-else>{{
                    selectedAgent ? agentInitial(selectedAgent) : ''
                  }}</span>
                </div>
                <div class="min-w-0 flex-1">
                  <div
                    class="text-[11px] font-medium uppercase tracking-wider text-primary/70"
                  >
                    {{ $t('common.commandBar.agentReady') }}
                  </div>
                  <div
                    class="mt-1 truncate text-sm font-semibold text-foreground"
                  >
                    {{ selectedAgent?.name }}
                  </div>
                  <div class="mt-1.5 text-xs leading-5 text-muted-foreground">
                    {{
                      effectiveWelcomeMessage ||
                      $t('common.globalAiChat.welcomeDesc')
                    }}
                  </div>
                </div>
              </div>

              <div
                v-if="effectiveSuggestedQuestions.length > 0"
                class="mt-4 border-t border-border/30 pt-3"
              >
                <div class="mb-2 flex items-center justify-between gap-2">
                  <span
                    class="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70"
                  >
                    {{ $t('common.commandBar.starterQuestions') }}
                  </span>
                  <span class="text-[10px] text-muted-foreground/50">
                    {{ $t('common.commandBar.clickToSend') }}
                  </span>
                </div>
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="(
                      question, questionIndex
                    ) in effectiveSuggestedQuestions"
                    :key="questionIndex"
                    class="hover:bg-primary/8 group flex max-w-full items-center gap-2 rounded-full border border-border/40 bg-background/80 px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:border-primary/30 hover:text-primary"
                    @click="handleStarterQuestionClick(question)"
                  >
                    <IconifyIcon
                      icon="lucide:message-circle"
                      class="size-3.5 shrink-0 text-primary/60 transition-colors group-hover:text-primary"
                    />
                    <span class="truncate">{{ question }}</span>
                  </button>
                </div>
              </div>
            </div>

            <div
              class="flex items-center gap-4 text-xs text-muted-foreground/70"
              :class="showAgentStarter ? 'mt-3' : ''"
            >
              <span v-if="!showAgentStarter" class="flex items-center gap-1">
                <kbd
                  class="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px]"
                  >@</kbd
                >
                {{ $t('common.commandBar.mentionHint') }}
              </span>
              <span class="flex items-center gap-1">
                <kbd
                  class="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px]"
                  >Enter</kbd
                >
                {{
                  showAgentStarter
                    ? $t('common.commandBar.send')
                    : $t('common.commandBar.openOrSend')
                }}
              </span>
              <span class="flex items-center gap-1">
                <kbd
                  class="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px]"
                  >Esc</kbd
                >
                {{ $t('common.aiPanel.close') }}
              </span>
            </div>

            <div
              v-if="showRecentConversations"
              class="mt-3 border-t border-border/30 pt-3"
            >
              <div
                class="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60"
              >
                <IconifyIcon icon="lucide:history" class="size-3" />
                {{ $t('common.commandBar.recentChats') }}
              </div>

              <div v-if="recentLoading" class="space-y-1">
                <div
                  v-for="i in 4"
                  :key="i"
                  class="flex items-center gap-2.5 px-2.5 py-1.5"
                >
                  <Skeleton.Avatar :active="true" :size="24" shape="square" />
                  <div class="min-w-0 flex-1">
                    <Skeleton.Input
                      :active="true"
                      size="small"
                      style="width: 60%; height: 16px"
                    />
                  </div>
                  <Skeleton.Input
                    :active="true"
                    size="small"
                    style="width: 50px; height: 12px"
                  />
                </div>
              </div>

              <div v-else class="space-y-0.5">
                <div
                  v-for="conv in recentConversations"
                  :key="conv.id"
                  class="group flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 transition-colors hover:bg-accent/60"
                  @click="handleConversationClick(conv)"
                  @dblclick.stop="startEditTitle(conv)"
                >
                  <div
                    v-if="editingConversationId !== conv.id"
                    class="flex size-6 shrink-0 items-center justify-center rounded-md bg-muted/60 text-[10px] font-medium text-muted-foreground"
                  >
                    <img
                      v-if="conv.agent_avatar"
                      :src="toAvatarDisplayUrl(conv.agent_avatar)"
                      :alt="conv.agent_name || ''"
                      class="size-full rounded-md object-cover"
                    />
                    <span v-else-if="conv.agent_name">{{
                      conv.agent_name.charAt(0).toUpperCase()
                    }}</span>
                    <IconifyIcon
                      v-else
                      icon="lucide:message-square"
                      class="size-3"
                    />
                  </div>
                  <div class="min-w-0 flex-1">
                    <template v-if="editingConversationId === conv.id">
                      <Input
                        v-model:value="editingTitle"
                        size="small"
                        :placeholder="
                          $t('common.globalAiChat.conversationTitlePlaceholder')
                        "
                        class="!h-6 text-[13px]"
                        @blur="commitEditTitle"
                        @keydown.enter="commitEditTitle"
                        @keydown.esc="cancelEditTitle"
                        @click.stop
                      />
                    </template>
                    <div v-else class="truncate text-[13px] text-foreground">
                      {{ conv.title || `#${conv.id}` }}
                    </div>
                  </div>
                  <Tooltip
                    v-if="editingConversationId !== conv.id"
                    :title="formatDate(conv.created_at)"
                    placement="left"
                  >
                    <span
                      class="shrink-0 text-[10px] tabular-nums text-muted-foreground/50"
                    >
                      {{ formatRelativeTime(conv.created_at) }}
                    </span>
                  </Tooltip>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Mask transition / 遮罩过渡 */
.command-bar-mask-enter-active {
  transition: opacity 0.2s ease-out;
}

.command-bar-mask-leave-active {
  transition: opacity 0.15s ease-in;
}

.command-bar-mask-enter-from,
.command-bar-mask-leave-to {
  opacity: 0;
}

/* Bar transition / 栏位过渡 */
.command-bar-enter-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.command-bar-leave-active {
  transition: all 0.15s ease-in;
}

.command-bar-enter-from {
  opacity: 0;
  transform: translate(-50%, -20px) scale(0.96);
}

.command-bar-leave-to {
  opacity: 0;
  transform: translate(-50%, -10px) scale(0.98);
}
</style>
