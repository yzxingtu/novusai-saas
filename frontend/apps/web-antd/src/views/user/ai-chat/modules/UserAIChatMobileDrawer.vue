<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Drawer, Input } from 'ant-design-vue';

import { $t } from '#/locales';
import { toAvatarDisplayUrl } from '#/utils/image';

import { useUserAIChatContext } from './ai-chat-context';
import UserAIChatConversationList from './UserAIChatConversationList.vue';

const { conversationSearch, mobileSidebarOpen, onSelectAgent, onStartNewChat, chat } =
  useUserAIChatContext();
const { agents, conversations, selectedAgentId } = chat;

function closeMobileSidebar() {
  mobileSidebarOpen.value = false;
}

function resolveAgentAvatar(avatar: null | string | undefined) {
  return avatar ? toAvatarDisplayUrl(avatar) : '';
}
</script>

<template>
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
      <div
        class="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
      >
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
          @click="
            onSelectAgent(agent.id);
            closeMobileSidebar();
          "
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
              :src="resolveAgentAvatar(agent.avatar)"
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
        <span
          class="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
        >
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
      <Input
        v-if="conversations.length > 3"
        v-model:value="conversationSearch"
        :placeholder="$t('common.globalAiChat.searchHistory')"
        size="small"
        allow-clear
        class="mb-2 !rounded-lg"
      >
        <template #prefix>
          <IconifyIcon
            icon="lucide:search"
            class="size-3 text-muted-foreground"
          />
        </template>
      </Input>
      <UserAIChatConversationList variant="mobile" />
    </div>
  </Drawer>
</template>
