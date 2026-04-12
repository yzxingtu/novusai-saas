<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Input, Spin } from 'ant-design-vue';

import { $t } from '#/locales';

import { useUserAIChatContext } from './ai-chat-context';
import UserAIChatConversationList from './UserAIChatConversationList.vue';

const {
  conversationSearch,
  onSelectAgent,
  onStartNewChat,
  chat,
} = useUserAIChatContext();
const { agents, agentsLoading, selectedAgentId, conversations } = chat;
</script>

<template>
  <aside
    class="hidden w-[280px] shrink-0 flex-col border-r border-border/50 md:flex"
  >
    <!-- Agent Selector -->
    <div class="shrink-0 border-b border-border/40 p-3">
      <div class="mb-2 flex items-center justify-between">
        <span
          class="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
        >
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
          @click="onSelectAgent(agent.id)"
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
      <div class="flex-1 overflow-y-auto px-3 pb-2">
        <UserAIChatConversationList variant="desktop" />
      </div>
    </div>
  </aside>
</template>
