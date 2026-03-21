<script lang="ts" setup>
/**
 * AI 调用日志列表页面
 * AI call log list page
 */
import type { AICallLogInfo } from '#/api/admin/ai';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, Spin, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getAICallLogListApi, getAICallLogStatisticsApi } from '#/api/admin/ai';
import {
  createRefreshPageOperation,
  createViewDetailPageOperation,
} from '#/composables';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { getProcessedImageUrl } from '#/utils/image';

import {
  formatCost,
  getCallSourceColor,
  getCallSourceText,
  getStatusText,
  isPlatformCall,
  getTenantDisplayName,
  useColumns,
  useGridFormSchema,
} from './data';
import CallLogDetail from './modules/detail.vue';

defineOptions({ name: 'AICallLogList' });

// ========== 统计摘要 ==========

const summaryLoading = ref(false);
const summaryData = ref({
  total_calls: 0,
  success_calls: 0,
  total_tokens: 0,
  total_cost: 0,
  avg_latency_ms: 0,
});

const successRate = computed(() => {
  const { total_calls, success_calls } = summaryData.value;
  if (total_calls === 0) return '0%';
  return `${((success_calls / total_calls) * 100).toFixed(1)}%`;
});

const summaryCards = computed(() => [
  {
    key: 'totalCalls',
    label: $t('admin.ai.callLog.summary.totalCalls'),
    value: summaryData.value.total_calls.toLocaleString(),
    icon: 'lucide:phone-call',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
  {
    key: 'successRate',
    label: $t('admin.ai.callLog.summary.successRate'),
    value: successRate.value,
    icon: 'lucide:check-circle',
    bgClass: 'bg-success/10',
    iconClass: 'text-success',
  },
  {
    key: 'avgLatency',
    label: $t('admin.ai.callLog.summary.avgLatency'),
    value: summaryData.value.avg_latency_ms
      ? `${Math.round(summaryData.value.avg_latency_ms)}ms`
      : '-',
    icon: 'lucide:timer',
    bgClass: 'bg-warning/10',
    iconClass: 'text-warning',
  },
  {
    key: 'totalCost',
    label: $t('admin.ai.callLog.summary.totalCost'),
    value: formatCost(summaryData.value.total_cost),
    icon: 'lucide:dollar-sign',
    bgClass: 'bg-destructive/10',
    iconClass: 'text-destructive',
  },
]);

async function loadSummary() {
  summaryLoading.value = true;
  try {
    const res = await getAICallLogStatisticsApi();
    summaryData.value = {
      total_calls: (res.total_calls as number) || 0,
      success_calls: (res.success_calls as number) || 0,
      total_tokens: (res.total_tokens as number) || 0,
      total_cost: (res.total_cost as number) || 0,
      avg_latency_ms: (res.avg_latency_ms as number) || 0,
    };
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  } finally {
    summaryLoading.value = false;
  }
}

onMounted(loadSummary);

// ========== 详情抽屉 ==========

const detailOpen = ref(false);
const detailLogId = ref<null | number>(null);

function onViewDetail(row: AICallLogInfo) {
  detailLogId.value = row.id;
  detailOpen.value = true;
}

// ========== Grid ==========

const { Grid, onRefresh } = useCrudPage<AICallLogInfo>({
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
  ai: {
    entityName: $t('admin.ai.callLog.name'),
    entityDescription: $t('admin.ai.callLog.pageDesc'),
    contextExtras: () => ({
      avg_latency_ms: summaryData.value.avg_latency_ms,
      success_rate: successRate.value,
      total_calls: summaryData.value.total_calls,
      total_cost: summaryData.value.total_cost,
      total_tokens: summaryData.value.total_tokens,
    }),
    extra: [
      createRefreshPageOperation({
        description:
          'Reload the call log list and summary / 重新加载调用日志列表与摘要',
        action: async () => {
          await Promise.resolve(onRefresh());
          await loadSummary();
        },
      }),
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
    :description="$t('admin.ai.callLog.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 详情抽屉 -->
    <CallLogDetail v-model:visible="detailOpen" :log-id="detailLogId" />

    <!-- 统计摘要 -->
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

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
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

        <!-- 供应商列 -->
        <template #providerName_cell="{ row }">
          <div
            v-if="row.provider_name"
            class="flex items-center justify-center gap-1.5"
          >
            <img
              v-if="row.provider_icon && Number(row.provider_icon) > 0"
              :src="getProcessedImageUrl(Number(row.provider_icon), { preset: 'small' })"
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

        <!-- 调用来源列 -->
        <template #source_cell="{ row }">
          <Tag :color="getCallSourceColor(row.tenant_id)">
            {{ getCallSourceText(row.tenant_id) }}
          </Tag>
        </template>

        <!-- 企业列 -->
        <template #tenantName_cell="{ row }">
          <span
            :class="
              isPlatformCall(row.tenant_id)
                ? 'font-medium text-foreground'
                : 'text-foreground'
            "
          >
            {{ getTenantDisplayName(row.tenant_id, row.tenant_name) }}
          </span>
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
                :icon="
                  row.status === 'success'
                    ? 'lucide:check-circle'
                    : row.status === 'failed'
                      ? 'lucide:x-circle'
                      : 'lucide:clock'
                "
                class="size-3"
              />
            </template>
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <!-- Tokens 合并列 -->
        <template #tokens_cell="{ row }">
          <Tooltip
            :title="`${$t('admin.ai.callLog.inputTokens')}: ${row.input_tokens} | ${$t('admin.ai.callLog.outputTokens')}: ${row.output_tokens}`"
          >
            <span class="font-mono text-sm text-muted-foreground">
              {{ row.total_tokens.toLocaleString() }}
            </span>
          </Tooltip>
        </template>

        <!-- 费用列 -->
        <template #cost_cell="{ row }">
          <span
            class="font-mono text-sm"
            :class="row.cost > 0 ? 'text-warning' : 'text-muted-foreground'"
          >
            {{ formatCost(row.cost) }}
          </span>
        </template>

        <!-- 延迟列：颜色编码 -->
        <template #latency_cell="{ row }">
          <span
            v-if="row.latency_ms"
            class="font-mono text-sm"
            :class="
              row.latency_ms > 5000
                ? 'text-destructive'
                : row.latency_ms > 2000
                  ? 'text-warning'
                  : 'text-success'
            "
          >
            {{ row.latency_ms }}ms
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
