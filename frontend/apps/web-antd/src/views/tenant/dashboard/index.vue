<script lang="ts" setup>
/**
 * Tenant Dashboard — 综合数据面板
 * Tenant dashboard — overview panel
 *
 * B5: 统计卡片 + 快捷操作 / B6: AI 使用趋势 / B7: 近期活动时间线
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import type {
  AITrendItem,
  TenantActivityItem,
  TenantDashboardStats,
} from '#/api/tenant/dashboard';

import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';
import { EchartsUI, useEcharts } from '@vben/plugins/echarts';
import { useUserStore } from '@vben/stores';

import { Card, Spin, Tag } from 'ant-design-vue';

import {
  getAITrendApi,
  getTenantDashboardStatsApi,
  getTenantRecentActivitiesApi,
} from '#/api/tenant/dashboard';
import PluginDashboardWidgets from '#/components/business/plugin-slots/PluginDashboardWidgets.vue';
import { usePageAIContext } from '#/composables/use-page-ai-registration';
import { $t } from '#/locales';
import { formatDate as formatDateUtil } from '#/utils/common';

defineOptions({ name: 'TenantDashboard' });

const router = useRouter();
const userStore = useUserStore();
const loading = ref(false);

const stats = ref<TenantDashboardStats>({
  total_users: 0,
  active_users: 0,
  api_calls: 0,
  total_tokens: 0,
  total_cost: 0,
  storage_used_bytes: 0,
  storage_used_mb: 0,
  total_agents: 0,
  total_knowledge_bases: 0,
  total_kb_documents: 0,
  monthly_conversations: 0,
});
const aiTrend = ref<AITrendItem[]>([]);
const activities = ref<TenantActivityItem[]>([]);

async function loadAll() {
  loading.value = true;
  try {
    const [s, trend, act] = await Promise.allSettled([
      getTenantDashboardStatsApi(),
      getAITrendApi(7),
      getTenantRecentActivitiesApi(15),
    ]);
    if (s.status === 'fulfilled') stats.value = s.value;
    if (trend.status === 'fulfilled') aiTrend.value = trend.value;
    if (act.status === 'fulfilled') activities.value = act.value;
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadAll();
});

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

function formatDate(dateStr: null | string): string {
  if (!dateStr) return '';
  return formatDateUtil(dateStr);
}

const methodColors: Record<string, string> = {
  GET: 'blue',
  POST: 'green',
  PUT: 'orange',
  DELETE: 'red',
  PATCH: 'purple',
};

// B5: 统计卡片 / B5: Stats cards
const statCards = computed(() => [
  {
    key: 'agents',
    label: $t('tenant.dashboard.stats.totalAgents'),
    value: stats.value.total_agents,
    icon: 'lucide:bot',
    bg: 'bg-primary/10',
    ic: 'text-primary',
  },
  {
    key: 'kbs',
    label: $t('tenant.dashboard.stats.totalKnowledgeBases'),
    value: stats.value.total_knowledge_bases,
    icon: 'lucide:book-open',
    bg: 'bg-success/10',
    ic: 'text-success',
  },
  {
    key: 'kbDocs',
    label: $t('tenant.dashboard.stats.totalKBDocuments'),
    value: formatNumber(stats.value.total_kb_documents),
    icon: 'lucide:file-text',
    bg: 'bg-warning/10',
    ic: 'text-warning',
  },
  {
    key: 'conversations',
    label: $t('tenant.dashboard.stats.monthlyConversations'),
    value: formatNumber(stats.value.monthly_conversations),
    icon: 'lucide:message-square',
    bg: 'bg-primary/10',
    ic: 'text-primary',
  },
  {
    key: 'calls',
    label: $t('tenant.dashboard.stats.apiCalls'),
    value: formatNumber(stats.value.api_calls),
    icon: 'lucide:brain',
    bg: 'bg-success/10',
    ic: 'text-success',
  },
  {
    key: 'storage',
    label: $t('tenant.dashboard.stats.storageUsed'),
    value: `${stats.value.storage_used_mb} MB`,
    icon: 'lucide:hard-drive',
    bg: 'bg-warning/10',
    ic: 'text-warning',
  },
]);

// B6: AI 趋势 / B6: AI trend
const aiTrendChartRef = ref<EchartsUIType>();
const { renderEcharts: renderAiTrendChart } = useEcharts(aiTrendChartRef);

function renderTrendChart() {
  const data = aiTrend.value;
  if (data.length === 0) return;
  renderAiTrendChart({
    tooltip: { trigger: 'axis' },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '8%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: data.map((i) => i.date.slice(5)),
      axisLabel: { fontSize: 10 },
    },
    yAxis: [
      { type: 'value', name: $t('tenant.analytics.chart.calls') },
      { type: 'value', name: 'Token' },
    ],
    series: [
      {
        name: $t('tenant.analytics.chart.calls'),
        type: 'bar',
        data: data.map((i) => i.calls),
        itemStyle: { color: '#5B8FF9', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 20,
      },
      {
        name: 'Token',
        type: 'line',
        data: data.map((i) => i.tokens),
        smooth: true,
        itemStyle: { color: '#5AD8A6' },
        yAxisIndex: 1,
      },
    ],
  });
}

watch(aiTrend, renderTrendChart);

// Quick actions / Fast actions
const quickActions = computed(() => [
  {
    key: 'chat',
    label: $t('tenant.dashboard.quickActions.aiChat'),
    icon: 'lucide:message-square',
    bg: 'bg-primary/10',
    color: 'text-primary',
    route: '/tenant/ai/chat',
  },
  {
    key: 'kb',
    label: $t('tenant.dashboard.quickActions.knowledgeBases'),
    icon: 'lucide:book-open',
    bg: 'bg-success/10',
    color: 'text-success',
    route: '/tenant/ai/knowledge-bases',
  },
  {
    key: 'agents',
    label: $t('tenant.dashboard.quickActions.agents'),
    icon: 'lucide:bot',
    bg: 'bg-warning/10',
    color: 'text-warning',
    route: '/tenant/ai/agents',
  },
  {
    key: 'logs',
    label: $t('tenant.dashboard.quickActions.callLogs'),
    icon: 'lucide:scroll-text',
    bg: 'bg-primary/10',
    color: 'text-primary',
    route: '/tenant/ai/call-logs',
  },
]);

function navigateTo(route: string) {
  router.push(route);
}

usePageAIContext({
  title: () => $t('tenant.dashboard.title'),
  resource: '/tenant/dashboard',
  data: () => ({
    api_calls: stats.value?.api_calls ?? 0,
    storage_used_mb: stats.value?.storage_used_mb ?? 0,
    total_tokens: stats.value?.total_tokens ?? 0,
  }),
});
</script>

<template>
  <div class="p-5">
    <!-- Welcome -->
    <Card :title="$t('tenant.dashboard.title')" class="mb-4">
      <template #extra>
        <span class="text-muted-foreground">{{
          $t('tenant.dashboard.welcome')
        }}</span>
      </template>
      <div class="text-lg">
        {{
          $t('tenant.dashboard.greeting', {
            name: userStore.userInfo?.realName || $t('tenant.common.admin'),
          })
        }}
      </div>
      <p class="mt-2 text-muted-foreground">
        {{ $t('tenant.dashboard.description') }}
      </p>
    </Card>

    <!-- B5: Stats Cards Grid (6 cards) -->
    <Spin :spinning="loading">
      <div class="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card
          v-for="stat in statCards"
          :key="stat.key"
          :body-style="{ padding: '20px' }"
        >
          <div class="flex items-center gap-4">
            <div
              class="flex size-12 items-center justify-center rounded-xl"
              :class="stat.bg"
            >
              <IconifyIcon :icon="stat.icon" class="size-6" :class="stat.ic" />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">{{ stat.label }}</div>
              <div class="text-2xl font-bold text-foreground">
                {{ stat.value }}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </Spin>

    <!-- 插件 dashboard_widgets -->
    <div class="mb-4">
      <PluginDashboardWidgets />
    </div>

    <!-- Row 2: Quick Actions + AI Trend + Recent Activities -->
    <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <!-- Quick Actions -->
      <Card :title="$t('tenant.dashboard.quickActions.title')">
        <div class="space-y-2">
          <div
            v-for="action in quickActions"
            :key="action.key"
            class="group flex cursor-pointer items-center gap-3 rounded-lg border border-transparent p-3 transition-all hover:border-primary/20 hover:bg-accent"
            @click="navigateTo(action.route)"
          >
            <div
              class="flex size-10 shrink-0 items-center justify-center rounded-lg"
              :class="action.bg"
            >
              <IconifyIcon
                :icon="action.icon"
                class="size-5"
                :class="action.color"
              />
            </div>
            <span class="text-sm font-medium text-foreground">{{
              action.label
            }}</span>
          </div>
        </div>
      </Card>

      <!-- B6: AI Usage Trend (ECharts) -->
      <Card :title="$t('tenant.dashboard.aiTrend.title')">
        <EchartsUI
          v-if="aiTrend.length > 0"
          ref="aiTrendChartRef"
          height="220px"
        />
        <div v-else class="py-8 text-center text-sm text-muted-foreground">
          {{ $t('tenant.dashboard.aiTrend.empty') }}
        </div>
      </Card>

      <!-- B7: Recent Activities -->
      <Card :title="$t('tenant.dashboard.activities.title')">
        <div
          v-if="activities.length > 0"
          class="max-h-72 space-y-2 overflow-y-auto"
        >
          <div
            v-for="act in activities"
            :key="act.id"
            class="flex items-start gap-2 border-b border-border/50 pb-2 last:border-0"
          >
            <Tag
              :color="methodColors[act.method] || 'default'"
              class="shrink-0 text-xs"
            >
              {{ act.method }}
            </Tag>
            <div class="min-w-0 flex-1">
              <div class="truncate text-xs text-foreground">
                <span class="font-medium">{{ act.username || '—' }}</span>
                <span class="text-muted-foreground">
                  · {{ act.module || '' }}</span
                >
              </div>
              <div class="truncate text-xs text-muted-foreground">
                {{ act.path }}
              </div>
            </div>
            <span class="shrink-0 text-xs text-muted-foreground">{{
              formatDate(act.created_at)
            }}</span>
          </div>
        </div>
        <div v-else class="py-8 text-center text-sm text-muted-foreground">
          {{ $t('tenant.dashboard.activities.empty') }}
        </div>
      </Card>
    </div>
  </div>
</template>
