<script lang="ts" setup>
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Input, Spin } from 'ant-design-vue';

import { $t } from '#/locales';

import { useUserAIChatContext } from './ai-chat-context';

const props = withDefaults(
  defineProps<{
    variant?: 'desktop' | 'mobile';
  }>(),
  { variant: 'desktop' },
);

const isDesktop = computed(() => props.variant === 'desktop');

const {
  groupedConversations,
  editingConversationId,
  editingTitle,
  onSelectConversation,
  onDeleteConversation,
  startEditTitle,
  commitEditTitle,
  cancelEditTitle,
  chat,
} = useUserAIChatContext();
const { activeConversationId, conversationsLoading } = chat;
</script>

<template>
  <Spin :spinning="conversationsLoading">
    <div
      v-if="groupedConversations.length === 0 && !conversationsLoading"
      class="py-6 text-center text-sm text-muted-foreground"
    >
      {{ $t('common.globalAiChat.noHistory') }}
    </div>
    <div v-for="group in groupedConversations" :key="group.label" class="mb-2">
      <div
        class="mb-1 text-[11px] font-medium text-muted-foreground/60"
        :class="isDesktop ? 'px-1 uppercase tracking-wider' : ''"
      >
        {{ group.label }}
      </div>
      <div class="space-y-0.5">
        <div
          v-for="conv in group.items"
          :key="conv.id"
          class="group relative flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 transition-all duration-150"
          :class="
            isDesktop
              ? activeConversationId === conv.id &&
                editingConversationId !== conv.id
                ? 'bg-primary/8 text-foreground shadow-sm shadow-primary/5 ring-1 ring-primary/15'
                : 'text-muted-foreground hover:bg-accent/50'
              : activeConversationId === conv.id &&
                  editingConversationId !== conv.id
                ? 'bg-primary/8 text-foreground'
                : 'text-muted-foreground hover:bg-accent/50'
          "
          @click="
            editingConversationId !== conv.id && onSelectConversation(conv.id)
          "
          @dblclick.stop="startEditTitle(conv)"
        >
          <div
            v-if="
              isDesktop &&
              activeConversationId === conv.id &&
              editingConversationId !== conv.id
            "
            class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r-full bg-primary"
          ></div>
          <template v-if="isDesktop">
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
              <IconifyIcon v-else icon="lucide:message-square" class="size-3" />
            </div>
            <div class="flex min-w-0 flex-1 flex-col">
              <template v-if="editingConversationId === conv.id">
                <Input
                  v-model:value="editingTitle"
                  size="small"
                  :placeholder="
                    $t('common.globalAiChat.conversationTitlePlaceholder')
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
              class="absolute right-2 flex size-5 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-focus-within:opacity-100 group-hover:opacity-100"
              :aria-label="$t('common.globalAiChat.deleteConversation')"
              @click.stop="onDeleteConversation(conv.id)"
            >
              <IconifyIcon icon="lucide:trash-2" class="size-3" />
            </button>
          </template>
          <template v-else>
            <IconifyIcon
              v-if="editingConversationId !== conv.id"
              icon="lucide:message-square"
              class="size-3.5 shrink-0"
            />
            <template v-if="editingConversationId === conv.id">
              <Input
                v-model:value="editingTitle"
                size="small"
                :placeholder="
                  $t('common.globalAiChat.conversationTitlePlaceholder')
                "
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
              class="ml-auto flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-100 transition-colors hover:bg-destructive/10 hover:text-destructive"
              :aria-label="$t('common.globalAiChat.deleteConversation')"
              @click.stop="onDeleteConversation(conv.id)"
            >
              <IconifyIcon icon="lucide:trash-2" class="size-3" />
            </button>
          </template>
        </div>
      </div>
    </div>
  </Spin>
</template>
