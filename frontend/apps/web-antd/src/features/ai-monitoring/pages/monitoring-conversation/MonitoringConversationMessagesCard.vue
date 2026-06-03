<script lang="ts" setup>
import type {
  MonitoringConversationDetail,
  MonitoringConversationMessage,
  MonitoringScope,
} from '../../api';

import type { TurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import type { AgentItem, ChatMessage } from '#/types/ai-chat';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Card, Empty, Tag, Tooltip } from 'ant-design-vue';

import { buildTurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import ChatMessageItem from '#/components/business/ai-chat-panel/ChatMessageItem.vue';
import { $t } from '#/locales';
import { formatDate, formatTimeOnly } from '#/utils/common';

import { formatTokens, roleColor } from './helpers';
import { toMonitoringChatMessage } from './monitoring-chat-message-adapter';

defineOptions({ name: 'MonitoringConversationMessagesCard' });

const props = defineProps<{
  i18nPrefix: string;
  messages: MonitoringConversationDetail['message_list'];
  scope: MonitoringScope;
}>();

const apiPrefix = computed(() =>
  props.scope === 'admin' ? '/admin' : '/tenant',
);

const normalizedMessages = computed<
  Array<{
    chatMessage: ChatMessage;
    kernelState: TurnFlowState;
    original: MonitoringConversationMessage;
  }>
>(() =>
  props.messages.map((message) => {
    const chatMessage = toMonitoringChatMessage(message);
    return {
      chatMessage,
      kernelState: buildTurnFlowState(chatMessage),
      original: message,
    };
  }),
);

const monitoringAgents = computed<AgentItem[]>(() => {
  const dedup = new Map<number, AgentItem>();
  for (const item of normalizedMessages.value) {
    const message = item.chatMessage;
    if (!message.agent_id || dedup.has(message.agent_id)) {
      continue;
    }
    dedup.set(message.agent_id, {
      id: message.agent_id,
      tenant_id: 0,
      name: message.agent_name || `Agent #${message.agent_id}`,
      description: null,
      avatar: message.agent_avatar || null,
      status: 'published',
    });
  }
  return [...dedup.values()];
});

function handleCopy(content: string) {
  if (navigator?.clipboard?.writeText) {
    void navigator.clipboard.writeText(content);
  }
}
</script>

<template>
  <Card class="monitoring-card" :bordered="false">
    <template #title>
      <div class="monitoring-card__title">
        <IconifyIcon class="size-4" icon="lucide:messages-square" />
        <span>{{ $t(`${i18nPrefix}.tabMessages`) }}</span>
        <Tag color="blue">
          {{ formatTokens(messages.length) }}
        </Tag>
      </div>
    </template>

    <Empty v-if="messages.length === 0" />

    <div v-else class="monitoring-scroll-area space-y-3">
      <div
        v-for="(item, index) in normalizedMessages"
        :key="item.original.id"
        class="monitoring-message-item"
      >
        <div class="monitoring-message-head">
          <Tag :color="roleColor(item.original.role)">
            {{ item.original.role }}
          </Tag>
          <span class="text-xs text-muted-foreground">
            #{{ item.original.sequence }}
          </span>
          <Tooltip :title="formatDate(item.original.created_at)">
            <span class="text-xs text-muted-foreground">
              {{ formatTimeOnly(item.original.created_at) }}
            </span>
          </Tooltip>
          <span
            v-if="item.original.token_count"
            class="text-xs text-muted-foreground"
          >
            {{ formatTokens(item.original.token_count) }}
          </span>
          <Tag v-if="item.original.tool_name" color="purple">
            {{ item.original.tool_name }}
          </Tag>
        </div>

        <div class="mt-2 space-y-1.5">
          <ChatMessageItem
            :msg="item.chatMessage"
            :index="index"
            :api-prefix="apiPrefix"
            :agents="monitoringAgents"
            :kernel-state="item.kernelState"
            :selected-agent="null"
            compact
            @copy="handleCopy"
            @confirm="() => undefined"
            @reject="() => undefined"
            @consent-confirm="() => undefined"
            @consent-reject="() => undefined"
            @open-url="() => undefined"
            @action-click="() => undefined"
            @regenerate="() => undefined"
            @edit="() => undefined"
            @retry="() => undefined"
          />
          <div
            v-if="
              !item.chatMessage.content && item.chatMessage.role !== 'assistant'
            "
            class="text-xs text-muted-foreground"
          >
            -
          </div>
        </div>
      </div>
    </div>
  </Card>
</template>
