<script lang="ts" setup>
/**
 * Tenant Dashboard — 综合数据面板
 *
 * B5: 统计卡片 + 快捷操作
 * B6: AI 使用趋势
 * B7: 近期活动时间线
 */
import { computed, onMounted, ref } from 'vue';

import { useUserStore } from '@vben/stores';
import { IconifyIcon } from '@vben/icons';

import { Card, Spin, Tag } from 'ant-design-vue';

import {
  type AITrendItem,
  type TenantActivityItem,
  type TenantDashboardStats,
  getAITrendApi,
  getTenantDashboardStatsApi,
  getTenantRecentActivitiesApi,
} from '#/api/tenant/dashboard';
import { $t } from '#/locales';
import { useRouter } from 'vue-router';

defineOptions({ name: 'TenantDashboard' });

const router = useRouter();
const userStore = useUserStore();
const loading = ref(false);

const stats = ref<TenantDashboardStats>({
  total_users: 0, active_users: 0, api_calls: 0,
  total_tokens: 0, total_cost: 0, storage_used_bytes: 0, storage_used_mb: 0,
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

onMounted(() => { loadAll(); });

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  try { return new Date(dateStr).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return dateStr; }
}

const methodColors: Record<string, string> = { GET: 'blue', POST: 'green', PUT: 'orange', DELETE: 'red', PATCH: 'purple' };

// B5: 统计卡片
const statCards = computed(() => [
  { key: 'users', label: $t('tenant.dashboard.stats.totalUsers'), value: stats.value.total_users, icon: 'lucide:users', bg: 'bg-primary/10', ic: 'text-primary' },
  { key: 'active', label: $t('tenant.dashboard.stats.activeUsers'), value: stats.value.active_users, icon: 'lucide:activity', bg: 'bg-success/10', ic: 'text-success' },
  { key: 'calls', label: $t('tenant.dashboard.stats.apiCalls'), value: formatNumber(stats.value.api_calls), icon: 'lucide:brain', bg: 'bg-warning/10', ic: 'text-warning' },
  { key: 'tokens', label: $t('tenant.dashboard.stats.totalTokens'), value: formatNumber(stats.value.total_tokens), icon: 'lucide:cpu', bg: 'bg-primary/10', ic: 'text-primary' },
  { key: 'cost', label: $t('tenant.dashboard.stats.totalCost'), value: `$${stats.value.total_cost.toFixed(2)}`, icon: 'lucide:dollar-sign', bg: 'bg-success/10', ic: 'text-success' },
  { key: 'storage', label: $t('tenant.dashboard.stats.storageUsed'), value: `${stats.value.storage_used_mb} MB`, icon: 'lucide:hard-drive', bg: 'bg-warning/10', ic: 'text-warning' },
]);

// B6: AI 趋势
const maxTrendCalls = computed(() => Math.max(...aiTrend.value.map(i => i.calls), 1));

// 快捷操作
const quickActions = computed(() => [
  { key: 'chat', label: $t('tenant.dashboard.quickActions.aiChat'), icon: 'lucide:message-square', bg: 'bg-primary/10', color: 'text-primary', route: '/tenant/ai/chat' },
  { key: 'agents', label: $t('tenant.dashboard.quickActions.agents'), icon: 'lucide:bot', bg: 'bg-success/10', color: 'text-success', route: '/tenant/ai/agents' },
  { key: 'kb', label: $t('tenant.dashboard.quickActions.knowledgeBases'), icon: 'lucide:book-open', bg: 'bg-warning/10', color: 'text-warning', route: '/tenant/ai/knowledge-bases' },
  { key: 'logs', label: $t('tenant.dashboard.quickActions.callLogs'), icon: 'lucide:scroll-text', bg: 'bg-primary/10', color: 'text-primary', route: '/tenant/ai/call-logs' },
]);

function navigateTo(route: string) { router.push(route); }
</script>

<template>
  <div class="p-5">
    <!-- Welcome -->
    <Card :title="$t('tenant.dashboard.title')" class="mb-4">
      <template #extra>
        <span class="text-muted-foreground">{{ $t('tenant.dashboard.welcome') }}</span>
      </template>
      <div class="text-lg">
        {{ $t('tenant.dashboard.greeting', { name: userStore.userInfo?.realName || $t('tenant.common.admin') }) }}
      </div>
      <p class="mt-2 text-muted-foreground">{{ $t('tenant.dashboard.description') }}</p>
    </Card>

    <!-- B5: Stats Cards Grid (6 cards) -->
    <Spin :spinning="loading">
      <div class="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card v-for="stat in statCards" :key="stat.key" :body-style="{ padding: '20px' }">
          <div class="flex items-center gap-4">
            <div class="flex size-12 items-center justify-center rounded-xl" :class="stat.bg">
              <IconifyIcon :icon="stat.icon" class="size-6" :class="stat.ic" />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">{{ stat.label }}</div>
              <div class="text-2xl font-bold text-foreground">{{ stat.value }}</div>
            </div>
          </div>
        </Card>
      </div>
    </Spin>

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
            <div class="flex size-10 shrink-0 items-center justify-center rounded-lg" :class="action.bg">
              <IconifyIcon :icon="action.icon" class="size-5" :class="action.color" />
            </div>
            <span class="text-sm font-medium text-foreground">{{ action.label }}</span>
          </div>
        </div>
      </Card>

      <!-- B6: AI Usage Trend (CSS bar chart) -->
      <Card :title="$t('tenant.dashboard.aiTrend.title')">
        <div v-if="aiTrend.length" class="space-y-1.5">
          <div v-for="item in aiTrend" :key="item.date" class="flex items-center gap-2">
            <span class="w-14 shrink-0 text-right text-xs text-muted-foreground">{{ item.date.slice(5) }}</span>
            <div class="flex-1">
              <div
                class="h-5 rounded bg-primary/20 transition-all"
                :style="{ width: `${Math.max((item.calls / maxTrendCalls) * 100, 4)}%` }"
              >
                <span class="px-1 text-xs font-medium leading-5 text-primary">{{ item.calls }}</span>
              </div>
            </div>
            <span class="w-14 text-right text-xs text-muted-foreground">{{ formatNumber(item.tokens) }}t</span>
          </div>
        </div>
        <div v-else class="py-8 text-center text-sm text-muted-foreground">{{ $t('tenant.dashboard.aiTrend.empty') }}</div>
      </Card>

      <!-- B7: Recent Activities -->
      <Card :title="$t('tenant.dashboard.activities.title')">
        <div v-if="activities.length" class="max-h-72 space-y-2 overflow-y-auto">
          <div v-for="act in activities" :key="act.id" class="flex items-start gap-2 border-b border-border/50 pb-2 last:border-0">
            <Tag :color="methodColors[act.method] || 'default'" class="shrink-0 text-xs">{{ act.method }}</Tag>
            <div class="min-w-0 flex-1">
              <div class="truncate text-xs text-foreground">
                <span class="font-medium">{{ act.username || '—' }}</span>
                <span class="text-muted-foreground"> · {{ act.module || '' }}</span>
              </div>
              <div class="truncate text-xs text-muted-foreground">{{ act.path }}</div>
            </div>
            <span class="shrink-0 text-xs text-muted-foreground">{{ formatDate(act.created_at) }}</span>
          </div>
        </div>
        <div v-else class="py-8 text-center text-sm text-muted-foreground">{{ $t('tenant.dashboard.activities.empty') }}</div>
      </Card>
    </div>
  </div>
</template>
