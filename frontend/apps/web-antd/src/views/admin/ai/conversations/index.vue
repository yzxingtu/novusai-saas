<script lang="ts" setup>
/**
 * 平台端 AI 对话管理列表页面
 */
import type { AIConversationInfo } from '#/api/admin/ai';
import type { ConversationCallLogSummary } from '#/components/business/conversation-detail/ConversationDetail.vue';
import type { ApiRequestOptions } from '#/utils/request';

import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';

import { Avatar, Card, Descriptions, Tag } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getAIConversationDetailApi,
  getAIConversationListApi,
} from '#/api/admin/ai';
import { getAICallLogListApi } from '#/api/admin/ai-call-logs';
import ConversationDetail from '#/components/business/conversation-detail/ConversationDetail.vue';
import {
  createKeywordSearchPageOperation,
  createViewDetailPageOperation,
} from '#/composables';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

import AIPageHeroCard from '../_shared/AIPageHeroCard.vue';
import {
  formatCost,
  formatTokens,
  getStatusText,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'AdminAIConversations' });

const heroChips = computed(() => [
  {
    key: 'scope',
    icon: 'lucide:building-2',
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
    text: `${$t('admin.ai.conversation.tenantName')} / ${$t('admin.ai.conversation.user')} / ${$t('admin.ai.conversation.title')}`,
  },
  {
    key: 'cost',
    icon: 'lucide:wallet-cards',
    className: 'bg-background/90 text-foreground',
    text: `${$t('admin.ai.conversation.messageCount')} / ${$t('admin.ai.conversation.tokenCount')} / ${$t('admin.ai.conversation.cost')}`,
  },
  {
    key: 'detail',
    icon: 'lucide:file-search',
    className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
    text: `${$t('admin.ai.conversation.messageCount')} / ${$t('admin.ai.callLog.detail.title')}`,
  },
]);

const detailOpen = ref(false);
const detailId = ref<null | number>(null);
const conversationDetailApi = (id: number, ...args: unknown[]) =>
  getAIConversationDetailApi(id, args[0] as ApiRequestOptions | undefined);

function onViewDetail(row: AIConversationInfo) {
  detailId.value = row.id;
  detailOpen.value = true;
}

async function loadConversationCallLogs(
  conversationId: number,
): Promise<ConversationCallLogSummary[]> {
  const res = await getAICallLogListApi({
    'filter[conversation_id][eq]': conversationId,
    'page[size]': 100,
    sort: 'created_at',
  });
  return res.items as ConversationCallLogSummary[];
}

const { Grid, gridApi } = useCrudPage<AIConversationInfo>({
  api: {
    list: getAIConversationListApi,
    resource: '/admin/ai/conversations',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.ai.conversation',
  defaultSort: '-created_at',
  customActions: {
    detail: onViewDetail,
  },
  ai: {
    entityName: $t('admin.ai.conversation.name'),
    entityDescription: $t('admin.ai.conversation.pageDesc'),
    extra: [
      createKeywordSearchPageOperation({
        description:
          'Search conversations by title keyword / 按标题关键字搜索对话',
        keywordDescription: 'Conversation title keyword / 对话标题关键字',
        setKeyword: () => {},
        action: async (keyword) => {
          gridApi.formApi?.setValues({
            'filter[title][ilike]': keyword || undefined,
          });
          gridApi.reload({ page: 1 });
        },
        successMessage: (keyword) =>
          keyword
            ? $t('shared.pageOperation.msg.searchApplied', {
                fields: 'title',
              })
            : $t('shared.pageOperation.msg.searchCleared'),
      }),
      createViewDetailPageOperation({
        description:
          'Open the conversation detail drawer by ID / 按 ID 打开对话详情抽屉',
        idDescription: 'Conversation ID / 对话 ID',
        openDetail: async (id) => {
          detailId.value = id;
          detailOpen.value = true;
        },
      }),
    ],
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AIPageHeroCard
      :chips="heroChips"
      :description="$t('admin.ai.conversation.pageDesc')"
      icon="lucide:messages-square"
      icon-wrap-class="bg-primary/10 text-primary"
      :title="$t('admin.ai.conversation.title')"
    />
    <ConversationDetail
      v-model:open="detailOpen"
      :conversation-id="detailId"
      api-prefix="/admin"
      i18n-prefix="admin.ai.conversation"
      :get-detail-api="conversationDetailApi"
      :format-tokens="formatTokens"
      :format-cost="formatCost"
      :get-status-text="getStatusText"
      :load-call-logs="loadConversationCallLogs"
    >
      <template #extra-descriptions="{ detail }">
        <Descriptions.Item
          :label="$t('admin.ai.conversation.tenantName')"
          :span="1"
        >
          {{ detail.tenant_name || '-' }}
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.ai.conversation.user')" :span="1">
          <div v-if="detail.user_info" class="flex items-center gap-2">
            <Avatar
              v-if="detail.user_info.avatar"
              :src="toAvatarDisplayUrl(detail.user_info.avatar)"
              :size="24"
            />
            <Avatar
              v-else
              :size="24"
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
            <span>{{
              detail.user_info.nickname || detail.user_info.username
            }}</span>
          </div>
          <span v-else class="text-muted-foreground">-</span>
        </Descriptions.Item>
      </template>
    </ConversationDetail>

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 企业列 -->
        <template #tenant_cell="{ row }">
          <span v-if="row.tenant_name" class="text-foreground">{{
            row.tenant_name
          }}</span>
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

        <!-- 标题列 -->
        <template #title_cell="{ row }">
          <span v-if="row.title" class="text-foreground">{{ row.title }}</span>
          <span v-else class="italic text-muted-foreground">{{
            $t('common.noData')
          }}</span>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag
            :color="
              row.status === 'active'
                ? 'success'
                : row.status === 'archived'
                  ? 'default'
                  : 'warning'
            "
          >
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <!-- Tokens 列 -->
        <template #tokens_cell="{ row }">
          <span class="font-mono text-sm text-muted-foreground">
            {{ formatTokens(row.token_count) }}
          </span>
        </template>

        <!-- 费用列 -->
        <template #cost_cell="{ row }">
          <span
            class="font-mono text-sm"
            :class="row.cost > 0 ? 'text-foreground' : 'text-muted-foreground'"
          >
            {{ formatCost(row.cost) }}
          </span>
        </template>

        <!-- 创建时间列 -->
        <template #createdAt_cell="{ row }">
          <span class="text-muted-foreground">
            {{ formatDate(row.created_at) }}
          </span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
