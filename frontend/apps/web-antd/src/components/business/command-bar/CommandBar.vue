<script lang="ts" setup>
import type {
  AgentItem,
  ConversationItem,
} from '#/components/business/ai-chat-panel/types';

/**
 * Command Bar 组件
 *
 * 全局命令面板，支持：
 * - 快速输入消息发送给 AI
 * - @mention 选择智能体
 * - 最近对话快速恢复
 * - Ctrl+J 快捷键唤起
 */
import { computed, nextTick, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Spin } from 'ant-design-vue';

import { $t } from '#/locales';
import { toAvatarDisplayUrl } from '#/utils/image';
import { useAIPanelStore } from '#/store';

import { useCommandBar } from './use-command-bar';

defineOptions({ name: 'CommandBar' });

const props = withDefaults(
  defineProps<{
    /** API 前缀 */
    apiPrefix: string;
    /** 是否有 AI 聊天权限 */
    canChat: boolean;
  }>(),
  {
    apiPrefix: '/tenant',
    canChat: false,
  },
);

const emit = defineEmits<{
  /** 选择历史对话 */
  selectConversation: [conversationId: number];
  /** 用户提交消息 */
  submit: [message: string];
}>();

const aiPanelStore = useAIPanelStore();

const apiPrefixRef = computed(() => props.apiPrefix);
const canChatRef = computed(() => props.canChat);

const {
  open,
  inputText,
  mode,
  agentsLoading,
  filteredAgents,
  recentConversations,
  recentLoading,
  show,
  hide,
  toggle,
  loadAgents,
  selectMentionAgent,
  exitMentionMode,
  onInputChange,
  submit,
} = useCommandBar({
  apiPrefix: apiPrefixRef,
  canChat: canChatRef,
});

const inputRef = ref<HTMLInputElement | null>(null);
const selectedIndex = ref(0);

// 打开时聚焦输入框
watch(open, async (isOpen) => {
  if (isOpen) {
    selectedIndex.value = 0;
    await nextTick();
    inputRef.value?.focus();
  }
});

// mention 模式切换时重置选中索引
watch(mode, () => {
  selectedIndex.value = 0;
});

function handleInput(e: Event) {
  const target = e.target as HTMLInputElement;
  onInputChange(target.value);
}

function handleKeydown(e: KeyboardEvent) {
  if (mode.value === 'mention') {
    const list = filteredAgents.value;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex.value = (selectedIndex.value + 1) % list.length;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex.value =
        (selectedIndex.value - 1 + list.length) % list.length;
    } else if (e.key === 'Enter' && list.length > 0) {
      e.preventDefault();
      const agent = list[selectedIndex.value];
      if (agent) {
        selectMentionAgent(agent);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      exitMentionMode();
    }
    return;
  }

  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSubmit();
  }
}

function handleSubmit() {
  const message = submit();
  if (message) {
    emit('submit', message);
  }
}

function handleMaskClick() {
  hide();
}

function handleAgentClick(agent: AgentItem) {
  selectMentionAgent(agent);
}

function agentInitial(agent: AgentItem): string {
  return agent.name.charAt(0).toUpperCase();
}

function handleConversationClick(conv: ConversationItem) {
  hide();
  if (!aiPanelStore.visible) {
    aiPanelStore.open();
  }
  emit('selectConversation', conv.id);
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const diff = now - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return $t('common.commandBar.justNow');
  if (mins < 60) return $t('common.commandBar.minutesAgo', { n: mins });
  const hours = Math.floor(mins / 60);
  if (hours < 24) return $t('common.commandBar.hoursAgo', { n: hours });
  const days = Math.floor(hours / 24);
  return $t('common.commandBar.daysAgo', { n: days });
}

/** 固定的智能体名称（UI 展示） */
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
        class="fixed inset-0 z-[1100] bg-black/40 backdrop-blur-sm"
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

            <input
              ref="inputRef"
              :value="inputText"
              :placeholder="$t('common.commandBar.placeholder')"
              class="min-w-0 flex-1 border-none bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/60"
              type="text"
              @input="handleInput"
              @keydown="handleKeydown"
            />

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

          <!-- Default: Quick Tips + Recent Conversations -->
          <div v-else-if="!inputText.trim()" class="px-4 py-3">
            <div
              class="flex items-center gap-4 text-xs text-muted-foreground/70"
            >
              <span class="flex items-center gap-1">
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
                {{ $t('common.commandBar.openOrSend') }}
              </span>
              <span class="flex items-center gap-1">
                <kbd
                  class="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px]"
                  >Esc</kbd
                >
                {{ $t('common.aiPanel.close') }}
              </span>
            </div>

            <!-- Recent Conversations -->
            <div
              v-if="recentConversations.length > 0 || recentLoading"
              class="mt-3 border-t border-border/30 pt-3"
            >
              <div
                class="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60"
              >
                <IconifyIcon icon="lucide:history" class="size-3" />
                {{ $t('common.commandBar.recentChats') }}
              </div>
              <Spin v-if="recentLoading" size="small" class="flex justify-center py-3" />
              <div v-else class="space-y-0.5">
                <div
                  v-for="conv in recentConversations"
                  :key="conv.id"
                  class="group flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 transition-colors hover:bg-accent/60"
                  @click="handleConversationClick(conv)"
                >
                  <div
                    class="flex size-6 shrink-0 items-center justify-center rounded-md bg-muted/60 text-[10px] font-medium text-muted-foreground"
                  >
                    <img
                      v-if="conv.agent_avatar"
                      :src="toAvatarDisplayUrl(conv.agent_avatar)"
                      :alt="conv.agent_name || ''"
                      class="size-full rounded-md object-cover"
                    />
                    <span v-else-if="conv.agent_name">{{ conv.agent_name.charAt(0).toUpperCase() }}</span>
                    <IconifyIcon v-else icon="lucide:message-square" class="size-3" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-[13px] text-foreground">
                      {{ conv.title || `#${conv.id}` }}
                    </div>
                  </div>
                  <div class="shrink-0 text-right">
                    <span class="text-[10px] tabular-nums text-muted-foreground/50">
                      {{ formatRelativeTime(conv.created_at) }}
                    </span>
                  </div>
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
/* Mask transition */
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

/* Bar transition */
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
