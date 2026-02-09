<script lang="ts" setup>
/**
 * AI 调用日志列表页面
 */
import type { AICallLogInfo } from '#/api/admin/ai';

defineOptions({ name: 'AICallLogList' });

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getAICallLogListApi } from '#/api/admin/ai';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { formatCost, getStatusText, useColumns, useGridFormSchema } from './data';
import CallLogDetail from './modules/detail.vue';

const detailOpen = ref(false);
const detailLogId = ref<null | number>(null);

function onViewDetail(row: AICallLogInfo) {
  detailLogId.value = row.id;
  detailOpen.value = true;
}

const { Grid } = useCrudPage<AICallLogInfo>({
  api: {
    list: getAICallLogListApi,
    resource: '/admin/ai/call-logs',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.ai.callLog',
  defaultSort: '-created_at',
  customActions: {
    detail: onViewDetail,
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <!-- 详情抽屉 -->
    <CallLogDetail
      v-model:visible="detailOpen"
      :log-id="detailLogId"
    />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 调用时间列 -->
        <template #createdAt_cell="{ row }">
          <span class="text-muted-foreground">
            {{ formatDate(row.created_at) }}
          </span>
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

        <!-- 租户列 -->
        <template #tenantName_cell="{ row }">
          <span v-if="row.tenant_name" class="text-foreground">
            {{ row.tenant_name }}
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 状态列：图标 + 文字 -->
        <template #status_cell="{ row }">
          <Tag
            :color="
              row.status === 'success'
                ? 'success'
                : row.status === 'failed'
                  ? 'error'
                  : 'warning'
            "
          >
            <template #icon>
              <IconifyIcon
                :icon="row.status === 'success' ? 'lucide:check-circle' : row.status === 'failed' ? 'lucide:x-circle' : 'lucide:clock'"
                class="size-3"
              />
            </template>
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <!-- Tokens 合并列 -->
        <template #tokens_cell="{ row }">
          <Tooltip :title="`${$t('admin.ai.callLog.inputTokens')}: ${row.input_tokens} | ${$t('admin.ai.callLog.outputTokens')}: ${row.output_tokens}`">
            <span class="font-mono text-sm text-muted-foreground">
              {{ row.total_tokens.toLocaleString() }}
            </span>
          </Tooltip>
        </template>

        <!-- 费用列 -->
        <template #cost_cell="{ row }">
          <span class="font-mono text-sm" :class="row.cost > 0 ? 'text-foreground' : 'text-muted-foreground'">
            {{ formatCost(row.cost) }}
          </span>
        </template>

        <!-- 延迟列：颜色编码 -->
        <template #latency_cell="{ row }">
          <span
            v-if="row.latency_ms"
            class="font-mono text-sm"
            :class="row.latency_ms > 5000 ? 'text-destructive' : row.latency_ms > 2000 ? 'text-warning' : 'text-success'"
          >
            {{ row.latency_ms }}ms
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
