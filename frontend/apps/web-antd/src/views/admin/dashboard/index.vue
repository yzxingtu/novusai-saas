<script lang="ts" setup>
/**
 * Admin Dashboard — 综合数据面板
 *
 * A7: 统计卡片网格（基础 + AI + 存储 + 插件）
 * A8: 企业增长趋势
 * A9: 近期活动时间线
 * A10: 系统健康状态指示卡片
 */
import type { EchartsUIType } from '@vben/plugins/echarts';

import type {
  ActivityItem,
  AIOverview,
  DashboardStats,
  PluginOverview,
  StorageOverview,
  SystemHealth,
  TenantGrowthItem,
} from '#/api/admin/dashboard';

import {
  computed,
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';
import { EchartsUI, useEcharts } from '@vben/plugins/echarts';
import { useUserStore } from '@vben/stores';

import { Card, Progress, Spin, Tag } from 'ant-design-vue';

import {
  getAIOverviewApi,
  getDashboardStatsApi,
  getPluginOverviewApi,
  getRecentActivitiesApi,
  getStorageOverviewApi,
  getSystemHealthApi,
  getTenantGrowthApi,
} from '#/api/admin/dashboard';
import PluginDashboardWidgets from '#/components/business/plugin-slots/PluginDashboardWidgets.vue';
import { usePageAIContext } from '#/composables/use-page-ai-registration';
import { $t } from '#/locales';
import { formatDate as formatDateUtil } from '#/utils/common';

defineOptions({ name: 'Dashboard' });

const router = useRouter();
const userStore = useUserStore();
const loading = ref(false);

const stats = ref<DashboardStats>({
  total_tenants: 0,
  active_tenants: 0,
  total_users: 0,
  today_login: 0,
});
const health = ref<null | SystemHealth>(null);
const aiOverview = ref<AIOverview | null>(null);
const storageOverview = ref<null | StorageOverview>(null);
const pluginOverview = ref<null | PluginOverview>(null);
const tenantGrowth = ref<TenantGrowthItem[]>([]);
const activities = ref<ActivityItem[]>([]);

async function loadAll() {
  loading.value = true;
  try {
    const [s, h, ai, sto, pl, tg, act] = await Promise.allSettled([
      getDashboardStatsApi(),
      getSystemHealthApi(),
      getAIOverviewApi(),
      getStorageOverviewApi(),
      getPluginOverviewApi(),
      getTenantGrowthApi(30),
      getRecentActivitiesApi(15),
    ]);
    if (s.status === 'fulfilled') stats.value = s.value;
    if (h.status === 'fulfilled') health.value = h.value;
    if (ai.status === 'fulfilled') aiOverview.value = ai.value;
    if (sto.status === 'fulfilled') storageOverview.value = sto.value;
    if (pl.status === 'fulfilled') pluginOverview.value = pl.value;
    if (tg.status === 'fulfilled') tenantGrowth.value = tg.value;
    if (act.status === 'fulfilled') activities.value = act.value;
  } finally {
    loading.value = false;
  }
}

usePageAIContext({
  title: () => $t('admin.dashboard.platformConsole'),
  data: () => ({
    system_health: health.value?.status ?? 'unknown',
    total_tenants: stats.value.total_tenants,
    active_tenants: stats.value.active_tenants,
    total_users: stats.value.total_users,
    today_login: stats.value.today_login,
    ai_calls_today: aiOverview.value?.today_calls ?? 0,
    ai_total_tokens: aiOverview.value?.total_tokens ?? 0,
    storage_files: storageOverview.value?.total_files ?? 0,
    plugins_enabled: pluginOverview.value?.enabled ?? 0,
  }),
});

onMounted(() => {
  loadAll();
});

// ── A7: 统计卡片 ──
const statCards = computed(() => [
  {
    key: 'tenants',
    label: $t('admin.dashboard.stats.totalTenants'),
    value: stats.value.total_tenants,
    icon: 'lucide:building-2',
    bg: 'bg-primary/10',
    ic: 'text-primary',
  },
  {
    key: 'active',
    label: $t('admin.dashboard.stats.activeTenants'),
    value: stats.value.active_tenants,
    icon: 'lucide:activity',
    bg: 'bg-success/10',
    ic: 'text-success',
  },
  {
    key: 'users',
    label: $t('admin.dashboard.stats.totalUsers'),
    value: stats.value.total_users,
    icon: 'lucide:users',
    bg: 'bg-warning/10',
    ic: 'text-warning',
  },
  {
    key: 'login',
    label: $t('admin.dashboard.stats.todayLogin'),
    value: stats.value.today_login,
    icon: 'lucide:log-in',
    bg: 'bg-primary/10',
    ic: 'text-primary',
  },
  {
    key: 'aiCalls',
    label: $t('admin.dashboard.stats.aiCalls'),
    value: aiOverview.value?.total_calls ?? 0,
    icon: 'lucide:brain',
    bg: 'bg-primary/10',
    ic: 'text-primary',
  },
  {
    key: 'aiTokens',
    label: $t('admin.dashboard.stats.aiTokens'),
    value: formatNumber(aiOverview.value?.total_tokens ?? 0),
    icon: 'lucide:cpu',
    bg: 'bg-success/10',
    ic: 'text-success',
  },
  {
    key: 'storage',
    label: $t('admin.dashboard.stats.storageFiles'),
    value: storageOverview.value?.total_files ?? 0,
    icon: 'lucide:hard-drive',
    bg: 'bg-warning/10',
    ic: 'text-warning',
  },
  {
    key: 'plugins',
    label: $t('admin.dashboard.stats.pluginsEnabled'),
    value: pluginOverview.value?.enabled ?? 0,
    icon: 'lucide:puzzle',
    bg: 'bg-success/10',
    ic: 'text-success',
  },
]);

// ── A10: 健康状态 ──
const healthColor = computed(() => {
  if (!health.value) return 'default';
  if (health.value.status === 'healthy') return 'success';
  if (health.value.status === 'degraded') return 'warning';
  return 'error';
});

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

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

// ── Quick Actions ──
const quickActions = computed(() => [
  {
    key: 'tenants',
    label: $t('admin.dashboard.quickActions.tenantManage'),
    desc: $t('admin.dashboard.quickActions.tenantManageDesc'),
    icon: 'lucide:building-2',
    color: 'text-primary',
    bg: 'bg-primary/10',
    route: '/admin/tenant/list',
  },
  {
    key: 'admins',
    label: $t('admin.dashboard.quickActions.adminManage'),
    desc: $t('admin.dashboard.quickActions.adminManageDesc'),
    icon: 'lucide:shield-check',
    color: 'text-success',
    bg: 'bg-success/10',
    route: '/admin/system/admins',
  },
  {
    key: 'config',
    label: $t('admin.dashboard.quickActions.systemConfig'),
    desc: $t('admin.dashboard.quickActions.systemConfigDesc'),
    icon: 'lucide:settings',
    color: 'text-warning',
    bg: 'bg-warning/10',
    route: '/admin/system/configs',
  },
  {
    key: 'ai',
    label: $t('admin.dashboard.quickActions.aiProviders'),
    desc: $t('admin.dashboard.quickActions.aiProvidersDesc'),
    icon: 'lucide:brain',
    color: 'text-primary',
    bg: 'bg-primary/10',
    route: '/admin/ai/providers',
  },
  {
    key: 'tasks',
    label: $t('admin.dashboard.quickActions.periodicTasks'),
    desc: $t('admin.dashboard.quickActions.periodicTasksDesc'),
    icon: 'lucide:clock',
    color: 'text-success',
    bg: 'bg-success/10',
    route: '/admin/system/periodic-tasks',
  },
  {
    key: 'logs',
    label: $t('admin.dashboard.quickActions.operationLogs'),
    desc: $t('admin.dashboard.quickActions.operationLogsDesc'),
    icon: 'lucide:scroll-text',
    color: 'text-warning',
    bg: 'bg-warning/10',
    route: '/admin/system/operation-logs',
  },
]);

function navigateTo(route: string) {
  router.push(route);
}

// ── A8: 企业增长趋势（简单条形图） ──
const growthChartRef = ref<EchartsUIType>();
const { renderEcharts: renderGrowthChart } = useEcharts(growthChartRef);

function renderTenantGrowthChart() {
  const data = tenantGrowth.value.slice(-10);
  if (data.length === 0) return;
  renderGrowthChart({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
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
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'bar',
        data: data.map((i) => i.count),
        itemStyle: { color: '#5B8FF9', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 24,
      },
    ],
  });
}

watch(tenantGrowth, renderTenantGrowthChart);

const currentTime = ref('');
let timeInterval: null | ReturnType<typeof setInterval> = null;
function startClock() {
  if (timeInterval) return;
  currentTime.value = formatDateUtil(new Date());
  timeInterval = setInterval(() => {
    currentTime.value = formatDateUtil(new Date());
  }, 1000);
}

function stopClock() {
  if (!timeInterval) return;
  clearInterval(timeInterval);
  timeInterval = null;
}

onMounted(startClock);
onActivated(startClock);
onDeactivated(stopClock);
onUnmounted(() => {
  stopClock();
});
</script>

<template>
  <div class="p-5">
    <!-- Welcome -->
    <Card :title="$t('admin.dashboard.platformConsole')" class="mb-4">
      <template #extra>
        <span class="text-muted-foreground">{{ currentTime }}</span>
      </template>
      <div class="text-lg">
        {{
          $t('admin.dashboard.greeting', {
            name: userStore.userInfo?.realName || $t('admin.dashboard.admin'),
          })
        }}
      </div>
      <p class="mt-2 text-muted-foreground">
        {{ $t('admin.dashboard.description') }}
      </p>
    </Card>

    <!-- A7: Stats Cards Grid (8 cards: 2 rows × 4) -->
    <Spin :spinning="loading">
      <div class="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
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

    <!-- Row 2: Health + AI Overview + Storage -->
    <div class="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
      <!-- A10: System Health -->
      <Card :title="$t('admin.dashboard.health.title')">
        <div v-if="health" class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.health.status')
            }}</span>
            <Tag :color="healthColor">{{ health.status }}</Tag>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.health.database')
            }}</span>
            <Tag :color="health.database.connected ? 'success' : 'error'">
              {{
                health.database.connected
                  ? $t('admin.dashboard.health.connected')
                  : $t('admin.dashboard.health.disconnected')
              }}
            </Tag>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">Redis</span>
            <Tag :color="health.redis.connected ? 'success' : 'error'">
              {{
                health.redis.connected
                  ? $t('admin.dashboard.health.connected')
                  : $t('admin.dashboard.health.disconnected')
              }}
            </Tag>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">Celery</span>
            <Tag :color="health.celery.connected ? 'success' : 'warning'">
              {{
                health.celery.connected
                  ? $t('admin.dashboard.health.connected')
                  : $t('admin.dashboard.health.disconnected')
              }}
            </Tag>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.health.memory')
            }}</span>
            <span class="font-mono text-sm text-foreground"
              >{{ health.memory_mb }} MB</span
            >
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.health.uptime')
            }}</span>
            <span class="font-mono text-sm text-foreground">{{
              formatUptime(health.uptime_seconds)
            }}</span>
          </div>
        </div>
        <Spin v-else />
      </Card>

      <!-- AI Overview -->
      <Card :title="$t('admin.dashboard.ai.title')">
        <div v-if="aiOverview" class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.ai.totalCalls')
            }}</span>
            <span class="font-semibold text-foreground">{{
              formatNumber(aiOverview.total_calls)
            }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.ai.todayCalls')
            }}</span>
            <span class="font-semibold text-foreground">{{
              aiOverview.today_calls
            }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.ai.totalTokens')
            }}</span>
            <span class="font-mono text-sm text-foreground">{{
              formatNumber(aiOverview.total_tokens)
            }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.ai.successRate')
            }}</span>
            <Progress
              :percent="aiOverview.success_rate"
              size="small"
              style="width: 120px"
            />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.ai.providers')
            }}</span>
            <span class="font-semibold text-foreground">{{
              aiOverview.active_providers
            }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.ai.totalCost')
            }}</span>
            <span class="font-mono text-sm text-foreground"
              >${{ aiOverview.total_cost.toFixed(4) }}</span
            >
          </div>
        </div>
        <Spin v-else />
      </Card>

      <!-- Storage Overview -->
      <Card :title="$t('admin.dashboard.storage.title')">
        <div v-if="storageOverview" class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.storage.totalFiles')
            }}</span>
            <span class="font-semibold text-foreground">{{
              storageOverview.total_files
            }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-muted-foreground">{{
              $t('admin.dashboard.storage.totalSize')
            }}</span>
            <span class="font-mono text-sm text-foreground"
              >{{ storageOverview.total_size_mb }} MB</span
            >
          </div>
          <div
            v-if="storageOverview.driver_distribution.length > 0"
            class="mt-2"
          >
            <div class="mb-1 text-xs text-muted-foreground">
              {{ $t('admin.dashboard.storage.drivers') }}
            </div>
            <div
              v-for="d in storageOverview.driver_distribution"
              :key="d.driver"
              class="flex items-center justify-between py-1"
            >
              <Tag>{{ d.driver }}</Tag>
              <span class="text-xs text-muted-foreground"
                >{{ d.file_count }}
                {{ $t('admin.dashboard.storage.files') }}</span
              >
            </div>
          </div>
        </div>
        <Spin v-else />
      </Card>
    </div>

    <!-- Row 3: Quick Actions + Tenant Growth + Recent Activities -->
    <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <!-- Quick Actions -->
      <Card :title="$t('admin.dashboard.quickActions.title')">
        <div class="grid grid-cols-2 gap-2">
          <div
            v-for="action in quickActions"
            :key="action.key"
            class="group flex cursor-pointer items-center gap-2 rounded-lg border border-transparent p-2 transition-all hover:border-primary/20 hover:bg-accent"
            @click="navigateTo(action.route)"
          >
            <div
              class="flex size-8 shrink-0 items-center justify-center rounded-lg"
              :class="action.bg"
            >
              <IconifyIcon
                :icon="action.icon"
                class="size-4"
                :class="action.color"
              />
            </div>
            <div class="min-w-0">
              <div class="truncate text-xs font-medium text-foreground">
                {{ action.label }}
              </div>
            </div>
          </div>
        </div>
      </Card>

      <!-- A8: Tenant Growth Trend (ECharts) -->
      <Card :title="$t('admin.dashboard.tenantGrowth.title')">
        <EchartsUI
          v-if="tenantGrowth.length > 0"
          ref="growthChartRef"
          height="220px"
        />
        <div v-else class="py-8 text-center text-sm text-muted-foreground">
          {{ $t('admin.dashboard.tenantGrowth.empty') }}
        </div>
      </Card>

      <!-- A9: Recent Activities Timeline -->
      <Card :title="$t('admin.dashboard.activities.title')">
        <div
          v-if="activities.length > 0"
          class="max-h-80 space-y-2 overflow-y-auto"
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
                  · {{ act.module || '' }} · {{ act.action || '' }}</span
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
          {{ $t('admin.dashboard.activities.empty') }}
        </div>
      </Card>
    </div>
  </div>
</template>
