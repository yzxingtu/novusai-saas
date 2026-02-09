<script lang="ts" setup>
/**
 * 平台管理端 AI 使用量统计页面
 */
defineOptions({ name: 'AdminAIUsage' });

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, Progress, Spin, Tooltip } from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import { getAICallLogStatisticsApi, getAIUsageStatsApi } from '#/api/admin/ai';
import { $t } from '#/locales';

import { formatCost, formatTokens, useColumns, useGridFormSchema } from './data';

// ============================================================
// Summary statistics
// ============================================================

interface SummaryData {
  total_calls: number;
  total_tokens: number;
  total_cost: number;
  success_calls: number;
}

const summaryLoading = ref(false);
const summaryData = ref<SummaryData>({
  total_calls: 0,
  total_tokens: 0,
  total_cost: 0,
  success_calls: 0,
});

const successRate = computed(() => {
  const { total_calls, success_calls } = summaryData.value;
  if (total_calls === 0) return '0%';
  return `${((success_calls / total_calls) * 100).toFixed(1)}%`;
});

const summaryCards = computed(() => [
  {
    key: 'totalCalls',
    label: $t('admin.ai.usage.summary.totalCalls'),
    value: summaryData.value.total_calls,
    icon: 'lucide:phone-call',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
  {
    key: 'totalTokens',
    label: $t('admin.ai.usage.summary.totalTokens'),
    value: formatTokens(summaryData.value.total_tokens),
    icon: 'lucide:hash',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
  {
    key: 'totalCost',
    label: $t('admin.ai.usage.summary.totalCost'),
    value: formatCost(summaryData.value.total_cost),
    icon: 'lucide:dollar-sign',
    bgClass: 'bg-warning/10',
    iconClass: 'text-warning',
  },
  {
    key: 'successRate',
    label: $t('admin.ai.usage.summary.successRate'),
    value: successRate.value,
    icon: 'lucide:check-circle',
    bgClass: 'bg-success/10',
    iconClass: 'text-success',
  },
]);

async function loadSummary() {
  summaryLoading.value = true;
  try {
    const res = await getAICallLogStatisticsApi();
    summaryData.value = {
      total_calls: (res.total_calls as number) || 0,
      total_tokens: (res.total_tokens as number) || 0,
      total_cost: (res.total_cost as number) || 0,
      success_calls: (res.success_calls as number) || 0,
    };
  } catch {
    // Error handled by request interceptor
  } finally {
    summaryLoading.value = false;
  }
}

onMounted(loadSummary);

// ============================================================
// Grid
// ============================================================

const [Grid] = useVbenVxeGrid({
  gridOptions: {
    columns: useColumns(),
    proxyConfig: {
      ajax: {
        query: async ({ page: pager, form: formValues }: { form: Record<string, unknown>; page: { currentPage: number; pageSize: number } }) => {
          const params: Record<string, unknown> = {
            ...formValues,
            'page[number]': pager.currentPage,
            'page[size]': pager.pageSize,
            sort: '-stat_date',
          };
          const res = await getAIUsageStatsApi(params);
          return {
            items: res.items,
            total: res.total,
          };
        },
      },
    },
    pagerConfig: {
      pageSize: 20,
    },
    toolbarConfig: {
      search: true,
    },
  },
  formOptions: {
    schema: useGridFormSchema(),
    submitOnChange: true,
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <!-- Summary statistics cards -->
    <Spin :spinning="summaryLoading">
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card
          v-for="stat in summaryCards"
          :key="stat.key"
          :body-style="{ padding: '16px' }"
        >
          <div class="flex items-center gap-3">
            <div
              class="flex size-10 items-center justify-center rounded-lg"
              :class="stat.bgClass"
            >
              <IconifyIcon
                :icon="stat.icon"
                class="size-5"
                :class="stat.iconClass"
              />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">{{ stat.label }}</div>
              <div class="text-lg font-semibold text-foreground">
                {{ stat.value }}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </Spin>

    <!-- Data table -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- Total Tokens -->
        <template #totalTokens_cell="{ row }">
          <span class="font-mono text-foreground">
            {{ formatTokens(row.total_tokens) }}
          </span>
        </template>

        <!-- Input Tokens -->
        <template #inputTokens_cell="{ row }">
          <span class="font-mono text-muted-foreground">
            {{ formatTokens(row.input_tokens) }}
          </span>
        </template>

        <!-- Output Tokens -->
        <template #outputTokens_cell="{ row }">
          <span class="font-mono text-muted-foreground">
            {{ formatTokens(row.output_tokens) }}
          </span>
        </template>

        <!-- 成功率 -->
        <template #successRate_cell="{ row }">
          <Tooltip :title="`${$t('admin.ai.usage.successCount')}: ${row.success_count} | ${$t('admin.ai.usage.failedCount')}: ${row.failed_count}`">
            <Progress
              :percent="row.call_count > 0 ? Math.round((row.success_count / row.call_count) * 100) : 0"
              :stroke-color="(row.success_count / row.call_count) >= 0.95 ? '#22c55e' : (row.success_count / row.call_count) >= 0.8 ? '#f59e0b' : '#ef4444'"
              size="small"
              class="w-16"
            />
          </Tooltip>
        </template>

        <!-- Total Cost -->
        <template #totalCost_cell="{ row }">
          <span class="font-mono text-warning">
            {{ formatCost(row.total_cost) }}
          </span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
