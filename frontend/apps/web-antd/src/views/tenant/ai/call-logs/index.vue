<script lang="ts" setup>
/**
 * 企业端 AI 调用日志列表页面
 */
import type { TenantAICallLogInfo } from '#/api/tenant/ai';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getTenantAICallLogListApi } from '#/api/tenant/ai';
import { createViewDetailPageOperation } from '#/composables';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAttachmentImageUrl } from '#/utils/image';

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

// Quick status filter / 快捷状态筛选
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

const { Grid, gridApi } = useCrudPage<TenantAICallLogInfo>({
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
  ai: {
    entityName: $t('tenant.ai.callLog.name'),
    entityDescription: $t('tenant.ai.callLog.pageDesc'),
    contextExtras: () => ({
      quick_status_filter: activeFilter.value,
    }),
    extra: [
      createViewDetailPageOperation({
        description:
          'Open the call log detail drawer by ID / 按 ID 打开调用日志详情抽屉',
        idDescription: 'Call log ID / 调用日志 ID',
        openDetail: async (id) => {
          detailLogId.value = id;
          detailOpen.value = true;
        },
      }),
    ],
  },
});
</script>

<template>
  <Page
    auto-content-height
    class="min-w-0 max-w-full"
    :description="$t('tenant.ai.callLog.pageDesc')"
    content-class="flex min-h-0 min-w-0 w-full max-w-full flex-1 flex-col gap-4"
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

    <Card
      class="flex min-h-0 w-full min-w-0 max-w-full flex-1 flex-col"
      :body-style="{
        padding: '16px',
        flex: 1,
        minHeight: 0,
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }"
    >
      <div class="min-h-0 w-full min-w-0 max-w-full flex-1 overflow-hidden">
        <Grid class="h-full w-full min-w-0 max-w-full">
          <!-- 调用时间列 -->
          <template #createdAt_cell="{ row }">
            <Tooltip :title="formatDate(row.created_at)">
              <span class="text-muted-foreground">
                {{ formatRelativeTime(row.created_at) }}
              </span>
            </Tooltip>
          </template>

          <!-- 模型名称列 -->
          <template #modelName_cell="{ row }">
            <div
              v-if="row.model_name && row.model_name !== '-'"
              class="flex items-center gap-1.5"
            >
              <IconifyIcon
                icon="lucide:brain"
                class="size-3.5 text-muted-foreground"
              />
              <code class="rounded bg-accent px-1 py-0.5 text-xs">
                {{ row.model_name }}
              </code>
            </div>
            <span v-else class="text-muted-foreground">-</span>
          </template>

          <!-- 调用人 -->
          <template #callerName_cell="{ row }">
            <span
              v-if="row.caller_name && row.caller_name !== '-'"
              class="text-foreground"
            >
              {{ row.caller_name }}
            </span>
            <span v-else class="text-muted-foreground">-</span>
          </template>

          <!-- Provider column: icon + name / 供应商列：图标 + 名称 -->
          <template #providerName_cell="{ row }">
            <div
              v-if="row.provider_name && row.provider_name !== '-'"
              class="flex items-center justify-center gap-1.5"
            >
              <img
                v-if="
                  toAttachmentImageUrl(row.provider_icon, { preset: 'small' })
                "
                :src="
                  toAttachmentImageUrl(row.provider_icon, { preset: 'small' })
                "
                class="size-4 shrink-0 rounded object-contain"
                alt=""
              />
              <IconifyIcon
                v-else
                icon="lucide:cpu"
                class="size-3.5 text-muted-foreground"
              />
              <span class="text-foreground">{{ row.provider_name }}</span>
            </div>
            <span v-else class="text-muted-foreground">-</span>
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
      </div>
    </Card>
  </Page>
</template>
