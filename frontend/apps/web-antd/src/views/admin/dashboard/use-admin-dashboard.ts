import type { AdminDashboardOverview } from '#/api/admin/dashboard';
import type {
  DashboardActivityActor,
  DashboardActivityEntry,
  DashboardActivityIdentitySource,
  DashboardChip,
  DashboardHeroAction,
  DashboardMetricCard,
  DashboardRouteCardItem,
  DashboardSpotlightItem,
  DashboardSummaryPanel,
} from '#/views/_shared/dashboard/types';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

import { computed, onMounted, ref } from 'vue';

import { getDashboardOverviewApi } from '#/api/admin/dashboard';
import { createIdentityDisplayModel } from '#/components/business/identity-display';
import { $t } from '#/locales';
import {
  useNotificationStore,
  usePresenceStore,
  useSocketIOStore,
} from '#/store';
import { formatDate } from '#/utils/common';
import { useDashboardRealtimeRefresh } from '#/views/_shared/dashboard/use-dashboard-realtime-refresh';
import {
  formatCompactNumber,
  formatCurrency,
  formatUptime,
  getSocketStatusLabel,
  getSocketStatusTone,
} from '#/views/_shared/dashboard/utils';

type AdminDashboardActivityItem =
  AdminDashboardOverview['recent_activities'][number] &
    DashboardActivityIdentitySource;

const DASHBOARD_IDENTITY_TYPES = new Set([
  'admin',
  'tenant_admin',
  'tenant_user',
]);

function resolveActivityRoleName(
  activity: DashboardActivityIdentitySource,
): string | undefined {
  if (Object.prototype.hasOwnProperty.call(activity, 'display_role_name')) {
    return activity.display_role_name?.trim() || undefined;
  }
  return activity.role_name?.trim() || undefined;
}

function hasActivityActorName(
  activity: DashboardActivityIdentitySource,
): boolean {
  return [activity.display_name, activity.nickname, activity.username].some(
    (value) => typeof value === 'string' && value.trim().length > 0,
  );
}

function buildActivityIdentityMeta(
  activity: DashboardActivityIdentitySource,
): IdentityDetailMeta {
  const normalizedUserType =
    typeof activity.user_type === 'string' ? activity.user_type.trim() : '';
  const roleName = resolveActivityRoleName(activity);
  return {
    orgNodeName: activity.org_node_name ?? undefined,
    roleName,
    scope: 'admin',
    subjectType: normalizedUserType || undefined,
    userType: normalizedUserType || undefined,
    username: activity.username ?? undefined,
  };
}

function buildDashboardActivityActor(
  activity: AdminDashboardActivityItem,
  systemLabel: string,
): DashboardActivityActor {
  const hasActorName = hasActivityActorName(activity);
  const normalizedUserType =
    typeof activity.user_type === 'string' ? activity.user_type.trim() : '';
  const roleName = resolveActivityRoleName(activity);

  return {
    interactive:
      typeof activity.user_id === 'number' &&
      Number.isFinite(activity.user_id) &&
      DASHBOARD_IDENTITY_TYPES.has(normalizedUserType),
    meta: buildActivityIdentityMeta(activity),
    model: createIdentityDisplayModel({
      avatar: activity.avatar ?? undefined,
      displayName: hasActorName
        ? (activity.display_name ?? undefined)
        : systemLabel,
      id: activity.user_id ?? `admin-dashboard-activity-${activity.id}`,
      isActive: activity.is_active,
      isLeader: activity.is_leader,
      isOwner: activity.is_owner,
      nickname: activity.nickname ?? (hasActorName ? undefined : systemLabel),
      orgNodeId: activity.org_node_id ?? undefined,
      orgNodeName: activity.org_node_name ?? undefined,
      roleName,
      userType: normalizedUserType || undefined,
      username: activity.username ?? undefined,
    }),
  };
}

function createEmptyOverview(): AdminDashboardOverview {
  return {
    ai_overview: {
      active_providers: 0,
      success_rate: 0,
      today_calls: 0,
      today_tokens: 0,
      total_calls: 0,
      total_cost: 0,
      total_tokens: 0,
    },
    generated_at: null,
    health: {
      celery: { connected: false },
      database: { connected: false },
      memory_mb: 0,
      redis: { connected: false },
      status: 'unhealthy',
      uptime_seconds: 0,
    },
    plugin_overview: {
      disabled: 0,
      enabled: 0,
      error_count: 0,
      total: 0,
    },
    recent_activities: [],
    stats: {
      active_tenants: 0,
      today_login: 0,
      total_tenants: 0,
      total_users: 0,
    },
    storage_overview: {
      driver_distribution: [],
      total_files: 0,
      total_size_bytes: 0,
      total_size_mb: 0,
    },
    tenant_growth: [],
  };
}

export function useAdminDashboard() {
  const loading = ref(false);
  const overview = ref<AdminDashboardOverview>(createEmptyOverview());

  const presenceStore = usePresenceStore();
  const notificationStore = useNotificationStore();
  const socketStore = useSocketIOStore();

  const stats = computed(() => overview.value.stats);
  const health = computed(() => overview.value.health);
  const aiOverview = computed(() => overview.value.ai_overview);
  const storageOverview = computed(() => overview.value.storage_overview);
  const pluginOverview = computed(() => overview.value.plugin_overview);
  const tenantGrowth = computed(() => overview.value.tenant_growth);
  const activityEntries = computed<DashboardActivityEntry[]>(() => {
    const systemActorLabel = $t('admin.dashboard.controlTower.systemActor');
    return overview.value.recent_activities.map((activity) => {
      const nextActivity = activity as AdminDashboardActivityItem;
      return {
        actor: buildDashboardActivityActor(nextActivity, systemActorLabel),
        createdAt: nextActivity.created_at,
        detail:
          [nextActivity.module, nextActivity.action]
            .filter(Boolean)
            .join(' / ') || $t('admin.dashboard.controlTower.unknownModule'),
        id: nextActivity.id,
        method: nextActivity.method,
        path: nextActivity.path,
        statusCode: nextActivity.status_code,
      };
    });
  });

  async function loadDashboardData(options: { silent?: boolean } = {}) {
    if (!options.silent) {
      loading.value = true;
    }
    try {
      overview.value = await getDashboardOverviewApi();
    } finally {
      if (!options.silent) {
        loading.value = false;
      }
    }
  }

  async function loadRealtimeSignals() {
    await Promise.allSettled([
      presenceStore.loadAdminPresence(),
      notificationStore.loadUnreadCount(),
    ]);
  }

  async function loadAll(options: { silent?: boolean } = {}) {
    await Promise.all([loadDashboardData(options), loadRealtimeSignals()]);
  }

  const activeTenantRate = computed(() => {
    if (stats.value.total_tenants === 0) {
      return 0;
    }
    return Math.round(
      (stats.value.active_tenants / stats.value.total_tenants) * 100,
    );
  });

  const avgUsersPerTenant = computed(() => {
    if (stats.value.active_tenants === 0) {
      return 0;
    }
    return Math.round(stats.value.total_users / stats.value.active_tenants);
  });

  const healthTone = computed(() => {
    switch (health.value.status) {
      case 'degraded': {
        return {
          badge: 'bg-amber-500/12 text-amber-700 dark:text-amber-300',
          border: 'border-amber-500/20',
          dot: 'bg-amber-500',
        };
      }
      case 'healthy': {
        return {
          badge: 'bg-emerald-500/12 text-emerald-700 dark:text-emerald-300',
          border: 'border-emerald-500/20',
          dot: 'bg-emerald-500',
        };
      }
      default: {
        return {
          badge: 'bg-destructive/12 text-destructive',
          border: 'border-destructive/20',
          dot: 'bg-destructive',
        };
      }
    }
  });

  const socketTone = computed(() => getSocketStatusTone(socketStore.status));

  const realtimeChips = computed<DashboardChip[]>(() => [
    {
      badge: 'bg-background/90 text-muted-foreground',
      border: 'border-border/70',
      icon: 'lucide:clock-3',
      key: 'snapshot',
      text: formatDate(overview.value.generated_at),
    },
    {
      badge: healthTone.value.badge,
      border: healthTone.value.border,
      icon: 'lucide:shield-check',
      key: 'health',
      text: health.value.status || $t('admin.dashboard.controlTower.unknown'),
    },
    {
      badge: socketTone.value.badge,
      border: socketTone.value.border,
      icon: 'lucide:radio-tower',
      key: 'socket',
      text: getSocketStatusLabel(socketStore.status),
    },
    {
      badge: 'bg-sky-500/12 text-sky-700 dark:text-sky-300',
      border: 'border-sky-500/20',
      icon: 'lucide:users-round',
      key: 'onlineAdmins',
      text: $t('admin.dashboard.realtime.onlineAdmins', {
        count: presenceStore.getOnlineCount('admin'),
      }),
    },
    {
      badge: 'bg-primary/10 text-primary',
      border: 'border-primary/20',
      icon: 'lucide:bell-ring',
      key: 'notifications',
      text: $t('admin.dashboard.realtime.unreadNotifications', {
        count: notificationStore.unreadCount,
      }),
    },
  ]);

  const heroActions = computed<DashboardHeroAction[]>(() => [
    {
      icon: 'lucide:building-2',
      key: 'tenants',
      label: $t('admin.dashboard.controlTower.actions.tenantsTitle'),
      route: '/admin/tenant/list',
      variant: 'primary',
    },
    {
      icon: 'lucide:activity',
      key: 'usage',
      label: $t('admin.dashboard.controlTower.actions.usageTitle'),
      route: '/admin/ai/usage',
      variant: 'secondary',
    },
  ]);

  const overviewCards = computed<DashboardMetricCard[]>(() => [
    {
      icon: 'lucide:building-2',
      key: 'tenants',
      label: $t('admin.dashboard.command.metrics.tenants'),
      value: formatCompactNumber(stats.value.total_tenants),
    },
    {
      icon: 'lucide:gauge',
      key: 'activeRate',
      label: $t('admin.dashboard.command.metrics.activeRate'),
      value: `${activeTenantRate.value}%`,
    },
    {
      icon: 'lucide:users-round',
      key: 'users',
      label: $t('admin.dashboard.command.metrics.users'),
      value: formatCompactNumber(stats.value.total_users),
    },
    {
      icon: 'lucide:brain',
      key: 'calls',
      label: $t('admin.dashboard.command.metrics.callsToday'),
      value: formatCompactNumber(aiOverview.value.today_calls),
    },
  ]);

  const growthSummary = computed(() => {
    const currentWindow = tenantGrowth.value.slice(-7);
    const previousWindow = tenantGrowth.value.slice(-14, -7);
    const currentCount = currentWindow.reduce(
      (sum, item) => sum + item.count,
      0,
    );
    const previousCount = previousWindow.reduce(
      (sum, item) => sum + item.count,
      0,
    );
    let delta = 0;
    if (previousCount === 0) {
      delta = currentCount > 0 ? 100 : 0;
    } else {
      delta = Math.round(
        ((currentCount - previousCount) / previousCount) * 100,
      );
    }

    return {
      delta,
      recent: currentCount,
    };
  });

  const pluginSpotlightTone = computed<DashboardSpotlightItem['tone']>(() => {
    if (pluginOverview.value.error_count > 0) {
      return 'warning';
    }
    if (pluginOverview.value.enabled > 0) {
      return 'positive';
    }
    return 'default';
  });

  const spotlightCards = computed<DashboardSpotlightItem[]>(() => [
    {
      detail: `${growthSummary.value.delta}%`,
      icon: 'lucide:trending-up',
      key: 'growth',
      label: $t('admin.dashboard.spotlights.growth'),
      tone: growthSummary.value.delta >= 0 ? 'positive' : 'warning',
      value: formatCompactNumber(growthSummary.value.recent),
    },
    {
      icon: 'lucide:badge-dollar-sign',
      key: 'cost',
      label: $t('admin.dashboard.spotlights.cost'),
      value: formatCurrency(aiOverview.value.total_cost),
    },
    {
      icon: 'lucide:plug-zap',
      key: 'plugins',
      label: $t('admin.dashboard.spotlights.plugins'),
      tone: pluginSpotlightTone.value,
      value: formatCompactNumber(pluginOverview.value.enabled),
    },
    {
      icon: 'lucide:timer-reset',
      key: 'runtime',
      label: $t('admin.dashboard.spotlights.runtime'),
      value: formatUptime(health.value.uptime_seconds),
    },
  ]);

  const signalCards = computed<DashboardRouteCardItem[]>(() => [
    {
      description:
        health.value.status === 'healthy'
          ? $t('admin.dashboard.controlTower.signals.healthHealthy')
          : $t('admin.dashboard.controlTower.signals.healthAttention'),
      icon: 'lucide:shield-check',
      key: 'health',
      route: '/admin/system/operation-logs',
      title: $t('admin.dashboard.controlTower.signals.healthTitle'),
      value: health.value.status || $t('admin.dashboard.controlTower.unknown'),
    },
    {
      description:
        pluginOverview.value.error_count > 0
          ? $t('admin.dashboard.controlTower.signals.pluginAttention')
          : $t('admin.dashboard.controlTower.signals.pluginHealthy'),
      icon: 'lucide:puzzle',
      key: 'plugins',
      route: '/admin/system/operation-logs',
      title: $t('admin.dashboard.controlTower.signals.pluginTitle'),
      value: formatCompactNumber(pluginOverview.value.enabled),
    },
    {
      description:
        aiOverview.value.success_rate >= 95
          ? $t('admin.dashboard.controlTower.signals.aiHealthy')
          : $t('admin.dashboard.controlTower.signals.aiAttention'),
      icon: 'lucide:cpu',
      key: 'ai',
      route: '/admin/ai/usage',
      title: $t('admin.dashboard.controlTower.signals.aiTitle'),
      value: `${Math.round(aiOverview.value.success_rate)}%`,
    },
    {
      description: $t('admin.dashboard.controlTower.signals.usersDesc', {
        count: avgUsersPerTenant.value,
      }),
      icon: 'lucide:users',
      key: 'users',
      route: '/admin/tenant/list',
      title: $t('admin.dashboard.controlTower.signals.usersTitle'),
      value: formatCompactNumber(avgUsersPerTenant.value),
    },
  ]);

  const actionDeck = computed<DashboardRouteCardItem[]>(() => [
    {
      description: $t('admin.dashboard.controlTower.actions.tenantsDesc'),
      icon: 'lucide:building-2',
      key: 'tenants',
      route: '/admin/tenant/list',
      title: $t('admin.dashboard.controlTower.actions.tenantsTitle'),
    },
    {
      description: $t('admin.dashboard.controlTower.actions.plansDesc'),
      icon: 'lucide:layers-3',
      key: 'plans',
      route: '/admin/tenant/plans',
      title: $t('admin.dashboard.controlTower.actions.plansTitle'),
    },
    {
      description: $t('admin.dashboard.controlTower.actions.providersDesc'),
      icon: 'lucide:brain',
      key: 'providers',
      route: '/admin/ai/providers',
      title: $t('admin.dashboard.controlTower.actions.providersTitle'),
    },
    {
      description: $t('admin.dashboard.controlTower.actions.usageDesc'),
      icon: 'lucide:activity',
      key: 'usage',
      route: '/admin/ai/usage',
      title: $t('admin.dashboard.controlTower.actions.usageTitle'),
    },
    {
      description: $t('admin.dashboard.controlTower.actions.tasksDesc'),
      icon: 'lucide:clock-3',
      key: 'tasks',
      route: '/admin/system/periodic-tasks',
      title: $t('admin.dashboard.controlTower.actions.tasksTitle'),
    },
    {
      description: $t('admin.dashboard.controlTower.actions.logsDesc'),
      icon: 'lucide:scroll-text',
      key: 'logs',
      route: '/admin/system/operation-logs',
      title: $t('admin.dashboard.controlTower.actions.logsTitle'),
    },
  ]);

  const infrastructurePanels = computed<DashboardSummaryPanel[]>(() => [
    {
      icon: 'lucide:brain-circuit',
      key: 'ai',
      rows: [
        {
          label: $t('admin.dashboard.infrastructure.ai.calls'),
          value: formatCompactNumber(aiOverview.value.total_calls),
        },
        {
          label: $t('admin.dashboard.infrastructure.ai.tokens'),
          value: formatCompactNumber(aiOverview.value.total_tokens),
        },
        {
          label: $t('admin.dashboard.infrastructure.ai.cost'),
          value: formatCurrency(aiOverview.value.total_cost),
        },
      ],
      title: $t('admin.dashboard.infrastructure.ai.title'),
    },
    {
      icon: 'lucide:database-zap',
      key: 'system',
      rows: [
        {
          label: $t('admin.dashboard.infrastructure.system.database'),
          value: health.value.database.connected
            ? $t('admin.dashboard.connected')
            : $t('admin.dashboard.disconnected'),
        },
        {
          label: $t('admin.dashboard.infrastructure.system.redis'),
          value: health.value.redis.connected
            ? $t('admin.dashboard.connected')
            : $t('admin.dashboard.disconnected'),
        },
        {
          label: $t('admin.dashboard.infrastructure.system.celery'),
          value: health.value.celery.connected
            ? $t('admin.dashboard.connected')
            : $t('admin.dashboard.disconnected'),
        },
      ],
      title: $t('admin.dashboard.infrastructure.system.title'),
    },
    {
      icon: 'lucide:hard-drive',
      key: 'storage',
      rows: [
        {
          label: $t('admin.dashboard.infrastructure.storage.files'),
          value: formatCompactNumber(storageOverview.value.total_files),
        },
        {
          label: $t('admin.dashboard.infrastructure.storage.size'),
          value: `${storageOverview.value.total_size_mb} MB`,
        },
        {
          label: $t('admin.dashboard.infrastructure.storage.drivers'),
          value: formatCompactNumber(
            storageOverview.value.driver_distribution.length,
          ),
        },
      ],
      title: $t('admin.dashboard.infrastructure.storage.title'),
    },
    {
      icon: 'lucide:plug-zap',
      key: 'plugins',
      rows: [
        {
          label: $t('admin.dashboard.infrastructure.plugins.enabled'),
          value: formatCompactNumber(pluginOverview.value.enabled),
        },
        {
          label: $t('admin.dashboard.infrastructure.plugins.disabled'),
          value: formatCompactNumber(pluginOverview.value.disabled),
        },
        {
          label: $t('admin.dashboard.infrastructure.plugins.errors'),
          value: formatCompactNumber(pluginOverview.value.error_count),
        },
      ],
      title: $t('admin.dashboard.infrastructure.plugins.title'),
    },
  ]);

  const runtimeValue = computed(() =>
    formatUptime(health.value.uptime_seconds),
  );

  const condensedActivityEntries = computed(() =>
    activityEntries.value.slice(0, 6),
  );

  useDashboardRealtimeRefresh(
    async () => {
      await loadAll({ silent: true });
    },
    {
      events: ['notification'],
      refreshOnConnect: true,
    },
  );

  onMounted(() => {
    void loadAll();
  });

  return {
    actionDeck,
    activityEntries: condensedActivityEntries,
    aiOverview,
    growthSummary,
    health,
    healthTone,
    heroActions,
    infrastructurePanels,
    loading,
    overviewCards,
    pluginOverview,
    realtimeChips,
    runtimeValue,
    signalCards,
    spotlightCards,
    stats,
    storageOverview,
    tenantGrowth,
  };
}
