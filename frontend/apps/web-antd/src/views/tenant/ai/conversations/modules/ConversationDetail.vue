<script lang="ts" setup>
defineOptions({ name: 'TenantConversationDetail' });
/**
 * 对话详情抽屉 — 展示对话基本信息 + 消息列表
 */
import type { ConversationDetailInfo, ConversationMessageInfo } from '#/api/tenant/conversations';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Descriptions, Drawer, Empty, Spin, Tag, Timeline } from 'ant-design-vue';

import { getConversationDetailApi } from '#/api/tenant/conversations';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { formatCost, formatTokenCount, getStatusText } from '../data';

const props = defineProps<{
  conversationId: null | number;
  open: boolean;
}>();

const emits = defineEmits<{ 'update:open': [value: boolean] }>();

const loading = ref(false);
const detail = ref<ConversationDetailInfo | null>(null);

watch(
  () => props.conversationId,
  async (id) => {
    if (id) {
      loading.value = true;
      try {
        detail.value = await getConversationDetailApi(id);
      } catch {
        detail.value = null;
      } finally {
        loading.value = false;
      }
    }
  },
);

function onClose() {
  emits('update:open', false);
}

const messages = computed<ConversationMessageInfo[]>(() => {
  if (!detail.value?.message_list) return [];
  return [...detail.value.message_list].sort((a, b) => a.sequence - b.sequence);
});

function getRoleColor(role: string): string {
  switch (role) {
    case 'user': return 'blue';
    case 'assistant': return 'green';
    case 'system': return 'orange';
    case 'tool': return 'purple';
    default: return 'default';
  }
}

function getRoleIcon(role: string): string {
  switch (role) {
    case 'user': return 'lucide:user';
    case 'assistant': return 'lucide:bot';
    case 'system': return 'lucide:settings';
    case 'tool': return 'lucide:wrench';
    default: return 'lucide:message-circle';
  }
}
</script>

<template>
  <Drawer
    :open="open"
    :title="$t('tenant.ai.conversation.detailTitle')"
    width="700"
    @close="onClose"
  >
    <Spin :spinning="loading">
      <template v-if="detail">
        <!-- 基本信息 -->
        <Descriptions bordered :column="2" size="small">
          <Descriptions.Item :label="$t('tenant.ai.conversation.title')" :span="2">
            {{ detail.title || $t('tenant.ai.conversation.untitled') }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.conversation.agentName')" :span="1">
            {{ detail.agent_name || '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.conversation.status')" :span="1">
            <Tag :color="detail.status === 'active' ? 'success' : 'default'">
              {{ getStatusText(detail.status) }}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.conversation.tokenCount')" :span="1">
            {{ formatTokenCount(detail.token_count) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.conversation.cost')" :span="1">
            {{ formatCost(detail.cost) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.conversation.messageCount')" :span="1">
            {{ detail.message_count }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.conversation.createdAt')" :span="1">
            {{ formatDate(detail.created_at) }}
          </Descriptions.Item>
        </Descriptions>

        <!-- 消息时间线 -->
        <div class="mt-6">
          <h4 class="mb-3 font-medium text-foreground">
            <IconifyIcon icon="lucide:messages-square" class="mr-1 inline size-4" />
            {{ $t('tenant.ai.conversation.messageList') }}
          </h4>

          <Empty v-if="messages.length === 0" />

          <Timeline v-else>
            <Timeline.Item
              v-for="msg in messages"
              :key="msg.id"
              :color="getRoleColor(msg.role)"
            >
              <div class="mb-1 flex items-center gap-2">
                <Tag :color="getRoleColor(msg.role)" size="small">
                  <IconifyIcon :icon="getRoleIcon(msg.role)" class="mr-0.5 inline size-3" />
                  {{ msg.role }}
                </Tag>
                <span class="text-xs text-muted-foreground">
                  #{{ msg.sequence }} · {{ formatDate(msg.created_at) }}
                </span>
                <span v-if="msg.token_count" class="text-xs text-muted-foreground">
                  · {{ formatTokenCount(msg.token_count) }} tokens
                </span>
              </div>
              <div class="rounded-lg bg-accent p-3 text-sm whitespace-pre-wrap">
                {{ msg.content || '-' }}
              </div>
              <!-- tool_calls 展示 -->
              <div v-if="msg.tool_calls && msg.tool_calls.length > 0" class="mt-1">
                <pre class="max-h-[150px] overflow-auto rounded bg-accent/50 p-2 text-xs">{{ JSON.stringify(msg.tool_calls, null, 2) }}</pre>
              </div>
            </Timeline.Item>
          </Timeline>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
