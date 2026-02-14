<script lang="ts" setup>
defineOptions({ name: 'AdminConversationDetail' });
/**
 * 平台端对话详情抽屉 — 展示对话基本信息 + 消息列表
 */
import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Descriptions, Drawer, Empty, Spin, Tag, Timeline } from 'ant-design-vue';

import { getAIConversationDetailApi } from '#/api/admin/ai';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { formatCost, formatTokens, getStatusText } from '../data';

interface ConversationMessage {
  id: number;
  role: string;
  content: string | null;
  sequence: number;
  token_count: number | null;
  tool_calls: unknown[] | null;
  created_at: string;
}

interface ConversationDetail {
  id: number;
  tenant_id: number;
  agent_id: number;
  user_id: number | null;
  title: string | null;
  status: string;
  token_count: number;
  cost: number;
  agent_name: string | null;
  message_count: number;
  message_list: ConversationMessage[];
  created_at: string;
  updated_at: string;
}

const props = defineProps<{
  conversationId: null | number;
  open: boolean;
}>();

const emits = defineEmits<{ 'update:open': [value: boolean] }>();

const loading = ref(false);
const detail = ref<ConversationDetail | null>(null);

watch(
  () => props.conversationId,
  async (id) => {
    if (id) {
      loading.value = true;
      try {
        detail.value = (await getAIConversationDetailApi(id)) as unknown as ConversationDetail;
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

const messages = computed<ConversationMessage[]>(() => {
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
    :title="$t('admin.ai.conversation.viewDetail')"
    width="700"
    @close="onClose"
  >
    <Spin :spinning="loading">
      <template v-if="detail">
        <!-- 基本信息 -->
        <Descriptions bordered :column="2" size="small">
          <Descriptions.Item :label="$t('admin.ai.conversation.conversationTitle')" :span="2">
            {{ detail.title || '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.conversation.agentName')" :span="1">
            {{ detail.agent_name || '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.conversation.status')" :span="1">
            <Tag
              :color="
                detail.status === 'active'
                  ? 'success'
                  : detail.status === 'archived'
                    ? 'default'
                    : 'warning'
              "
            >
              {{ getStatusText(detail.status) }}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.conversation.tenantId')" :span="1">
            {{ detail.tenant_id }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.conversation.userId')" :span="1">
            {{ detail.user_id ?? '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.conversation.tokenCount')" :span="1">
            {{ formatTokens(detail.token_count) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.conversation.cost')" :span="1">
            {{ formatCost(detail.cost) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.conversation.createdAt')" :span="2">
            {{ formatDate(detail.created_at) }}
          </Descriptions.Item>
        </Descriptions>

        <!-- 消息时间线 -->
        <div class="mt-6">
          <h4 class="mb-3 font-medium text-foreground">
            <IconifyIcon icon="lucide:messages-square" class="mr-1 inline size-4" />
            {{ $t('admin.ai.conversation.messageList') }}
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
                  · {{ formatTokens(msg.token_count) }} tokens
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
