<script lang="ts" setup>
/**
 * 租户端 AI 调用日志列表页面
 */
import type { TenantAICallLogInfo } from '#/api/tenant/ai';

import { onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getTenantAICallLogListApi } from '#/api/tenant/ai';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  formatCost,
  getStatusColor,
  getStatusText,
  useColumns,
  useGridFormSchema,
} from './data';
import CallLogDetail from './modules/CallLogDetail.vue';

defineOptions({ name: 'TenantAICallLogList' });

const detailOpen = ref(false);
const detailLogId = ref<null | number>(null);

function onViewDetail(row: TenantAICallLogInfo) {
  detailLogId.value = row.id;
  detailOpen.value = true;
}

// Quick status filter
const activeFilter = ref<'all' | 'failed' | 'success'>('all');

function applyQuickFilter(filter: 'all' | 'failed' | 'success') {
  activeFilter.value = filter;
  if (filter === 'all') {
    gridApi.formApi?.setValues({ 'filter[status][eq]': undefined });
  } else {
    gridApi.formApi?.setValues({ 'filter[status][eq]': filter });
  }
  gridApi.reload();
}

const { Grid, gridApi, onRefresh } = useCrudPage<TenantAICallLogInfo>({
  api: {
    list: getTenantAICallLogListApi,
    resource: '/tenant/ai/call-logs',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'tenant.ai.callLog',
  defaultSort: '-created_at',
  customActions: {
    detail: onViewDetail,
  },
});

const cleanupPageContext = registerPageContext('tenant/ai/call-logs', () => ({
  page_key: 'tenant.ai.call-logs',
  page_title: $t('tenant.ai.callLog.name'),
  page_data: {
    resource: '/tenant/ai/call-logs',
  },
}));

const cleanupPageOps = registerPageOperations('tenant.ai.call-logs', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the call log list',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'Call log list refreshed' };
    },
  },
  {
    name: 'search_logs',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search call logs by model name',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Model name keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[model_name][ilike]': keyword });
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
    :description="$t('tenant.ai.callLog.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 详情抽屉 -->
    <CallLogDetail v-model:open="detailOpen" :log-id="detailLogId" />

    <!-- 快速筛选 -->
    <div class="flex items-center gap-2">
      <Button
        :type="activeFilter === 'all' ? 'primary' : 'default'"
        size="small"
        @click="applyQuickFilter('all')"
      >
        {{ $t('tenant.ai.callLog.filter.all') }}
      </Button>
      <Button
        :type="activeFilter === 'success' ? 'primary' : 'default'"
        size="small"
        @click="applyQuickFilter('success')"
      >
        <IconifyIcon
          icon="lucide:check-circle"
          class="mr-1 inline size-3.5 text-success"
        />
        {{ $t('tenant.ai.callLog.filter.onlySuccess') }}
      </Button>
      <Button
        :type="activeFilter === 'failed' ? 'primary' : 'default'"
        size="small"
        @click="applyQuickFilter('failed')"
      >
        <IconifyIcon
          icon="lucide:x-circle"
          class="mr-1 inline size-3.5 text-destructive"
        />
        {{ $t('tenant.ai.callLog.filter.onlyFailed') }}
      </Button>
    </div>

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 调用时间列 -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatDate(row.created_at) }}
            </span>
          </Tooltip>
        </template>

        <!-- 模型名称列 -->
        <template #modelName_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon
              icon="lucide:brain"
              class="size-3.5 text-muted-foreground"
            />
            <code class="rounded bg-accent px-1 py-0.5 text-xs">
              {{ row.model_name || '-' }}
            </code>
          </div>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag :color="getStatusColor(row.status)">
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <!-- 费用列 -->
        <template #cost_cell="{ row }">
          <span class="text-muted-foreground">
            {{ formatCost(row.cost) }}
          </span>
        </template>

        <!-- 延迟列 -->
        <template #latency_cell="{ row }">
          <span v-if="row.latency_ms" class="text-muted-foreground">
            {{ row.latency_ms }}ms
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
