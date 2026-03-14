<script lang="ts" setup>
/**
 * 平台端 AI 操作审计日志列表页面
 *
 * 全局审计日志查询，支持跨企业筛选
 */
import type {
  AdminActionLogDetail,
  AdminActionLogItem,
} from '#/api/admin/action-logs';

import { onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, Descriptions, Drawer, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getAdminActionLogDetailApi,
  getAdminActionLogListApi,
} from '#/api/admin/action-logs';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  getLevelColor,
  getLevelText,
  getStatusColor,
  getStatusText,
  getTypeColor,
  getTypeText,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'AdminAIActionLogList' });

// ============ 详情抽屉 ============

const detailOpen = ref(false);
const detailLoading = ref(false);
const detailData = ref<AdminActionLogDetail | null>(null);

async function openDetail(row: AdminActionLogItem) {
  detailOpen.value = true;
  detailLoading.value = true;
  try {
    detailData.value = await getAdminActionLogDetailApi(row.id);
  } catch {
    detailData.value = null;
  } finally {
    detailLoading.value = false;
  }
}

// ============ 列表 ============

const { Grid, onRefresh, gridApi } = useCrudPage<AdminActionLogItem>({
  api: {
    list: getAdminActionLogListApi,
    resource: '/admin/ai/action-logs',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.ai.actionLog',
  defaultSort: '-created_at',
  customActions: {
    detail: openDetail,
  },
});

const cleanupPageContext = registerPageContext('admin/ai/action-logs', () => ({
  page_key: 'admin.ai.action-logs',
  page_title: $t('admin.ai.actionLog.name'),
  page_data: {
    resource: '/admin/ai/action-logs',
  },
}));

const cleanupPageOps = registerPageOperations('admin.ai.action-logs', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the action log list',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'Action log list refreshed' };
    },
  },
  {
    name: 'search',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search action logs by keyword',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Search keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[action_type][ilike]': keyword });
      gridApi.reload({ page: 1 });
      return { success: true, message: `Searched for: ${keyword}` };
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
    :description="$t('admin.ai.actionLog.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 时间列 -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatDate(row.created_at) }}
            </span>
          </Tooltip>
        </template>

        <!-- 操作名称列 -->
        <template #actionName_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon icon="lucide:zap" class="size-3.5 text-primary" />
            <code class="rounded bg-accent px-1 py-0.5 text-xs font-medium">
              {{ row.action_name }}
            </code>
          </div>
        </template>

        <!-- 类型列 -->
        <template #actionType_cell="{ row }">
          <Tag :color="getTypeColor(row.action_type)">
            {{ getTypeText(row.action_type) }}
          </Tag>
        </template>

        <!-- 安全等级列 -->
        <template #actionLevel_cell="{ row }">
          <Tag :color="getLevelColor(row.action_level)">
            {{ getLevelText(row.action_level) }}
          </Tag>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag :color="getStatusColor(row.status)">
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <!-- 耗时列 -->
        <template #duration_cell="{ row }">
          <span v-if="row.duration_ms" class="text-muted-foreground">
            {{ row.duration_ms }}ms
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>
      </Grid>
    </Card>

    <!-- 详情抽屉 -->
    <Drawer
      v-model:open="detailOpen"
      :title="$t('admin.ai.actionLog.viewDetail')"
      width="600"
      :loading="detailLoading"
    >
      <Descriptions v-if="detailData" :column="1" bordered size="small">
        <Descriptions.Item label="ID">
          {{ detailData.id }}
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.ai.actionLog.actionName')">
          <code class="rounded bg-accent px-1 py-0.5 text-xs">
            {{ detailData.action_name }}
          </code>
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.ai.actionLog.actionType')">
          <Tag :color="getTypeColor(detailData.action_type as string)">
            {{ getTypeText(detailData.action_type as string) }}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.ai.actionLog.actionLevel')">
          <Tag :color="getLevelColor(detailData.action_level as string)">
            {{ getLevelText(detailData.action_level as string) }}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.ai.actionLog.status')">
          <Tag :color="getStatusColor(detailData.status as string)">
            {{ getStatusText(detailData.status as string) }}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.ai.actionLog.tenantId')">
          {{ detailData.tenant_id }}
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.ai.actionLog.operatorId')">
          {{ detailData.operator_id ?? '-' }}
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.ai.actionLog.executionTime')">
          {{ detailData.duration_ms ? `${detailData.duration_ms}ms` : '-' }}
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.ai.actionLog.createdAt')">
          {{ formatDate(detailData.created_at as string) }}
        </Descriptions.Item>
        <Descriptions.Item
          v-if="detailData.error_message"
          :label="$t('admin.ai.actionLog.error')"
        >
          <pre
            class="max-h-40 overflow-auto rounded bg-destructive/10 p-2 text-xs text-destructive"
            >{{ detailData.error_message }}</pre
          >
        </Descriptions.Item>
        <Descriptions.Item
          v-if="detailData.request_data"
          :label="$t('admin.ai.actionLog.requestData')"
        >
          <pre
            class="max-h-60 overflow-auto rounded bg-accent/50 p-2 text-xs"
            >{{ JSON.stringify(detailData.request_data, null, 2) }}</pre
          >
        </Descriptions.Item>
        <Descriptions.Item
          v-if="detailData.response_data"
          :label="$t('admin.ai.actionLog.responseData')"
        >
          <pre
            class="max-h-60 overflow-auto rounded bg-accent/50 p-2 text-xs"
            >{{ JSON.stringify(detailData.response_data, null, 2) }}</pre
          >
        </Descriptions.Item>
      </Descriptions>
    </Drawer>
  </Page>
</template>
