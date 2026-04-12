import type { Dayjs } from 'dayjs';

import type {
  MonitoringScope,
  MonitoringUsageBreakdownItem,
  MonitoringUsageDashboard,
} from '../../api';

import { computed, onMounted, ref } from 'vue';

import dayjs from 'dayjs';

import { $t } from '#/locales';

import { getMonitoringUsageDashboard } from '../../api';
import {
  formatCost,
  formatNumber,
  formatPercent,
} from './formatters';

type DateRange = [Dayjs, Dayjs];

interface UsageSection {
  icon: string;
  iconWrapClass: string;
  items: MonitoringUsageBreakdownItem[];
  key: string;
  progressClass: string;
  title: string;
}

interface UsageDashboardOptions {
  i18nPrefix: string;
  scope: MonitoringScope;
}

export function useMonitoringUsageDashboard(options: UsageDashboardOptions) {
  const loading = ref(false);
  const dashboard = ref<MonitoringUsageDashboard | null>(null);
  const dateRange = ref<DateRange>([
    dayjs().subtract(29, 'day').startOf('day'),
    dayjs().endOf('day'),
  ]);

  const isAdmin = computed(() => options.scope === 'admin');

  const presets = computed(() => [
    {
      key: 'last7',
      label: $t(`${options.i18nPrefix}.last7Days`),
      value: [
        dayjs().subtract(6, 'day').startOf('day'),
        dayjs().endOf('day'),
      ] as DateRange,
    },
    {
      key: 'last30',
      label: $t(`${options.i18nPrefix}.last30Days`),
      value: [
        dayjs().subtract(29, 'day').startOf('day'),
        dayjs().endOf('day'),
      ] as DateRange,
    },
    {
      key: 'month',
      label: $t(`${options.i18nPrefix}.thisMonth`),
      value: [dayjs().startOf('month'), dayjs().endOf('day')] as DateRange,
    },
  ]);

  const totalCalls = computed(() => dashboard.value?.summary.total_calls ?? 0);
  const totalTokens = computed(() => dashboard.value?.summary.total_tokens ?? 0);
  const totalCost = computed(() => dashboard.value?.summary.total_cost ?? 0);
  const averageTokensPerCall = computed(() => {
    if (!totalCalls.value) {
      return 0;
    }
    return Math.round(totalTokens.value / totalCalls.value);
  });

  const rangeLabel = computed(
    () =>
      `${dateRange.value[0].format('YYYY-MM-DD')} ~ ${dateRange.value[1].format('YYYY-MM-DD')}`,
  );

  const activePresetLabel = computed(() => {
    const matched = presets.value.find((preset) => isPresetActive(preset.value));
    return matched?.label ?? $t(`${options.i18nPrefix}.snapshot.customRange`);
  });

  const scopeLabel = computed(() => {
    if (options.scope === 'admin') {
      return $t(`${options.i18nPrefix}.snapshot.platformScope`);
    }
    return (
      dashboard.value?.tenant_name ||
      $t(`${options.i18nPrefix}.snapshot.tenantScope`)
    );
  });

  const topModel = computed(() => dashboard.value?.model_stats?.[0] ?? null);
  const topChannel = computed(
    () => dashboard.value?.access_channel_stats?.[0] ?? null,
  );
  const topTenant = computed(() => dashboard.value?.top_tenants?.[0] ?? null);
  const tenantLeaders = computed(
    () => dashboard.value?.top_tenants?.slice(0, 4) ?? [],
  );
  const busiestDay = computed(() => {
    const daily = dashboard.value?.daily_stats ?? [];
    if (daily.length === 0) {
      return null;
    }
    let busiest = daily[0]!;
    for (const item of daily.slice(1)) {
      if (item.call_count > busiest.call_count) {
        busiest = item;
      }
    }
    return busiest;
  });

  const heroMetrics = computed(() => {
    if (isAdmin.value) {
      return [
        {
          key: 'calls',
          label: $t(`${options.i18nPrefix}.summary.totalCalls`),
          value: formatNumber(totalCalls.value),
        },
        {
          key: 'tokens',
          label: $t(`${options.i18nPrefix}.summary.totalTokens`),
          value: formatNumber(totalTokens.value),
        },
        {
          key: 'cost',
          label: $t(`${options.i18nPrefix}.summary.totalCost`),
          value: formatCost(totalCost.value),
        },
        {
          key: 'tenant',
          label: $t(`${options.i18nPrefix}.monitoring.topTenants`),
          value: topTenant.value
            ? breakdownLabel(topTenant.value)
            : $t(`${options.i18nPrefix}.snapshot.empty`),
        },
      ];
    }

    return [
      {
        key: 'calls',
        label: $t(`${options.i18nPrefix}.summary.totalCalls`),
        value: formatNumber(totalCalls.value),
      },
      {
        key: 'tokens',
        label: $t(`${options.i18nPrefix}.summary.totalTokens`),
        value: formatNumber(totalTokens.value),
      },
      {
        key: 'cost',
        label: $t(`${options.i18nPrefix}.summary.totalCost`),
        value: formatCost(totalCost.value),
      },
      {
        key: 'rate',
        label: $t(`${options.i18nPrefix}.summary.successRate`),
        value: formatPercent(dashboard.value?.summary.success_rate),
      },
    ];
  });

  const heroChips = computed(() => {
    const chips = [
      {
        key: 'range',
        icon: 'lucide:calendar-range',
        className: 'bg-primary/10 text-primary',
        text: `${activePresetLabel.value} · ${rangeLabel.value}`,
      },
      {
        key: 'scope',
        icon: isAdmin.value ? 'lucide:shield' : 'lucide:building-2',
        className: 'bg-background/90 text-foreground',
        text: scopeLabel.value,
      },
    ];

    if (topChannel.value) {
      chips.push({
        key: 'channel',
        icon: 'lucide:route',
        className: 'bg-accent text-foreground',
        text: `${$t(`${options.i18nPrefix}.accessChannel.topChannelLabel`)}: ${breakdownLabel(topChannel.value)}`,
      });
    }

    if (isAdmin.value && topTenant.value) {
      chips.push({
        key: 'tenant',
        icon: 'lucide:building-2',
        className: 'bg-accent text-foreground',
        text: `${$t(`${options.i18nPrefix}.monitoring.topTenants`)}: ${breakdownLabel(topTenant.value)}`,
      });
    } else if (topModel.value) {
      chips.push({
        key: 'model',
        icon: 'lucide:bot',
        className: 'bg-accent text-foreground',
        text: `${$t(`${options.i18nPrefix}.chart.modelDistribution`)}: ${breakdownLabel(topModel.value)}`,
      });
    }

    return chips;
  });

  const topSections = computed<UsageSection[]>(() => [
    {
      key: 'models',
      title: $t(`${options.i18nPrefix}.monitoring.topModels`),
      items: dashboard.value?.model_stats ?? [],
      icon: 'lucide:bot',
      iconWrapClass: 'bg-primary/10 text-primary',
      progressClass: 'from-primary to-primary/60',
    },
    {
      key: 'agents',
      title: $t(`${options.i18nPrefix}.monitoring.topAgents`),
      items: dashboard.value?.top_agents ?? [],
      icon: 'lucide:sparkles',
      iconWrapClass: 'bg-primary/10 text-primary',
      progressClass: 'from-primary to-primary/60',
    },
    {
      key: 'users',
      title: $t(`${options.i18nPrefix}.monitoring.topUsers`),
      items: dashboard.value?.top_users ?? [],
      icon: 'lucide:users',
      iconWrapClass: 'bg-primary/10 text-primary',
      progressClass: 'from-primary to-primary/60',
    },
  ]);

  async function loadDashboard() {
    loading.value = true;
    try {
      dashboard.value = await getMonitoringUsageDashboard(options.scope, {
        start_date: dateRange.value[0].format('YYYY-MM-DD'),
        end_date: dateRange.value[1].format('YYYY-MM-DD'),
      });
    } finally {
      loading.value = false;
    }
  }

  function isPresetActive(range: DateRange) {
    return (
      dateRange.value[0].isSame(range[0], 'day') &&
      dateRange.value[1].isSame(range[1], 'day')
    );
  }

  function applyPreset(range: DateRange) {
    dateRange.value = range;
    void loadDashboard();
  }

  function handleDateChange(value: [Dayjs, Dayjs] | [string, string] | null) {
    if (!value) {
      return;
    }
    if (typeof value[0] === 'string' || typeof value[1] === 'string') {
      return;
    }
    dateRange.value = value as DateRange;
    void loadDashboard();
  }

  function breakdownLabel(item: MonitoringUsageBreakdownItem) {
    if (item.key === 'admin_internal') {
      return $t(`${options.i18nPrefix}.accessChannel.admin_internal`);
    }
    if (item.key === 'tenant_admin') {
      return $t(`${options.i18nPrefix}.accessChannel.tenant_admin`);
    }
    if (item.key === 'tenant_user') {
      return $t(`${options.i18nPrefix}.accessChannel.tenant_user`);
    }
    if (item.key === 'unknown') {
      return $t(`${options.i18nPrefix}.accessChannel.unknown`);
    }
    return item.label || item.key;
  }

  onMounted(() => {
    void loadDashboard();
  });

  return {
    activePresetLabel,
    applyPreset,
    averageTokensPerCall,
    breakdownLabel,
    busiestDay,
    dashboard,
    dateRange,
    heroChips,
    heroMetrics,
    isAdmin,
    loading,
    presets,
    rangeLabel,
    scopeLabel,
    topChannel,
    topModel,
    topSections,
    topTenant,
    totalCalls,
    totalCost,
    totalTokens,
    tenantLeaders,
    handleDateChange,
  };
}

export type { DateRange, UsageSection };
