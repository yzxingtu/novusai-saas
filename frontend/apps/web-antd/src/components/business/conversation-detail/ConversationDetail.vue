<script lang="ts" setup>
/**
 * 对话详情抽屉（共享组件）
 *
 * 展示对话基本信息 + 消息时间线。
 * 通过 props 注入 API 函数和 i18n 前缀，适配 admin/tenant 两端。
 * 通过 #extra-descriptions slot 允许各端添加自定义描述字段。
 */
import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Avatar, Descriptions, Drawer, Empty, Spin, Tag, Timeline } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

export interface ConversationMessageItem {
  id: number;
  role: string;
  content: string | null;
  sequence: number;
  token_count: number | null;
  tool_calls: unknown[] | null;
  created_at: string;
}

export interface ConversationUserInfo {
  id: number;
  username: string;
  nickname: string | null;
  avatar: string | null;
}

export interface ConversationDetailData {
  id: number;
  title: string | null;
  status: string;
  token_count: number;
  cost: number;
  agent_name: string | null;
  agent_avatar?: string | null;
  tenant_name?: string | null;
  user_info?: ConversationUserInfo | null;
  message_count: number;
  message_list: ConversationMessageItem[];
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
}

const props = defineProps<{
  conversationId: null | number;
  open: boolean;
  /** i18n 前缀，如 'admin.ai.conversation' 或 'tenant.ai.conversation' */
  i18nPrefix: string;
  /** 获取对话详情的 API 函数 */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getDetailApi: (...args: any[]) => Promise<any>;
  /** 格式化 token 数量的函数 */
  formatTokens: (count: number | null | undefined) => string;
  /** 格式化费用的函数 */
  formatCost: (cost: number | null | undefined) => string;
  /** 获取状态文本的函数 */
  getStatusText: (status: string) => string;
}>();

const emits = defineEmits<{ 'update:open': [value: boolean] }>();

const loading = ref(false);
const detail = ref<ConversationDetailData | null>(null);

watch(
  () => props.conversationId,
  async (id) => {
    if (id) {
      loading.value = true;
      try {
        detail.value = await props.getDetailApi(id) as ConversationDetailData;
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

const messages = computed<ConversationMessageItem[]>(() => {
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

defineExpose({ detail });
</script>

<template>
  <Drawer
    :open="open"
    :title="$t(`${i18nPrefix}.viewDetail`)"
    width="700"
    @close="onClose"
  >
    <Spin :spinning="loading">
      <template v-if="detail">
        <!-- 基本信息 -->
        <Descriptions bordered :column="2" size="small">
          <Descriptions.Item :label="$t(`${i18nPrefix}.conversationTitle`)" :span="2">
            {{ detail.title || '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t(`${i18nPrefix}.agentName`)" :span="1">
            {{ detail.agent_name || '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t(`${i18nPrefix}.status`)" :span="1">
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

          <!-- 允许各端插入自定义描述字段 -->
          <slot name="extra-descriptions" :detail="detail" />

          <Descriptions.Item :label="$t(`${i18nPrefix}.tokenCount`)" :span="1">
            {{ formatTokens(detail.token_count) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t(`${i18nPrefix}.cost`)" :span="1">
            {{ formatCost(detail.cost) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t(`${i18nPrefix}.createdAt`)" :span="2">
            {{ formatDate(detail.created_at) }}
          </Descriptions.Item>
        </Descriptions>

        <!-- 消息时间线 -->
        <div class="mt-6">
          <h4 class="mb-3 font-medium text-foreground">
            <IconifyIcon icon="lucide:messages-square" class="mr-1 inline size-4" />
            {{ $t(`${i18nPrefix}.messageList`) }}
          </h4>

          <Empty v-if="messages.length === 0" />

          <Timeline v-else>
            <Timeline.Item
              v-for="msg in messages"
              :key="msg.id"
              :color="getRoleColor(msg.role)"
            >
              <div class="mb-1 flex items-center gap-2">
                <!-- user message: show user avatar + name -->
                <template v-if="msg.role === 'user' && detail?.user_info">
                  <Avatar
                    v-if="detail.user_info.avatar"
                    :src="toAvatarDisplayUrl(detail.user_info.avatar)"
                    :size="22"
                  />
                  <Avatar v-else :size="22" class="bg-primary/10 text-primary text-xs">
                    {{ (detail.user_info.nickname || detail.user_info.username || '?').charAt(0) }}
                  </Avatar>
                  <span class="text-sm font-medium text-foreground">
                    {{ detail.user_info.nickname || detail.user_info.username }}
                  </span>
                </template>
                <!-- assistant message: show agent avatar + name -->
                <template v-else-if="msg.role === 'assistant' && detail?.agent_name">
                  <Avatar
                    v-if="detail.agent_avatar"
                    :src="toAvatarDisplayUrl(detail.agent_avatar)"
                    :size="22"
                  />
                  <Avatar v-else :size="22" class="bg-success/10 text-success text-xs">
                    {{ (detail.agent_name || '?').charAt(0) }}
                  </Avatar>
                  <span class="text-sm font-medium text-foreground">
                    {{ detail.agent_name }}
                  </span>
                </template>
                <!-- other roles: fallback to tag -->
                <template v-else>
                  <Tag :color="getRoleColor(msg.role)" size="small">
                    <IconifyIcon :icon="getRoleIcon(msg.role)" class="mr-0.5 inline size-3" />
                    {{ msg.role }}
                  </Tag>
                </template>
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
