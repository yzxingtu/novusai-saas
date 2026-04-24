<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Input, Spin } from 'ant-design-vue';

import { $t } from '#/locales';

interface HistoryConversationItem {
  agent_name?: null | string;
  id: number;
  title?: null | string;
}

interface HistoryConversationGroup {
  items: HistoryConversationItem[];
  label: string;
}

withDefaults(
  defineProps<{
    activeConversationId?: null | number;
    conversationsCount?: number;
    conversationSearch?: string;
    conversationsLoading?: boolean;
    editingConversationId?: null | number;
    editingTitle?: string;
    groupedConversations?: HistoryConversationGroup[];
  }>(),
  {
    activeConversationId: null,
    conversationsCount: 0,
    conversationSearch: '',
    conversationsLoading: false,
    editingConversationId: null,
    editingTitle: '',
    groupedConversations: () => [],
  },
);

const emit = defineEmits<{
  (e: 'cancelEditTitle'): void;
  (e: 'commitEditTitle'): void;
  (e: 'deleteConversation', conversationId: number): void;
  (e: 'selectConversation', conversationId: number): void;
  (e: 'startEditTitle', conversation: HistoryConversationItem): void;
  (e: 'startNewChat'): void;
  (e: 'update:conversationSearch', value: string): void;
  (e: 'update:editingTitle', value: string): void;
}>();
</script>

<template>
  <div class="history-pane-shell flex flex-1 flex-col overflow-hidden">
    <div class="history-pane-header shrink-0 px-3 py-2.5">
      <div class="mb-2 flex items-center justify-between">
        <span
          class="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
        >
          {{ $t('common.globalAiChat.history') }}
        </span>
        <button
          class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-primary transition-colors hover:bg-primary/10"
          @click="emit('startNewChat')"
        >
          <IconifyIcon icon="lucide:plus" class="size-3" />
          {{ $t('common.aiPanel.newChat') }}
        </button>
      </div>
      <Input
        v-if="conversationsCount > 3"
        :value="conversationSearch"
        :placeholder="$t('common.globalAiChat.searchHistory')"
        size="small"
        allow-clear
        class="history-pane-search !rounded-xl"
        @update:value="
          (value) => emit('update:conversationSearch', value ?? '')
        "
      >
        <template #prefix>
          <IconifyIcon
            icon="lucide:search"
            class="size-3 text-muted-foreground"
          />
        </template>
      </Input>
    </div>

    <div class="history-pane-scroll flex-1 overflow-y-auto px-3 pb-2.5">
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
          <div
            class="mb-1 px-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60"
          >
            {{ group.label }}
          </div>
          <div class="space-y-1">
            <div
              v-for="conv in group.items"
              :key="conv.id"
              class="history-conversation-item group relative flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2.5 transition-all duration-150"
              :class="
                activeConversationId === conv.id &&
                editingConversationId !== conv.id
                  ? 'history-conversation-item-active text-foreground ring-1 ring-primary/15'
                  : 'text-muted-foreground hover:bg-muted/72'
              "
              @click="
                editingConversationId !== conv.id &&
                emit('selectConversation', conv.id)
              "
              @dblclick.stop="emit('startEditTitle', conv)"
            >
              <div
                v-if="
                  activeConversationId === conv.id &&
                  editingConversationId !== conv.id
                "
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
                    :value="editingTitle"
                    size="small"
                    :placeholder="
                      $t('common.globalAiChat.conversationTitlePlaceholder')
                    "
                    class="!h-7 text-[13px]"
                    @update:value="
                      (value) => emit('update:editingTitle', value ?? '')
                    "
                    @blur="emit('commitEditTitle')"
                    @keydown.enter="emit('commitEditTitle')"
                    @keydown.esc="emit('cancelEditTitle')"
                    @click.stop
                  />
                </template>
                <template v-else>
                  <span
                    class="truncate text-[13px]"
                    :class="
                      activeConversationId === conv.id ? 'font-medium' : ''
                    "
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
                @click.stop="emit('deleteConversation', conv.id)"
              >
                <IconifyIcon icon="lucide:trash-2" class="size-3" />
              </button>
            </div>
          </div>
        </div>
      </Spin>
    </div>
  </div>
</template>

<style scoped>
.history-pane-shell,
.history-pane-header,
.history-pane-scroll {
  background: hsl(var(--background));
}

.history-pane-header {
  border-bottom: 1px solid hsl(var(--border) / 0.42);
}

.history-conversation-item {
  border: 1px solid transparent;
}

.history-conversation-item:hover {
  border-color: hsl(var(--border) / 0.36);
}

.history-conversation-item-active {
  border-color: hsl(var(--primary) / 0.14);
  background: hsl(var(--primary) / 0.06);
  box-shadow: 0 8px 16px -18px hsl(var(--primary) / 0.14);
}
</style>
