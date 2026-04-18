import type { TenantDashboardOverview } from '#/api/tenant/dashboard';
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

import { getTenantDashboardOverviewApi } from '#/api/tenant/dashboard';
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
  getSocketStatusLabel,
  getSocketStatusTone,
} from '#/views/_shared/dashboard/utils';

type TenantDashboardActivityItem = DashboardActivityIdentitySource &
  TenantDashboardOverview['recent_activities'][number];

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
    scope: 'tenant',
    subjectType: normalizedUserType || undefined,
    userType: normalizedUserType || undefined,
    username: activity.username ?? undefined,
  };
}

function buildDashboardActivityActor(
  activity: TenantDashboardActivityItem,
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
      id: activity.user_id ?? `tenant-dashboard-activity-${activity.id}`,
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

function createEmptyOverview(): TenantDashboardOverview {
  return {
    ai_trend: [],
    generated_at: null,
    recent_activities: [],
    stats: {
      active_users: 0,
      api_calls: 0,
      monthly_conversations: 0,
      storage_used_bytes: 0,
      storage_used_mb: 0,
      total_agents: 0,
      total_cost: 0,
      total_kb_documents: 0,
      total_knowledge_bases: 0,
      total_tokens: 0,
      total_users: 0,
    },
    storage_detail: {
      total_files: 0,
      total_size_bytes: 0,
      total_size_mb: 0,
      type_distribution: [],
    },
  };
}

export function useTenantDashboard() {
  const loading = ref(false);
  const overview = ref<TenantDashboardOverview>(createEmptyOverview());

  const presenceStore = usePresenceStore();
  const notificationStore = useNotificationStore();
  const socketStore = useSocketIOStore();

  const stats = computed(() => overview.value.stats);
  const aiTrend = computed(() => overview.value.ai_trend);
  const storageDetail = computed(() => overview.value.storage_detail);

  async function loadDashboardData(options: { silent?: boolean } = {}) {
    if (!options.silent) {
      loading.value = true;
    }
    try {
      overview.value = await getTenantDashboardOverviewApi();
    } finally {
      if (!options.silent) {
        loading.value = false;
      }
    }
  }

  async function loadRealtimeSignals() {
    await Promise.allSettled([
      presenceStore.loadCurrentTenantPresence(),
      presenceStore.loadTenantUserPresence(),
      notificationStore.loadUnreadCount(),
    ]);
  }

  async function loadAll(options: { silent?: boolean } = {}) {
    await Promise.all([loadDashboardData(options), loadRealtimeSignals()]);
  }

  const activeUserRate = computed(() => {
    if (stats.value.total_users === 0) {
      return 0;
    }
    return Math.round(
      (stats.value.active_users / stats.value.total_users) * 100,
    );
  });

  const avgConversationPerAgent = computed(() => {
    if (stats.value.total_agents === 0) {
      return 0;
    }
    return Math.round(
      stats.value.monthly_conversations / stats.value.total_agents,
    );
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
      badge: socketTone.value.badge,
      border: socketTone.value.border,
      icon: 'lucide:radio-tower',
      key: 'socket',
      text: getSocketStatusLabel(socketStore.status),
    },
    {
      badge: 'bg-sky-500/12 text-sky-700 dark:text-sky-300',
      border: 'border-sky-500/20',
      icon: 'lucide:shield-check',
      key: 'tenantAdmins',
      text: $t('tenant.dashboard.realtime.onlineAdmins', {
        count: presenceStore.getOnlineCount('tenant_admin'),
      }),
    },
    {
      badge: 'bg-emerald-500/12 text-emerald-700 dark:text-emerald-300',
      border: 'border-emerald-500/20',
      icon: 'lucide:users-round',
      key: 'tenantUsers',
      text: $t('tenant.dashboard.realtime.onlineUsers', {
        count: presenceStore.getOnlineCount('tenant_user'),
      }),
    },
    {
      badge: 'bg-primary/10 text-primary',
      border: 'border-primary/20',
      icon: 'lucide:bell-ring',
      key: 'notifications',
      text: $t('tenant.dashboard.realtime.unreadNotifications', {
        count: notificationStore.unreadCount,
      }),
    },
  ]);

  const heroActions = computed<DashboardHeroAction[]>(() => [
    {
      icon: 'lucide:bot',
      key: 'agents',
      label: $t('tenant.dashboard.cockpit.primaryCta'),
      route: '/tenant/ai/agents',
      variant: 'primary',
    },
    {
      icon: 'lucide:activity',
      key: 'usage',
      label: $t('tenant.dashboard.cockpit.secondaryCta'),
      route: '/tenant/ai/usage',
      variant: 'secondary',
    },
  ]);

  const overviewCards = computed<DashboardMetricCard[]>(() => [
    {
      icon: 'lucide:users-round',
      key: 'users',
      label: $t('tenant.dashboard.cockpit.metrics.users'),
      value: formatCompactNumber(stats.value.total_users),
    },
    {
      icon: 'lucide:gauge',
      key: 'activeRate',
      label: $t('tenant.dashboard.cockpit.metrics.activeRate'),
      value: `${activeUserRate.value}%`,
    },
    {
      icon: 'lucide:message-square',
      key: 'conversations',
      label: $t('tenant.dashboard.cockpit.metrics.conversations'),
      value: formatCompactNumber(stats.value.monthly_conversations),
    },
    {
      icon: 'lucide:brain',
      key: 'calls',
      label: $t('tenant.dashboard.cockpit.metrics.calls'),
      value: formatCompactNumber(stats.value.api_calls),
    },
  ]);

  const spotlightCards = computed<DashboardSpotlightItem[]>(() => [
    {
      icon: 'lucide:file-stack',
      key: 'documents',
      label: $t('tenant.dashboard.cockpit.spotlights.documents'),
      value: formatCompactNumber(stats.value.total_kb_documents),
    },
    {
      icon: 'lucide:files',
      key: 'files',
      label: $t('tenant.dashboard.cockpit.spotlights.files'),
      value: formatCompactNumber(storageDetail.value.total_files),
    },
    {
      icon: 'lucide:badge-dollar-sign',
      key: 'cost',
      label: $t('tenant.dashboard.cockpit.spotlights.cost'),
      value: formatCurrency(stats.value.total_cost),
    },
    {
      icon: 'lucide:hard-drive',
      key: 'storage',
      label: $t('tenant.dashboard.cockpit.spotlights.storage'),
      value: `${stats.value.storage_used_mb} MB`,
    },
  ]);

  const operationalSignals = computed<DashboardRouteCardItem[]>(() => [
    {
      description: $t('tenant.dashboard.cockpit.signals.agentsDesc'),
      icon: 'lucide:bot',
      key: 'agents',
      route: '/tenant/ai/agents',
      title: $t('tenant.dashboard.cockpit.signals.agentsTitle'),
      value: formatCompactNumber(stats.value.total_agents),
    },
    {
      description: $t('tenant.dashboard.cockpit.signals.kbDesc'),
      icon: 'lucide:book-open',
      key: 'knowledge',
      route: '/tenant/ai/knowledge-bases',
      title: $t('tenant.dashboard.cockpit.signals.kbTitle'),
      value: formatCompactNumber(stats.value.total_knowledge_bases),
    },
    {
      description: $t('tenant.dashboard.cockpit.signals.storageDesc'),
      icon: 'lucide:hard-drive',
      key: 'storage',
      route: '/tenant/system/storage',
      title: $t('tenant.dashboard.cockpit.signals.storageTitle'),
      value: `${stats.value.storage_used_mb} MB`,
    },
    {
      description: $t('tenant.dashboard.cockpit.signals.costDesc'),
      icon: 'lucide:badge-dollar-sign',
      key: 'cost',
      route: '/tenant/ai/usage',
      title: $t('tenant.dashboard.cockpit.signals.costTitle'),
      value: formatCurrency(stats.value.total_cost),
    },
  ]);

  const actionDeck = computed<DashboardRouteCardItem[]>(() => [
    {
      description: $t('tenant.dashboard.cockpit.actions.agentsDesc'),
      icon: 'lucide:bot',
      key: 'agents',
      route: '/tenant/ai/agents',
      title: $t('tenant.dashboard.cockpit.actions.agentsTitle'),
    },
    {
      description: $t('tenant.dashboard.cockpit.actions.kbsDesc'),
      icon: 'lucide:book-open',
      key: 'knowledge',
      route: '/tenant/ai/knowledge-bases',
      title: $t('tenant.dashboard.cockpit.actions.kbsTitle'),
    },
    {
      description: $t('tenant.dashboard.cockpit.actions.usageDesc'),
      icon: 'lucide:activity',
      key: 'usage',
      route: '/tenant/ai/usage',
      title: $t('tenant.dashboard.cockpit.actions.usageTitle'),
    },
    {
      description: $t('tenant.dashboard.cockpit.actions.usersDesc'),
      icon: 'lucide:users',
      key: 'users',
      route: '/tenant/system/user-architecture',
      title: $t('tenant.dashboard.cockpit.actions.usersTitle'),
    },
    {
      description: $t('tenant.dashboard.cockpit.actions.storageDesc'),
      icon: 'lucide:hard-drive',
      key: 'storage',
      route: '/tenant/system/storage',
      title: $t('tenant.dashboard.cockpit.actions.storageTitle'),
    },
    {
      description: $t('tenant.dashboard.cockpit.actions.logsDesc'),
      icon: 'lucide:scroll-text',
      key: 'logs',
      route: '/tenant/system/operation-logs',
      title: $t('tenant.dashboard.cockpit.actions.logsTitle'),
    },
  ]);

  const portalHealthCards = computed<DashboardMetricCard[]>(() => [
    {
      icon: 'lucide:file-stack',
      key: 'docs',
      label: $t('tenant.dashboard.cockpit.portal.cards.documents'),
      value: formatCompactNumber(stats.value.total_kb_documents),
    },
    {
      icon: 'lucide:route',
      key: 'avgConversation',
      label: $t('tenant.dashboard.cockpit.portal.cards.avgConversation'),
      value: formatCompactNumber(avgConversationPerAgent.value),
    },
    {
      icon: 'lucide:binary',
      key: 'tokens',
      label: $t('tenant.dashboard.cockpit.portal.cards.tokens'),
      value: formatCompactNumber(stats.value.total_tokens),
    },
    {
      icon: 'lucide:users-round',
      key: 'activeUsers',
      label: $t('tenant.dashboard.cockpit.portal.cards.activeUsers'),
      value: formatCompactNumber(stats.value.active_users),
    },
  ]);

  const summaryPanels = computed<DashboardSummaryPanel[]>(() => [
    {
      icon: 'lucide:hard-drive',
      key: 'storage',
      rows: [
        {
          label: $t('tenant.dashboard.cockpit.summary.files'),
          value: formatCompactNumber(storageDetail.value.total_files),
        },
        {
          label: $t('tenant.dashboard.cockpit.summary.usedSpace'),
          value: `${storageDetail.value.total_size_mb} MB`,
        },
        {
          label: $t('tenant.dashboard.cockpit.summary.topType'),
          value: storageDetail.value.type_distribution[0]?.mime_type || '-',
        },
      ],
      title: $t('tenant.dashboard.cockpit.signals.storageTitle'),
    },
    {
      icon: 'lucide:book-open-check',
      key: 'assets',
      rows: [
        {
          label: $t('tenant.dashboard.cockpit.portal.cards.documents'),
          value: formatCompactNumber(stats.value.total_kb_documents),
        },
        {
          label: $t('tenant.dashboard.cockpit.signals.agentsTitle'),
          value: formatCompactNumber(stats.value.total_agents),
        },
        {
          label: $t('tenant.dashboard.cockpit.signals.kbTitle'),
          value: formatCompactNumber(stats.value.total_knowledge_bases),
        },
      ],
      title: $t('tenant.dashboard.cockpit.summary.assetsTitle'),
    },
  ]);

  const activityEntries = computed<DashboardActivityEntry[]>(() => {
    const systemActorLabel = $t('tenant.dashboard.cockpit.systemActor');
    return overview.value.recent_activities.map((activity) => {
      const nextActivity = activity as TenantDashboardActivityItem;
      return {
        actor: buildDashboardActivityActor(nextActivity, systemActorLabel),
        createdAt: nextActivity.created_at,
        detail:
          [nextActivity.module, nextActivity.action]
            .filter(Boolean)
            .join(' / ') || $t('tenant.dashboard.cockpit.unknownModule'),
        id: nextActivity.id,
        method: nextActivity.method,
        path: nextActivity.path,
        statusCode: nextActivity.status_code,
      };
    });
  });

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
    activityEntries,
    aiTrend,
    heroActions,
    loading,
    operationalSignals,
    overviewCards,
    portalHealthCards,
    realtimeChips,
    spotlights: spotlightCards,
    stats,
    summaryPanels,
  };
}
