<script lang="ts" setup>
/**
 * 平台端 AI 对话管理列表页面
 */
import type { AIConversationInfo } from '#/api/admin/ai';

import { onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';

import { Avatar, Card, Descriptions, Tag } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getAIConversationDetailApi,
  getAIConversationListApi,
} from '#/api/admin/ai';
import ConversationDetail from '#/components/business/conversation-detail/ConversationDetail.vue';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

import {
  formatCost,
  formatTokens,
  getStatusText,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'AdminAIConversations' });

const detailOpen = ref(false);
const detailId = ref<null | number>(null);

function onViewDetail(row: AIConversationInfo) {
  detailId.value = row.id;
  detailOpen.value = true;
}

const { Grid, onRefresh, gridApi } = useCrudPage<AIConversationInfo>({
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
});

const cleanupPageContext = registerPageContext('admin/ai/conversations', () => ({
  page_key: 'admin.ai.conversations',
  page_title: $t('admin.ai.conversation.name'),
  page_data: {
    resource: '/admin/ai/conversations',
  },
}));

const cleanupPageOps = registerPageOperations('admin.ai.conversations', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the conversation list',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'Conversation list refreshed' };
    },
  },
  {
    name: 'search',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search conversations by keyword',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Search keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[title][ilike]': keyword });
      gridApi.reload({ page: 1 });
      return { success: true, message: `Searched for: ${keyword}` };
    },
  },
  {
    name: 'view_detail',
    label: $t('shared.pageOperation.viewDetail'),
    description: 'View conversation detail by ID',
    readonly: true,
    params: {
      id: { type: 'number', description: 'Conversation ID' },
    },
    handler: async (params) => {
      const id = params?.id as number;
      if (!id) return { success: false, message: 'ID is required' };
      detailId.value = id;
      detailOpen.value = true;
      return { success: true, message: `Viewing conversation ${id}` };
    },
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.ai.conversation.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <ConversationDetail
      v-model:open="detailOpen"
      :conversation-id="detailId"
      api-prefix="/admin"
      i18n-prefix="admin.ai.conversation"
      :get-detail-api="getAIConversationDetailApi"
      :format-tokens="formatTokens"
      :format-cost="formatCost"
      :get-status-text="getStatusText"
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
