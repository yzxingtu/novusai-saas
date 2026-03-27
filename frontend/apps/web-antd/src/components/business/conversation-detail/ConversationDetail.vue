<script lang="ts" setup>
import type { RagSource } from '#/components/business/ai-chat-panel/types';

/**
 * Conversation Detail Drawer (Shared Component)
 * 对话详情抽屉（共享组件）
 *
 * Displays conversation basic info + message timeline.
 * 展示对话基本信息 + 消息时间线。
 * Injects API functions and i18n prefix via props, adapts to admin/tenant endpoints.
 * 通过 props 注入 API 函数和 i18n 前缀，适配 admin/tenant 两端。
 * Allows each endpoint to add custom description fields via #extra-descriptions slot.
 * 通过 #extra-descriptions slot 允许各端添加自定义描述字段。
 */
import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Avatar,
  Descriptions,
  Drawer,
  Empty,
  Spin,
  Tabs,
  Tag,
  Timeline,
} from 'ant-design-vue';

import { AgentProfilePopover } from '#/components/business/agent-profile-popover';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

/** Summary row for the model-call trace tab / 「模型调用」Tab 行 */
export interface ConversationCallLogSummary {
  id: number;
  created_at: string;
  model_name?: null | string;
  total_tokens: number;
  latency_ms: null | number;
  status: string;
  request_type?: string;
  error_message?: null | string;
}

export interface ConversationMessageItem {
  agent_avatar?: null | string;
  agent_id?: null | number;
  agent_name?: null | string;
  id: number;
  role: string;
  content: null | string;
  metadata?: null | {
    completion_reason?: string;
    interrupted?: boolean;
    memory_updated?: boolean;
    partial?: boolean;
    rag_sources?: RagSource[];
    route_source?: string;
    thinking_content?: string;
    tool_error?: string;
    tool_success?: boolean;
  };
  sequence: number;
  token_count: null | number;
  tool_calls: null | unknown[];
  tool_call_id?: null | string;
  tool_name?: null | string;
  created_at: string;
}

export interface ConversationUserInfo {
  id: number;
  username: string;
  nickname: null | string;
  avatar: null | string;
}

export interface ConversationDetailData {
  id: number;
  title: null | string;
  status: string;
  token_count: number;
  cost: number;
  agent_id?: null | number;
  agent_name: null | string;
  agent_avatar?: null | string;
  tenant_name?: null | string;
  user_info?: ConversationUserInfo | null;
  message_count: number;
  message_list: ConversationMessageItem[];
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
}

const props = defineProps<{
  /** API prefix: '/admin' or '/tenant', for loading agent skill packages / API 前缀，用于加载智能体技能包 */
  apiPrefix?: string;
  conversationId: null | number;
  /** Function to format cost / 格式化费用的函数 */
  formatCost: (cost: null | number | undefined) => string;
  /** Function to format token count / 格式化 token 数量的函数 */
  formatTokens: (count: null | number | undefined) => string;
  /** API function to get conversation detail / 获取对话详情的 API 函数 */
  getDetailApi: (id: number, ...args: unknown[]) => Promise<unknown>;
  /** Function to get status text / 获取状态文本的函数 */
  getStatusText: (status: string) => string;
  /** i18n prefix, e.g. 'admin.ai.conversation' or 'tenant.ai.conversation' / i18n 前缀 */
  i18nPrefix: string;
  /** Optional: load AI call logs for this conversation (model trace) / 可选：按对话加载模型调用记录 */
  loadCallLogs?: (
    conversationId: number,
  ) => Promise<ConversationCallLogSummary[]>;
  open: boolean;
}>();

const emits = defineEmits<{ 'update:open': [value: boolean] }>();

const loading = ref(false);
const detail = ref<ConversationDetailData | null>(null);
const activeDetailTab = ref('messages');
const callLogs = ref<ConversationCallLogSummary[]>([]);
const loadingCallLogs = ref(false);

watch(
  () => props.conversationId,
  async (id) => {
    activeDetailTab.value = 'messages';
    if (id) {
      loading.value = true;
      try {
        detail.value = (await props.getDetailApi(id)) as ConversationDetailData;
      } catch {
        detail.value = null;
      } finally {
        loading.value = false;
      }
    }
  },
);

watch(
  () => [props.open, props.conversationId, props.loadCallLogs] as const,
  async ([isOpen, convId, loader]) => {
    callLogs.value = [];
    if (!isOpen || !convId || !loader) {
      return;
    }
    loadingCallLogs.value = true;
    try {
      callLogs.value = await loader(convId);
    } catch {
      callLogs.value = [];
    } finally {
      loadingCallLogs.value = false;
    }
  },
);

function onClose() {
  emits('update:open', false);
}

const messages = computed<ConversationMessageItem[]>(() => {
  if (!detail.value?.message_list) return [];
  return detail.value.message_list.toSorted((a, b) => a.sequence - b.sequence);
});

function getRoleColor(role: string): string {
  switch (role) {
    case 'assistant': {
      return 'green';
    }
    case 'system': {
      return 'orange';
    }
    case 'tool': {
      return 'purple';
    }
    case 'user': {
      return 'blue';
    }
    default: {
      return 'default';
    }
  }
}

function getRoleIcon(role: string): string {
  switch (role) {
    case 'assistant': {
      return 'lucide:bot';
    }
    case 'system': {
      return 'lucide:settings';
    }
    case 'tool': {
      return 'lucide:wrench';
    }
    case 'user': {
      return 'lucide:user';
    }
    default: {
      return 'lucide:message-circle';
    }
  }
}

function isMentionRoute(msg: ConversationMessageItem): boolean {
  return msg.metadata?.route_source === 'mention';
}

function getToolCallDisplayName(tc: unknown): string {
  if (!tc || typeof tc !== 'object') {
    return '?';
  }
  const t = tc as Record<string, unknown>;
  const fn = t.function as Record<string, unknown> | undefined;
  if (fn?.name) {
    return String(fn.name);
  }
  return String(t.name ?? 'tool');
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
        <!-- Basic info / 基本信息 -->
        <Descriptions bordered :column="2" size="small">
          <Descriptions.Item
            :label="$t(`${i18nPrefix}.conversationTitle`)"
            :span="2"
          >
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

          <!-- Allow each endpoint to insert custom description fields / 允许各端插入自定义描述字段 -->
          <slot name="extra-descriptions" :detail="detail"></slot>

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

        <div class="mt-6">
          <Tabs v-model:active-key="activeDetailTab">
            <Tabs.TabPane key="messages" :tab="$t(`${i18nPrefix}.tabMessages`)">
              <Empty v-if="messages.length === 0" />

              <Timeline v-else>
                <Timeline.Item
                  v-for="msg in messages"
                  :key="msg.id"
                  :color="getRoleColor(msg.role)"
                >
                  <div class="mb-1 flex flex-wrap items-center gap-2">
                    <template v-if="msg.role === 'user' && detail?.user_info">
                      <Avatar
                        v-if="detail.user_info.avatar"
                        :src="toAvatarDisplayUrl(detail.user_info.avatar)"
                        :size="22"
                      />
                      <Avatar
                        v-else
                        :size="22"
                        class="bg-primary/10 text-xs text-primary"
                      >
                        {{
                          (
                            detail.user_info.nickname ||
                            detail.user_info.username ||
                            '?'
                          ).charAt(0)
                        }}
                      </Avatar>
                      <span class="text-sm font-medium text-foreground">
                        {{
                          detail.user_info.nickname || detail.user_info.username
                        }}
                      </span>
                    </template>
                    <template
                      v-else-if="
                        msg.role === 'assistant' &&
                        (msg.agent_name || detail?.agent_name)
                      "
                    >
                      <Tag v-if="isMentionRoute(msg)" color="blue">
                        @ {{ msg.agent_name || detail?.agent_name }}
                      </Tag>
                      <AgentProfilePopover
                        :agent-id="msg.agent_id ?? detail?.agent_id"
                        :agent-avatar="msg.agent_avatar ?? detail?.agent_avatar"
                        :agent-name="msg.agent_name ?? detail?.agent_name"
                        :api-prefix="props.apiPrefix"
                        size="sm"
                      />
                      <span class="text-sm font-medium text-foreground">
                        {{ msg.agent_name || detail?.agent_name }}
                      </span>
                    </template>
                    <template v-else>
                      <Tag :color="getRoleColor(msg.role)" size="small">
                        <IconifyIcon
                          :icon="getRoleIcon(msg.role)"
                          class="mr-0.5 inline size-3"
                        />
                        {{ msg.role }}
                      </Tag>
                      <span
                        v-if="msg.role === 'tool' && msg.tool_name"
                        class="text-xs text-muted-foreground"
                      >
                        {{ msg.tool_name }}
                      </span>
                    </template>
                    <span class="text-xs text-muted-foreground">
                      #{{ msg.sequence }} · {{ formatDate(msg.created_at) }}
                    </span>
                    <span
                      v-if="msg.token_count"
                      class="text-xs text-muted-foreground"
                    >
                      · {{ formatTokens(msg.token_count) }} tokens
                    </span>
                    <Tag
                      v-if="
                        msg.role === 'tool' &&
                        msg.metadata &&
                        msg.metadata.tool_success === false
                      "
                      color="error"
                      class="text-[10px]"
                    >
                      {{ $t(`${i18nPrefix}.toolFailed`) }}
                    </Tag>
                    <Tag
                      v-else-if="msg.role === 'tool'"
                      color="success"
                      class="text-[10px]"
                    >
                      {{ $t(`${i18nPrefix}.toolOk`) }}
                    </Tag>
                  </div>

                  <details
                    v-if="msg.metadata?.thinking_content"
                    class="mb-2 rounded-md border border-border/40 bg-muted/30 text-xs"
                  >
                    <summary
                      class="cursor-pointer px-2 py-1 font-medium text-muted-foreground"
                    >
                      {{ $t(`${i18nPrefix}.thinkingBlock`) }}
                    </summary>
                    <pre
                      class="max-h-40 overflow-auto whitespace-pre-wrap p-2 text-[11px]"
                      >{{ msg.metadata.thinking_content }}</pre
                    >
                  </details>

                  <div
                    v-if="msg.metadata?.rag_sources?.length"
                    class="mb-2 rounded-md border border-amber-500/25 bg-amber-500/5 p-2 text-xs"
                  >
                    <div
                      class="mb-1 font-medium text-amber-800 dark:text-amber-200"
                    >
                      {{ $t(`${i18nPrefix}.ragRefs`) }}
                    </div>
                    <ul
                      class="list-inside list-disc space-y-0.5 text-muted-foreground"
                    >
                      <li
                        v-for="(rs, ri) in msg.metadata.rag_sources"
                        :key="ri"
                      >
                        <span class="font-medium text-foreground">{{
                          rs.knowledge_base_name ||
                          (rs.knowledge_base_id != null
                            ? `KB#${rs.knowledge_base_id}`
                            : '—')
                        }}</span>
                        · {{ rs.doc_name }}
                      </li>
                    </ul>
                  </div>

                  <div
                    v-if="msg.content && msg.content.trim()"
                    class="whitespace-pre-wrap rounded-lg bg-accent p-3 text-sm"
                  >
                    {{ msg.content }}
                  </div>

                  <div
                    v-if="msg.tool_calls && msg.tool_calls.length > 0"
                    class="mt-2 space-y-1"
                  >
                    <div class="text-[11px] font-medium text-muted-foreground">
                      {{ $t(`${i18nPrefix}.toolCalls`) }}
                    </div>
                    <details
                      v-for="(tc, ti) in msg.tool_calls"
                      :key="ti"
                      class="rounded border border-border/30 bg-background/80 text-xs"
                    >
                      <summary
                        class="cursor-pointer px-2 py-1.5 font-medium text-foreground hover:bg-accent/50"
                      >
                        {{ getToolCallDisplayName(tc) }}
                      </summary>
                      <pre
                        class="max-h-36 overflow-auto border-t border-border/20 p-2 text-[11px] text-muted-foreground"
                        >{{ JSON.stringify(tc, null, 2) }}</pre
                      >
                    </details>
                  </div>
                </Timeline.Item>
              </Timeline>
            </Tabs.TabPane>

            <Tabs.TabPane
              v-if="loadCallLogs"
              key="calls"
              :tab="$t(`${i18nPrefix}.tabModelCalls`)"
            >
              <Spin :spinning="loadingCallLogs">
                <Empty
                  v-if="!loadingCallLogs && callLogs.length === 0"
                  :description="$t(`${i18nPrefix}.modelCallsEmpty`)"
                />
                <ul v-else class="space-y-2">
                  <li
                    v-for="log in callLogs"
                    :key="log.id"
                    class="rounded-lg border border-border/40 bg-accent/30 p-3 text-sm"
                  >
                    <div class="flex flex-wrap items-center gap-2">
                      <Tag
                        :color="log.status === 'success' ? 'success' : 'error'"
                        class="text-[10px]"
                      >
                        {{ log.status }}
                      </Tag>
                      <span class="font-medium">{{
                        log.model_name || '—'
                      }}</span>
                      <span class="text-xs text-muted-foreground">
                        {{ formatDate(log.created_at) }}
                      </span>
                    </div>
                    <div class="mt-1 text-xs text-muted-foreground">
                      {{ $t(`${i18nPrefix}.callLogTokens`) }}:
                      {{ formatTokens(log.total_tokens) }}
                      <template v-if="log.latency_ms != null">
                        · {{ $t(`${i18nPrefix}.callLogLatency`) }}:
                        {{ log.latency_ms }}ms
                      </template>
                      <template v-if="log.request_type">
                        · {{ log.request_type }}
                      </template>
                    </div>
                    <div
                      v-if="log.error_message"
                      class="mt-1 text-xs text-destructive"
                    >
                      {{ log.error_message }}
                    </div>
                  </li>
                </ul>
              </Spin>
            </Tabs.TabPane>
          </Tabs>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
