<script lang="ts" setup>
/**
 * 租户端对话管理列表页面
 */
import type { ConversationInfo } from '#/api/tenant/conversations';

defineOptions({ name: 'TenantConversationList' });

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, message, Modal, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  archiveConversationApi,
  deleteConversationApi,
  exportConversationApi,
  getConversationListApi,
} from '#/api/tenant/conversations';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { formatCost, formatTokenCount, getStatusText, useColumns, useGridFormSchema } from './data';
import BatchArchiveModal from './modules/BatchArchiveModal.vue';
import ConversationDetail from './modules/ConversationDetail.vue';

const detailOpen = ref(false);
const detailId = ref<null | number>(null);
const batchArchiveOpen = ref(false);

function onViewDetail(row: ConversationInfo) {
  detailId.value = row.id;
  detailOpen.value = true;
}

async function onArchive(row: ConversationInfo) {
  if (row.status === 'archived') return;
  Modal.confirm({
    title: $t('tenant.ai.conversation.confirmArchive'),
    async onOk() {
      await archiveConversationApi(row.id);
      message.success($t('tenant.ai.conversation.messages.archiveSuccess'));
      gridReload();
    },
  });
}

async function onExport(row: ConversationInfo) {
  try {
    const result = await exportConversationApi(row.id, 'json');
    const blob = new Blob([result.content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = result.filename;
    a.click();
    URL.revokeObjectURL(url);
    message.success($t('tenant.ai.conversation.messages.exportSuccess'));
  } catch {
    message.error($t('tenant.common.failed'));
  }
}

async function onDelete(row: ConversationInfo) {
  await deleteConversationApi(row.id);
  message.success($t('tenant.ai.conversation.messages.deleteSuccess'));
  gridReload();
}

let gridReload: () => void;

const { Grid } = useCrudPage<ConversationInfo>({
  api: {
    list: getConversationListApi,
    delete: deleteConversationApi,
    resource: '/tenant/ai/conversations',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'tenant.ai.conversation',
  defaultSort: '-created_at',
  customActions: {
    detail: onViewDetail,
    archive: onArchive,
    export: onExport,
    delete: onDelete,
  },
  onMounted(grid) {
    gridReload = () => grid.commitProxy('query');
  },
});

function onBatchArchiveSuccess() {
  gridReload();
}
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <!-- 详情抽屉 -->
    <ConversationDetail
      v-model:open="detailOpen"
      :conversation-id="detailId"
    />

    <!-- 批量归档弹窗 -->
    <BatchArchiveModal
      v-model:open="batchArchiveOpen"
      @success="onBatchArchiveSuccess"
    />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 工具栏插槽 -->
        <template #toolbar-tools>
          <Button
            v-access:code="['agent_conversation:update']"
            type="default"
            @click="batchArchiveOpen = true"
          >
            <IconifyIcon icon="lucide:archive" class="mr-1 size-4" />
            {{ $t('tenant.ai.conversation.batchArchive') }}
          </Button>
        </template>

        <!-- 标题列 -->
        <template #title_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon
              icon="lucide:message-square"
              class="size-3.5 text-muted-foreground"
            />
            <span class="truncate">{{ row.title || $t('tenant.ai.conversation.untitled') }}</span>
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

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag
            :color="row.status === 'active' ? 'success' : 'default'"
          >
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
