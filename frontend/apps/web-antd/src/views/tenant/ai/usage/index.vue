<script lang="ts" setup>
/**
 * 租户端 AI 用量统计页面
 */
import type { Dayjs } from 'dayjs';
import type { TenantAIUsageSummary } from '#/api/tenant/ai';

defineOptions({ name: 'TenantAIUsage' });

import { ref, onMounted, computed } from 'vue';

import dayjs from 'dayjs';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, DatePicker, Spin } from 'ant-design-vue';

import { getTenantAIUsageSummaryApi } from '#/api/tenant/ai';
import { $t } from '#/locales';

// ============ 日期范围 ============

type DateRange = [Dayjs, Dayjs];

const dateRange = ref<DateRange>([
  dayjs().subtract(29, 'day').startOf('day'),
  dayjs().endOf('day'),
]);

const presets = computed(() => [
  {
    label: $t('tenant.ai.usage.last7Days'),
    value: [dayjs().subtract(6, 'day').startOf('day'), dayjs().endOf('day')] as DateRange,
  },
  {
    label: $t('tenant.ai.usage.last30Days'),
    value: [dayjs().subtract(29, 'day').startOf('day'), dayjs().endOf('day')] as DateRange,
  },
  {
    label: $t('tenant.ai.usage.thisMonth'),
    value: [dayjs().startOf('month'), dayjs().endOf('day')] as DateRange,
  },
]);

function handleDateChange(dates: DateRange | [string, string] | null) {
  if (dates && dates[0] instanceof dayjs && dates[1] instanceof dayjs) {
    dateRange.value = dates as DateRange;
    loadSummary();
  }
}

function handlePreset(range: DateRange) {
  dateRange.value = range;
  loadSummary();
}

// ============ 数据加载 ============

const loading = ref(false);
const summary = ref<TenantAIUsageSummary | null>(null);

async function loadSummary() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = {};
    if (dateRange.value[0]) {
      params.start_date = dateRange.value[0].format('YYYY-MM-DD');
    }
    if (dateRange.value[1]) {
      params.end_date = dateRange.value[1].format('YYYY-MM-DD');
    }
    summary.value = await getTenantAIUsageSummaryApi(params);
  } catch {
    // Error handled by request interceptor
  } finally {
    loading.value = false;
  }
}

const successRate = computed(() => {
  if (!summary.value || summary.value.total_calls === 0) return '0%';
  const rate = (summary.value.success_calls / summary.value.total_calls) * 100;
  return `${rate.toFixed(1)}%`;
});

const formatCost = (cost: number | undefined) => {
  if (!cost) return '$0.00';
  return `$${cost.toFixed(4)}`;
};

const formatTokens = (tokens: number | undefined) => {
  if (!tokens) return '0';
  if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(2)}M`;
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
  return `${tokens}`;
};

/** 计算日趋势中某值占最大值的百分比 */
const maxDailyTokens = computed(() => {
  if (!summary.value?.daily_stats) return 1;
  return Math.max(...summary.value.daily_stats.map((d: Record<string, number>) => d.total_tokens || 0), 1);
});

function barWidth(value: number, max: number): string {
  if (max <= 0) return '0%';
  return `${Math.round((value / max) * 100)}%`;
}

onMounted(loadSummary);
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <!-- 日期范围筛选 -->
    <Card :body-style="{ padding: '12px 16px' }">
      <div class="flex flex-wrap items-center gap-3">
        <span class="text-sm font-medium text-foreground">
          {{ $t('tenant.ai.usage.dateRange') }}
        </span>
        <div class="flex items-center gap-2">
          <Button
            v-for="preset in presets"
            :key="preset.label"
            size="small"
            :type="
              dateRange[0]?.format('YYYY-MM-DD') === preset.value[0].format('YYYY-MM-DD')
                && dateRange[1]?.format('YYYY-MM-DD') === preset.value[1].format('YYYY-MM-DD')
                ? 'primary'
                : 'default'
            "
            @click="handlePreset(preset.value)"
          >
            {{ preset.label }}
          </Button>
        </div>
        <DatePicker.RangePicker
          :value="dateRange"
          format="YYYY-MM-DD"
          :allow-clear="false"
          size="small"
          class="w-56"
          @change="handleDateChange"
        />
      </div>
    </Card>

    <Spin :spinning="loading">
      <!-- 统计卡片 -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <!-- 总 Tokens -->
        <Card :body-style="{ padding: '20px' }">
          <div class="flex items-center gap-3">
            <div class="flex size-12 items-center justify-center rounded-xl bg-primary/10">
              <IconifyIcon icon="lucide:hash" class="size-6 text-primary" />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">
                {{ $t('tenant.ai.usage.summary.totalTokens') }}
              </div>
              <div class="text-2xl font-bold text-foreground">
                {{ formatTokens(summary?.total_tokens) }}
              </div>
            </div>
          </div>
        </Card>

        <!-- 总费用 -->
        <Card :body-style="{ padding: '20px' }">
          <div class="flex items-center gap-3">
            <div class="flex size-12 items-center justify-center rounded-xl bg-warning/10">
              <IconifyIcon icon="lucide:dollar-sign" class="size-6 text-warning" />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">
                {{ $t('tenant.ai.usage.summary.totalCost') }}
              </div>
              <div class="text-2xl font-bold text-foreground">
                {{ formatCost(summary?.total_cost) }}
              </div>
            </div>
          </div>
        </Card>

        <!-- 调用次数 -->
        <Card :body-style="{ padding: '20px' }">
          <div class="flex items-center gap-3">
            <div class="flex size-12 items-center justify-center rounded-xl bg-success/10">
              <IconifyIcon icon="lucide:activity" class="size-6 text-success" />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">
                {{ $t('tenant.ai.usage.summary.totalCalls') }}
              </div>
              <div class="text-2xl font-bold text-foreground">
                {{ summary?.total_calls || 0 }}
              </div>
            </div>
          </div>
        </Card>

        <!-- 成功率 -->
        <Card :body-style="{ padding: '20px' }">
          <div class="flex items-center gap-3">
            <div class="flex size-12 items-center justify-center rounded-xl bg-success/10">
              <IconifyIcon icon="lucide:check-circle" class="size-6 text-success" />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">
                {{ $t('tenant.ai.usage.summary.successRate') }}
              </div>
              <div class="text-2xl font-bold text-foreground">
                {{ successRate }}
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- 每日用量趋势 -->
      <Card
        v-if="summary?.daily_stats && summary.daily_stats.length > 0"
        class="mt-4"
        :title="$t('tenant.ai.usage.chart.dailyTrend')"
        :body-style="{ padding: '16px' }"
      >
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-muted-foreground">
                <th class="py-2 text-left font-medium">{{ $t('tenant.ai.usage.dateRange') }}</th>
                <th class="py-2 text-right font-medium">{{ $t('tenant.ai.usage.chart.tokens') }}</th>
                <th class="py-2 text-right font-medium">{{ $t('tenant.ai.usage.chart.cost') }}</th>
                <th class="py-2 text-right font-medium">{{ $t('tenant.ai.usage.chart.calls') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="day in summary.daily_stats"
                :key="day.date"
                class="border-b last:border-0 hover:bg-accent/50"
              >
                <td class="py-2 text-foreground">{{ day.date }}</td>
                <td class="py-2 text-right">
                  <div class="flex items-center justify-end gap-2">
                    <div class="h-2 w-24 overflow-hidden rounded-full bg-accent">
                      <div
                        class="h-full rounded-full bg-primary transition-all duration-300"
                        :style="{ width: barWidth(day.total_tokens, maxDailyTokens) }"
                      />
                    </div>
                    <span class="min-w-[48px] text-right text-muted-foreground">
                      {{ formatTokens(day.total_tokens) }}
                    </span>
                  </div>
                </td>
                <td class="py-2 text-right text-muted-foreground">{{ formatCost(day.cost) }}</td>
                <td class="py-2 text-right text-muted-foreground">{{ day.calls }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      <!-- 按模型分布 -->
      <Card
        v-if="summary?.model_stats && summary.model_stats.length > 0"
        class="mt-4"
        :title="$t('tenant.ai.usage.chart.modelDistribution')"
        :body-style="{ padding: '16px' }"
      >
        <div class="space-y-3">
          <div
            v-for="model in summary.model_stats"
            :key="model.model_id"
            class="flex items-center justify-between rounded-lg bg-accent/30 p-3"
          >
            <div class="flex items-center gap-2">
              <IconifyIcon icon="lucide:brain" class="size-4 text-primary" />
              <span class="font-medium text-foreground">{{ model.model_name }}</span>
            </div>
            <div class="flex items-center gap-4 text-sm text-muted-foreground">
              <span>{{ formatTokens(model.total_tokens) }} tokens</span>
              <span>{{ formatCost(model.cost) }}</span>
              <span>{{ model.calls }} {{ $t('tenant.ai.usage.chart.calls') }}</span>
            </div>
          </div>
        </div>
      </Card>

      <!-- 空状态 -->
      <Card
        v-if="!loading && (!summary || summary.total_calls === 0)"
        class="mt-4"
        :body-style="{ padding: '48px', textAlign: 'center' }"
      >
        <IconifyIcon icon="lucide:bar-chart-3" class="mx-auto mb-4 size-12 text-muted-foreground" />
        <div class="text-muted-foreground">{{ $t('common.noData') }}</div>
      </Card>
    </Spin>
  </Page>
</template>
