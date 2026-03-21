<script lang="ts" setup>
/**
 * 企业端对话管理列表页面
 */
import type { ConversationInfo } from '#/api/tenant/conversations';
import type { ApiRequestOptions } from '#/utils/request';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Avatar, Card, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getTenantAICallLogListApi } from '#/api/tenant/ai';
import {
  getConversationDetailApi,
  getConversationListApi,
} from '#/api/tenant/conversations';
import ConversationDetail from '#/components/business/conversation-detail/ConversationDetail.vue';
import type { ConversationCallLogSummary } from '#/components/business/conversation-detail/ConversationDetail.vue';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

import {
  formatCost,
  formatTokenCount,
  getStatusText,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'TenantConversationList' });

const detailOpen = ref(false);
const detailId = ref<null | number>(null);
const conversationDetailApi = (
  id: number,
  ...args: unknown[]
) => getConversationDetailApi(
  id,
  args[0] as Record<string, unknown> | undefined,
  args[1] as ApiRequestOptions | undefined,
);

function onViewDetail(row: ConversationInfo) {
  detailId.value = row.id;
  detailOpen.value = true;
}

async function loadConversationCallLogs(
  conversationId: number,
): Promise<ConversationCallLogSummary[]> {
  const res = await getTenantAICallLogListApi({
    'filter[conversation_id][eq]': conversationId,
    'page[size]': 100,
    sort: 'created_at',
  });
  return res.items as ConversationCallLogSummary[];
}

const { Grid } = useCrudPage<ConversationInfo>({
  api: {
    list: getConversationListApi,
    resource: '/tenant/ai/conversations',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'tenant.ai.conversation',
  defaultSort: '-created_at',
  customActions: {
    detail: onViewDetail,
  },
  ai: {
    pageKey: 'tenant.ai.conversations',
    entityName: $t('tenant.ai.conversation.name'),
    entityDescription: $t('tenant.ai.conversation.pageDesc'),
    extra: [
      {
        name: 'view_detail',
        label: $t('shared.pageOperation.viewDetail'),
        description:
          'Open the conversation detail drawer by ID / 按 ID 打开对话详情抽屉',
        readonly: true,
        params: {
          id: {
            type: 'number',
            description: 'Conversation ID / 对话 ID',
            required: true,
          },
        },
        handler: async (params) => {
          const id = Number(params.id);
          if (!Number.isFinite(id) || id <= 0) {
            return {
              success: false,
              message: $t('shared.pageOperation.msg.missingIdParam'),
            };
          }
          detailId.value = id;
          detailOpen.value = true;
          return {
            success: true,
            message: $t('shared.pageOperation.msg.detailOpened', { id }),
          };
        },
      },
    ],
  },
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('tenant.ai.conversation.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 详情抽屉 -->
    <ConversationDetail
      v-model:open="detailOpen"
      :conversation-id="detailId"
      api-prefix="/tenant"
      i18n-prefix="tenant.ai.conversation"
      :get-detail-api="conversationDetailApi"
      :format-tokens="formatTokenCount"
      :format-cost="formatCost"
      :get-status-text="getStatusText"
      :load-call-logs="loadConversationCallLogs"
    />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 标题列 -->
        <template #title_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon
              icon="lucide:message-square"
              class="size-3.5 text-muted-foreground"
            />
            <span class="truncate">{{
              row.title || $t('tenant.ai.conversation.untitled')
            }}</span>
          </div>
        </template>

        <!-- 智能体名称列 -->
        <template #agentName_cell="{ row }">
          <div v-if="row.agent_name" class="flex items-center gap-1.5">
            <IconifyIcon
              icon="lucide:bot"
              class="size-3.5 text-muted-foreground"
            />
            <span>{{ row.agent_name }}</span>
          </div>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 用户列 -->
        <template #user_cell="{ row }">
          <div v-if="row.user_info" class="flex items-center gap-2">
            <Avatar
              v-if="row.user_info.avatar"
              :src="toAvatarDisplayUrl(row.user_info.avatar)"
              :size="28"
            />
            <Avatar
              v-else
              :size="28"
              class="flex-shrink-0 bg-primary/10 text-xs text-primary"
            >
              {{
                (
                  row.user_info.nickname ||
                  row.user_info.username ||
                  '?'
                ).charAt(0)
              }}
            </Avatar>
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm text-foreground">
                {{ row.user_info.nickname || row.user_info.username }}
              </div>
              <div
                v-if="row.user_info.nickname"
                class="truncate text-xs text-muted-foreground"
              >
                {{ row.user_info.username }}
              </div>
            </div>
          </div>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag :color="row.status === 'active' ? 'success' : 'default'">
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <!-- Token 数量列 -->
        <template #tokenCount_cell="{ row }">
          <span class="text-muted-foreground">
            {{ formatTokenCount(row.token_count) }}
          </span>
        </template>

        <!-- 费用列 -->
        <template #cost_cell="{ row }">
          <span class="text-muted-foreground">
            {{ formatCost(row.cost) }}
          </span>
        </template>

        <!-- 创建时间列 -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatDate(row.created_at) }}
            </span>
          </Tooltip>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
