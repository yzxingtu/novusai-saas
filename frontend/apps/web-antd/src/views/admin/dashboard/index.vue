<script lang="ts" setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';

import { useUserStore } from '@vben/stores';
import { IconifyIcon } from '@vben/icons';

import { Card, Spin } from 'ant-design-vue';

import { type DashboardStats, getDashboardStatsApi } from '#/api/admin/dashboard';
import { $t } from '#/locales';
import { useRouter } from 'vue-router';

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

async function loadStats() {
  loading.value = true;
  try {
    stats.value = await getDashboardStatsApi();
  } catch {
    // error handled by global interceptor
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadStats();
});

const statCards = computed(() => [
  {
    key: 'totalTenants',
    label: $t('admin.dashboard.stats.totalTenants'),
    value: stats.value.total_tenants,
    icon: 'lucide:building-2',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
  {
    key: 'activeTenants',
    label: $t('admin.dashboard.stats.activeTenants'),
    value: stats.value.active_tenants,
    icon: 'lucide:activity',
    bgClass: 'bg-success/10',
    iconClass: 'text-success',
  },
  {
    key: 'totalUsers',
    label: $t('admin.dashboard.stats.totalUsers'),
    value: stats.value.total_users,
    icon: 'lucide:users',
    bgClass: 'bg-warning/10',
    iconClass: 'text-warning',
  },
  {
    key: 'todayLogin',
    label: $t('admin.dashboard.stats.todayLogin'),
    value: stats.value.today_login,
    icon: 'lucide:log-in',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
]);

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

const currentTime = ref('');
let timeInterval: ReturnType<typeof setInterval> | null = null;

function updateTime() {
  currentTime.value = new Date().toLocaleString();
}

onMounted(() => {
  updateTime();
  timeInterval = setInterval(updateTime, 1000);
});

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval);
  }
});
</script>

<template>
  <div class="p-5">
    <!-- Welcome -->
    <Card :title="$t('admin.dashboard.platformConsole')" class="mb-4">
      <template #extra>
        <span class="text-muted-foreground">{{ $t('admin.dashboard.welcome') }}</span>
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

    <!-- Stats Cards -->
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
              :class="stat.bgClass"
            >
              <IconifyIcon
                :icon="stat.icon"
                class="size-6"
                :class="stat.iconClass"
              />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">{{ stat.label }}</div>
              <div class="text-2xl font-bold text-foreground">{{ stat.value }}</div>
            </div>
          </div>
        </Card>
      </div>
    </Spin>

    <!-- Quick Actions + System Overview -->
    <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <!-- Quick Actions -->
      <Card :title="$t('admin.dashboard.quickActions.title')" class="lg:col-span-2">
        <div class="grid grid-cols-2 gap-3 md:grid-cols-3">
          <div
            v-for="action in quickActions"
            :key="action.key"
            class="group flex cursor-pointer items-center gap-3 rounded-lg border border-transparent p-3 transition-all hover:border-primary/20 hover:bg-accent"
            @click="navigateTo(action.route)"
          >
            <div
              class="flex size-10 shrink-0 items-center justify-center rounded-lg transition-transform group-hover:scale-110"
              :class="action.bg"
            >
              <IconifyIcon
                :icon="action.icon"
                class="size-5"
                :class="action.color"
              />
            </div>
            <div class="min-w-0">
              <div class="truncate text-sm font-medium text-foreground">
                {{ action.label }}
              </div>
              <div class="truncate text-xs text-muted-foreground">
                {{ action.desc }}
              </div>
            </div>
          </div>
        </div>
      </Card>

      <!-- System Overview -->
      <Card :title="$t('admin.dashboard.systemOverview.title')">
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 text-sm text-muted-foreground">
              <IconifyIcon icon="lucide:tag" class="size-4" />
              {{ $t('admin.dashboard.systemOverview.version') }}
            </div>
            <span class="font-mono text-sm font-medium text-foreground">v1.0.0</span>
          </div>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 text-sm text-muted-foreground">
              <IconifyIcon icon="lucide:server" class="size-4" />
              {{ $t('admin.dashboard.systemOverview.environment') }}
            </div>
            <span class="rounded bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
              Production
            </span>
          </div>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 text-sm text-muted-foreground">
              <IconifyIcon icon="lucide:clock" class="size-4" />
              {{ $t('admin.dashboard.systemOverview.currentTime') }}
            </div>
            <span class="font-mono text-sm text-foreground">{{ currentTime }}</span>
          </div>
        </div>
      </Card>
    </div>
  </div>
</template>
