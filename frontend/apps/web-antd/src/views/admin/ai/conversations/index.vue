<script lang="ts" setup>
/**
 * 平台端 AI 对话监控列表页面
 */
import type { AIConversationInfo } from '#/api/admin/ai';

defineOptions({ name: 'AdminAIConversations' });

import { ref } from 'vue';

import { Page } from '@vben/common-ui';

import { Card, Descriptions, Tag } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getAIConversationDetailApi, getAIConversationListApi } from '#/api/admin/ai';
import ConversationDetail from '#/components/business/conversation-detail/ConversationDetail.vue';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { formatCost, formatTokens, getStatusText, useColumns, useGridFormSchema } from './data';

const detailOpen = ref(false);
const detailId = ref<null | number>(null);

function onViewDetail(row: AIConversationInfo) {
  detailId.value = row.id;
  detailOpen.value = true;
}

const { Grid } = useCrudPage<AIConversationInfo>({
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
</script>

<template>
  <Page auto-content-height :description="$t('admin.ai.conversation.pageDesc')" content-class="flex flex-col gap-4">
    <ConversationDetail
      v-model:open="detailOpen"
      :conversation-id="detailId"
      i18n-prefix="admin.ai.conversation"
      :get-detail-api="getAIConversationDetailApi"
      :format-tokens="formatTokens"
      :format-cost="formatCost"
      :get-status-text="getStatusText"
    >
      <template #extra-descriptions="{ detail }">
        <Descriptions.Item :label="$t('admin.ai.conversation.tenantId')" :span="1">
          {{ detail.tenant_id }}
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.ai.conversation.userId')" :span="1">
          {{ detail.user_id ?? '-' }}
        </Descriptions.Item>
      </template>
    </ConversationDetail>

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 标题列 -->
        <template #title_cell="{ row }">
          <span v-if="row.title" class="text-foreground">{{ row.title }}</span>
          <span v-else class="text-muted-foreground italic">{{ $t('common.noData') }}</span>
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
          <span class="font-mono text-sm" :class="row.cost > 0 ? 'text-foreground' : 'text-muted-foreground'">
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
