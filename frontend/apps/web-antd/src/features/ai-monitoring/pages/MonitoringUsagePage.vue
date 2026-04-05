<script lang="ts" setup>
import type { Dayjs } from 'dayjs';

import type {
  MonitoringScope,
  MonitoringUsageBreakdownItem,
  MonitoringUsageDashboard,
} from '../api';

import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import { Button, DatePicker, Empty, Spin } from 'ant-design-vue';
import dayjs from 'dayjs';

import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';
import { $t } from '#/locales';

import { getMonitoringUsageDashboard } from '../api';

type DateRange = [Dayjs, Dayjs];

interface UsageSection {
  icon: string;
  iconWrapClass: string;
  items: MonitoringUsageBreakdownItem[];
  key: string;
  progressClass: string;
  title: string;
}

const props = defineProps<{
  i18nPrefix: string;
  scope: MonitoringScope;
  showTopTenants?: boolean;
  title: string;
}>();

const loading = ref(false);
const dashboard = ref<MonitoringUsageDashboard | null>(null);
const dateRange = ref<DateRange>([
  dayjs().subtract(29, 'day').startOf('day'),
  dayjs().endOf('day'),
]);

const callChartRef = ref();
const modelChartRef = ref();
const { renderEcharts: renderCallChart } = useEcharts(callChartRef);
const { renderEcharts: renderModelChart } = useEcharts(modelChartRef);
const isAdmin = computed(() => props.scope === 'admin');
let themeObserver: MutationObserver | null = null;

function formatCost(cost?: null | number, digits = 4) {
  return `$${Number(cost || 0).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

function formatNumber(value?: null | number) {
  return Number(value || 0).toLocaleString();
}

function formatPercent(value?: null | number) {
  return `${Number(value || 0)
    .toFixed(1)
    .replace(/\.0$/, '')}%`;
}

function formatShare(value: number, total: number) {
  if (!total) {
    return '0%';
  }
  return formatPercent((value / total) * 100);
}

function progressWidth(value: number, total: number, minimum = 0) {
  if (!total) {
    return '0%';
  }
  const width = (value / total) * 100;
  return `${Math.max(width, minimum)}%`;
}

function maxCallCount(items: MonitoringUsageBreakdownItem[]) {
  return Math.max(...items.map((item) => item.call_count), 0);
}

function cssVarColor(name: string, alpha?: number) {
  if (typeof window === 'undefined') {
    return '';
  }
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  if (!value) {
    return '';
  }
  return alpha === undefined ? `hsl(${value})` : `hsl(${value} / ${alpha})`;
}

const presets = computed(() => [
  {
    key: 'last7',
    label: $t(`${props.i18nPrefix}.last7Days`),
    value: [
      dayjs().subtract(6, 'day').startOf('day'),
      dayjs().endOf('day'),
    ] as DateRange,
  },
  {
    key: 'last30',
    label: $t(`${props.i18nPrefix}.last30Days`),
    value: [
      dayjs().subtract(29, 'day').startOf('day'),
      dayjs().endOf('day'),
    ] as DateRange,
  },
  {
    key: 'month',
    label: $t(`${props.i18nPrefix}.thisMonth`),
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
  return matched?.label ?? $t(`${props.i18nPrefix}.snapshot.customRange`);
});

const scopeLabel = computed(() => {
  if (props.scope === 'admin') {
    return $t(`${props.i18nPrefix}.snapshot.platformScope`);
  }
  return (
    dashboard.value?.tenant_name ||
    $t(`${props.i18nPrefix}.snapshot.tenantScope`)
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
        label: $t(`${props.i18nPrefix}.summary.totalCalls`),
        value: formatNumber(totalCalls.value),
      },
      {
        key: 'tokens',
        label: $t(`${props.i18nPrefix}.summary.totalTokens`),
        value: formatNumber(totalTokens.value),
      },
      {
        key: 'cost',
        label: $t(`${props.i18nPrefix}.summary.totalCost`),
        value: formatCost(totalCost.value),
      },
      {
        key: 'tenant',
        label: $t(`${props.i18nPrefix}.monitoring.topTenants`),
        value: topTenant.value
          ? breakdownLabel(topTenant.value)
          : $t(`${props.i18nPrefix}.snapshot.empty`),
      },
    ];
  }

  return [
    {
      key: 'calls',
      label: $t(`${props.i18nPrefix}.summary.totalCalls`),
      value: formatNumber(totalCalls.value),
    },
    {
      key: 'tokens',
      label: $t(`${props.i18nPrefix}.summary.totalTokens`),
      value: formatNumber(totalTokens.value),
    },
    {
      key: 'cost',
      label: $t(`${props.i18nPrefix}.summary.totalCost`),
      value: formatCost(totalCost.value),
    },
    {
      key: 'rate',
      label: $t(`${props.i18nPrefix}.summary.successRate`),
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
      text: `${$t(`${props.i18nPrefix}.accessChannel.topChannelLabel`)}: ${breakdownLabel(topChannel.value)}`,
    });
  }

  if (isAdmin.value && topTenant.value) {
    chips.push({
      key: 'tenant',
      icon: 'lucide:building-2',
      className: 'bg-accent text-foreground',
      text: `${$t(`${props.i18nPrefix}.monitoring.topTenants`)}: ${breakdownLabel(topTenant.value)}`,
    });
  } else if (topModel.value) {
    chips.push({
      key: 'model',
      icon: 'lucide:bot',
      className: 'bg-accent text-foreground',
      text: `${$t(`${props.i18nPrefix}.chart.modelDistribution`)}: ${breakdownLabel(topModel.value)}`,
    });
  }

  return chips;
});

const topSections = computed<UsageSection[]>(() => {
  return [
    {
      key: 'models',
      title: $t(`${props.i18nPrefix}.monitoring.topModels`),
      items: dashboard.value?.model_stats ?? [],
      icon: 'lucide:bot',
      iconWrapClass: 'bg-primary/10 text-primary',
      progressClass: 'from-primary to-primary/60',
    },
    {
      key: 'agents',
      title: $t(`${props.i18nPrefix}.monitoring.topAgents`),
      items: dashboard.value?.top_agents ?? [],
      icon: 'lucide:sparkles',
      iconWrapClass: 'bg-primary/10 text-primary',
      progressClass: 'from-primary to-primary/60',
    },
    {
      key: 'users',
      title: $t(`${props.i18nPrefix}.monitoring.topUsers`),
      items: dashboard.value?.top_users ?? [],
      icon: 'lucide:users',
      iconWrapClass: 'bg-primary/10 text-primary',
      progressClass: 'from-primary to-primary/60',
    },
  ];
});

async function loadDashboard() {
  loading.value = true;
  try {
    dashboard.value = await getMonitoringUsageDashboard(props.scope, {
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
    return $t(`${props.i18nPrefix}.accessChannel.admin_internal`);
  }
  if (item.key === 'tenant_admin') {
    return $t(`${props.i18nPrefix}.accessChannel.tenant_admin`);
  }
  if (item.key === 'tenant_user') {
    return $t(`${props.i18nPrefix}.accessChannel.tenant_user`);
  }
  if (item.key === 'unknown') {
    return $t(`${props.i18nPrefix}.accessChannel.unknown`);
  }
  return item.label || item.key;
}

function buildUsageActorIdentityModel(item: MonitoringUsageBreakdownItem) {
  const actor = item.actor;
  const fallbackLabel = (item.label || item.key || '').trim();
  if (!actor && !fallbackLabel) {
    return null;
  }

  const displayName =
    actor?.display_name?.trim() ||
    actor?.nickname?.trim() ||
    actor?.username?.trim() ||
    fallbackLabel;

  return {
    avatar: actor?.avatar,
    displayName: actor?.display_name || displayName,
    id: actor?.id ?? item.key,
    isActive: actor?.is_active,
    isLeader: actor?.is_leader,
    isOwner: actor?.is_owner,
    nickname: displayName,
    orgNodeId: actor?.org_node_id,
    orgNodeName: actor?.org_node_name,
    roleName: actor?.role_name,
    userType: actor?.type ?? undefined,
    username:
      actor?.display_name || actor?.nickname
        ? undefined
        : (actor?.username ?? undefined),
  };
}

function buildUsageActorMeta(
  item: MonitoringUsageBreakdownItem,
): IdentityDetailMeta {
  const actor = item.actor;
  return {
    orgNodeName: actor?.org_node_name,
    roleName: actor?.role_name,
    scope: props.scope,
    subjectType: actor?.type,
    tenantId: actor?.tenant_id ?? dashboard.value?.tenant_id ?? undefined,
    tenantName: actor?.tenant_name ?? dashboard.value?.tenant_name,
    userType: actor?.type,
    username:
      actor?.username ||
      actor?.display_name ||
      actor?.nickname ||
      undefined,
  };
}

function renderCharts() {
  const current = dashboard.value;
  if (!current) {
    return;
  }

  const primary = cssVarColor('--primary');
  const primarySoft = cssVarColor('--primary', 0.1);
  const success = cssVarColor('--success');
  const successSoft = cssVarColor('--success', 0.08);
  const warning = cssVarColor('--warning');
  const destructive = cssVarColor('--destructive');
  const mutedForeground = cssVarColor('--muted-foreground');
  const border = cssVarColor('--border');

  renderCallChart({
    color: [primary, success, warning],
    tooltip: { trigger: 'axis' },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      top: '8%',
      containLabel: true,
    },
    legend: {
      bottom: 0,
      icon: 'circle',
      data: [
        $t(`${props.i18nPrefix}.summary.totalCalls`),
        $t(`${props.i18nPrefix}.summary.totalTokens`),
        $t(`${props.i18nPrefix}.summary.totalCost`),
      ],
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: current.daily_stats.map((item) => item.date.slice(5)),
      axisLabel: { color: mutedForeground },
      axisLine: { lineStyle: { color: border } },
    },
    yAxis: [
      {
        type: 'value',
        name: $t(`${props.i18nPrefix}.summary.totalCalls`),
        axisLabel: { color: mutedForeground },
        splitLine: { lineStyle: { color: cssVarColor('--border', 0.28) } },
      },
      {
        type: 'value',
        name: $t(`${props.i18nPrefix}.summary.totalTokens`),
        axisLabel: { color: mutedForeground },
        splitLine: { show: false },
      },
      {
        type: 'value',
        show: false,
      },
    ],
    series: [
      {
        name: $t(`${props.i18nPrefix}.summary.totalCalls`),
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { width: 3 },
        areaStyle: {
          color: primarySoft,
        },
        data: current.daily_stats.map((item) => item.call_count),
      },
      {
        name: $t(`${props.i18nPrefix}.summary.totalTokens`),
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2.5 },
        areaStyle: {
          color: successSoft,
        },
        data: current.daily_stats.map((item) => item.total_tokens),
      },
      {
        name: $t(`${props.i18nPrefix}.summary.totalCost`),
        type: 'bar',
        yAxisIndex: 2,
        barMaxWidth: 18,
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: cssVarColor('--warning', 0.58),
        },
        data: current.daily_stats.map((item) => item.total_cost),
      },
    ],
  });

  renderModelChart({
    color: [
      primary,
      success,
      warning,
      destructive,
      cssVarColor('--secondary-foreground'),
      cssVarColor('--muted-foreground'),
    ],
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      type: 'scroll',
      bottom: 0,
      left: 'center',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: mutedForeground },
    },
    series: [
      {
        type: 'pie',
        radius: ['48%', '74%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        label: { show: false },
        emphasis: {
          scale: true,
          itemStyle: {
            shadowBlur: 12,
            shadowColor: 'rgba(15, 23, 42, 0.18)',
          },
        },
        data: current.model_stats.map((item) => ({
          name: breakdownLabel(item),
          value: item.call_count,
        })),
      },
    ],
  });
}

watch(
  [dashboard, callChartRef, modelChartRef],
  async () => {
    if (!dashboard.value || !callChartRef.value || !modelChartRef.value) {
      return;
    }
    await nextTick();
    renderCharts();
  },
  { flush: 'post' },
);

onMounted(() => {
  void loadDashboard();
  if (typeof window !== 'undefined') {
    themeObserver = new MutationObserver(() => {
      if (dashboard.value) {
        void nextTick().then(renderCharts);
      }
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'data-theme', 'style'],
    });
  }
});

onBeforeUnmount(() => {
  themeObserver?.disconnect();
  themeObserver = null;
});
</script>

<template>
  <Page
    auto-content-height
    content-class="monitoring-usage-page flex flex-col gap-4 !p-4"
  >
    <AIPageHeroCard
      :chips="heroChips"
      :description="$t(`${i18nPrefix}.pageDesc`)"
      icon="lucide:chart-column-big"
      icon-wrap-class="bg-primary/10 text-primary"
      :metrics="heroMetrics"
      :title="title"
    >
      <template #actions>
        <Button
          v-for="preset in presets"
          :key="preset.key"
          size="small"
          @click="applyPreset(preset.value)"
        >
          {{ preset.label }}
        </Button>
        <DatePicker.RangePicker
          :value="dateRange"
          class="monitoring-range-picker w-64"
          format="YYYY-MM-DD"
          :allow-clear="false"
          :id="`${scope}-usage-range`"
          :name="`${scope}-usage-range`"
          size="small"
          @change="handleDateChange"
        />
      </template>
    </AIPageHeroCard>

    <Spin :spinning="loading">
      <template v-if="dashboard">
        <section
          class="grid items-start gap-5 2xl:grid-cols-[minmax(0,1.58fr)_minmax(328px,0.92fr)]"
        >
          <div class="flex min-w-0 flex-col gap-5">
            <article class="monitoring-surface">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="monitoring-surface__eyebrow">
                    {{ $t(`${i18nPrefix}.chart.dailyTrend`) }}
                  </p>
                  <h3 class="monitoring-surface__title">{{ rangeLabel }}</h3>
                  <p class="monitoring-surface__desc">
                    {{ scopeLabel }} ·
                    {{ $t(`${i18nPrefix}.summary.totalCalls`) }}
                    {{ formatNumber(totalCalls) }}
                  </p>
                </div>
                <div class="flex flex-wrap gap-2">
                  <span class="monitoring-chip monitoring-chip--sky">
                    {{ $t(`${i18nPrefix}.snapshot.busiestDay`) }}
                    <strong class="ml-1 font-semibold">
                      {{
                        busiestDay
                          ? dayjs(busiestDay.date).format('MM-DD')
                          : $t(`${i18nPrefix}.snapshot.empty`)
                      }}
                    </strong>
                  </span>
                  <span class="monitoring-chip monitoring-chip--amber">
                    {{ $t(`${i18nPrefix}.metrics.avgTokensPerCall`) }}
                    <strong class="ml-1 font-semibold">
                      {{ formatNumber(averageTokensPerCall) }}
                    </strong>
                  </span>
                </div>
              </div>

              <div class="monitoring-chart-shell mt-4">
                <EchartsUI ref="callChartRef" height="286px" />
              </div>
            </article>

            <article class="monitoring-surface">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="monitoring-surface__eyebrow">
                    {{ $t(`${i18nPrefix}.chart.modelDistribution`) }}
                  </p>
                  <h3 class="monitoring-surface__title">
                    {{
                      topModel
                        ? breakdownLabel(topModel)
                        : $t(`${i18nPrefix}.snapshot.empty`)
                    }}
                  </h3>
                  <p class="monitoring-surface__desc">
                    {{ $t(`${i18nPrefix}.snapshot.topModel`) }}
                  </p>
                </div>
                <span class="monitoring-chip monitoring-chip--violet">
                  {{ formatNumber(dashboard.model_stats.length) }}
                </span>
              </div>

              <div class="monitoring-chart-shell mt-4">
                <EchartsUI ref="modelChartRef" height="224px" />
              </div>
            </article>

            <article
              v-if="!isAdmin && topSections[0]"
              class="monitoring-surface"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="flex items-start gap-3">
                  <span
                    class="flex size-11 items-center justify-center rounded-2xl"
                    :class="topSections[0].iconWrapClass"
                  >
                    <IconifyIcon :icon="topSections[0].icon" class="size-5" />
                  </span>
                  <div>
                    <p class="monitoring-surface__eyebrow">
                      {{ topSections[0].title }}
                    </p>
                    <h3 class="monitoring-surface__title">
                      {{ topSections[0].title }}
                    </h3>
                  </div>
                </div>
                <span class="monitoring-chip">
                  {{ formatNumber(topSections[0].items.length) }}
                </span>
              </div>

              <Empty
                v-if="topSections[0].items.length === 0"
                class="py-8"
                :description="$t(`${i18nPrefix}.list.empty`)"
              />
              <div v-else class="monitoring-list-shell mt-4 space-y-2.5">
                <div
                  v-for="(item, index) in topSections[0].items"
                  :key="item.key"
                  class="rounded-2xl border border-border/60 bg-accent/15 p-3"
                >
                  <div class="flex items-start gap-3">
                    <span
                      class="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
                      :class="topSections[0].iconWrapClass"
                    >
                      {{ index + 1 }}
                    </span>
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center justify-between gap-3">
                        <div class="truncate font-medium text-foreground">
                          {{ breakdownLabel(item) }}
                        </div>
                        <div class="text-xs text-muted-foreground">
                          {{ formatShare(item.call_count, totalCalls) }}
                        </div>
                      </div>
                      <div class="mt-2 h-2 rounded-full bg-muted/55">
                        <div
                          class="h-full rounded-full bg-gradient-to-r"
                          :class="topSections[0].progressClass"
                          :style="{
                            width: progressWidth(
                              item.call_count,
                              maxCallCount(topSections[0].items),
                              item.call_count > 0 ? 12 : 0,
                            ),
                          }"
                        ></div>
                      </div>
                      <div
                        class="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground"
                      >
                        <span>
                          {{ $t(`${i18nPrefix}.summary.totalCalls`) }}
                          {{ formatNumber(item.call_count) }}
                        </span>
                        <span>
                          {{ $t(`${i18nPrefix}.summary.totalTokens`) }}
                          {{ formatNumber(item.total_tokens) }}
                        </span>
                        <span>
                          {{ $t(`${i18nPrefix}.summary.totalCost`) }}
                          {{ formatCost(item.total_cost) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </article>
          </div>

          <div class="flex min-w-0 flex-col gap-5 self-start">
            <article
              v-if="isAdmin && showTopTenants"
              class="monitoring-surface"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="monitoring-surface__eyebrow">
                    {{ $t(`${i18nPrefix}.monitoring.topTenants`) }}
                  </p>
                  <h3 class="monitoring-surface__title">
                    {{
                      topTenant
                        ? breakdownLabel(topTenant)
                        : $t(`${i18nPrefix}.snapshot.empty`)
                    }}
                  </h3>
                  <p class="monitoring-surface__desc">
                    {{ $t(`${i18nPrefix}.summary.totalCost`) }}
                    {{
                      topTenant
                        ? formatCost(topTenant.total_cost)
                        : formatCost(0)
                    }}
                  </p>
                </div>
                <span class="monitoring-chip monitoring-chip--rose">
                  {{ formatNumber(tenantLeaders.length) }}
                </span>
              </div>

              <Empty
                v-if="tenantLeaders.length === 0"
                :description="$t(`${i18nPrefix}.list.empty`)"
              />
              <div v-else class="monitoring-list-shell mt-4 space-y-2.5">
                <div
                  v-for="(item, index) in tenantLeaders"
                  :key="item.key"
                  class="rounded-2xl border border-border/60 bg-accent/15 p-3"
                >
                  <div class="flex items-start gap-3">
                    <span
                      class="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary"
                    >
                      {{ index + 1 }}
                    </span>
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center justify-between gap-3">
                        <div class="truncate font-medium text-foreground">
                          {{ breakdownLabel(item) }}
                        </div>
                        <div class="text-xs text-muted-foreground">
                          {{ formatShare(item.call_count, totalCalls) }}
                        </div>
                      </div>
                      <div class="mt-2 h-2 rounded-full bg-muted/55">
                        <div
                          class="h-full rounded-full bg-gradient-to-r from-primary to-primary/60"
                          :style="{
                            width: progressWidth(
                              item.call_count,
                              maxCallCount(tenantLeaders),
                              item.call_count > 0 ? 12 : 0,
                            ),
                          }"
                        ></div>
                      </div>
                      <div
                        class="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground"
                      >
                        <span>
                          {{ $t(`${i18nPrefix}.summary.totalCalls`) }}
                          {{ formatNumber(item.call_count) }}
                        </span>
                        <span>
                          {{ $t(`${i18nPrefix}.summary.totalTokens`) }}
                          {{ formatNumber(item.total_tokens) }}
                        </span>
                        <span>
                          {{ $t(`${i18nPrefix}.summary.totalCost`) }}
                          {{ formatCost(item.total_cost) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </article>

            <article class="monitoring-surface">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p class="monitoring-surface__eyebrow">
                    {{ $t(`${i18nPrefix}.accessChannel.title`) }}
                  </p>
                  <h3 class="monitoring-surface__title">
                    {{ $t(`${i18nPrefix}.accessChannel.title`) }}
                  </h3>
                  <p class="monitoring-surface__desc">
                    {{ $t(`${i18nPrefix}.accessChannel.subtitle`) }}
                  </p>
                </div>
                <span class="monitoring-chip monitoring-chip--cyan">
                  {{ formatNumber(dashboard.access_channel_stats.length) }}
                </span>
              </div>

              <Empty
                v-if="dashboard.access_channel_stats.length === 0"
                :description="$t(`${i18nPrefix}.list.empty`)"
              />
              <div v-else class="monitoring-list-shell mt-4 space-y-2.5">
                <div
                  v-for="item in dashboard.access_channel_stats"
                  :key="item.key"
                  class="rounded-2xl border border-border/60 bg-accent/15 p-2.5"
                >
                  <div class="flex items-center justify-between gap-3">
                    <div class="truncate font-medium text-foreground">
                      {{ breakdownLabel(item) }}
                    </div>
                    <div class="text-xs text-muted-foreground">
                      {{ formatShare(item.call_count, totalCalls) }}
                    </div>
                  </div>
                  <div class="mt-2 h-2 rounded-full bg-muted/55">
                    <div
                      class="h-full rounded-full bg-gradient-to-r from-primary to-primary/60"
                      :style="{
                        width: progressWidth(
                          item.call_count,
                          totalCalls,
                          item.call_count > 0 ? 10 : 0,
                        ),
                      }"
                    ></div>
                  </div>
                  <div
                    class="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground"
                  >
                    <span>
                      {{ $t(`${i18nPrefix}.accessChannel.calls`) }}
                      {{ formatNumber(item.call_count) }}
                    </span>
                    <span>
                      {{ $t(`${i18nPrefix}.accessChannel.tokens`) }}
                      {{ formatNumber(item.total_tokens) }}
                    </span>
                    <span>
                      {{ $t(`${i18nPrefix}.accessChannel.cost`) }}
                      {{ formatCost(item.total_cost) }}
                    </span>
                  </div>
                </div>
              </div>
            </article>

            <article
              v-for="section in !isAdmin ? topSections.slice(1) : []"
              :key="section.key"
              class="monitoring-surface"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="flex items-start gap-3">
                  <span
                    class="flex size-11 items-center justify-center rounded-2xl"
                    :class="section.iconWrapClass"
                  >
                    <IconifyIcon :icon="section.icon" class="size-5" />
                  </span>
                  <div>
                    <p class="monitoring-surface__eyebrow">
                      {{ section.title }}
                    </p>
                    <h3 class="monitoring-surface__title">
                      {{ section.title }}
                    </h3>
                  </div>
                </div>
                <span class="monitoring-chip">
                  {{ formatNumber(section.items.length) }}
                </span>
              </div>

              <Empty
                v-if="section.items.length === 0"
                class="py-8"
                :description="$t(`${i18nPrefix}.list.empty`)"
              />
              <div v-else class="monitoring-list-shell mt-4 space-y-2.5">
                <div
                  v-for="(item, index) in section.items"
                  :key="item.key"
                  class="rounded-2xl border border-border/60 bg-accent/15 p-3"
                >
                  <div class="flex items-start gap-3">
                    <span
                      class="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
                      :class="section.iconWrapClass"
                    >
                      {{ index + 1 }}
                    </span>
                    <div class="min-w-0 flex-1">
                      <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0 flex-1">
                          <IdentityTrigger
                            v-if="
                              section.key === 'users' &&
                              buildUsageActorIdentityModel(item)
                            "
                            :avatar-size="32"
                            :model="buildUsageActorIdentityModel(item)!"
                            :meta="buildUsageActorMeta(item)"
                            :context="section.title"
                          />
                          <div
                            v-else
                            class="truncate font-medium text-foreground"
                          >
                            {{ breakdownLabel(item) }}
                          </div>
                        </div>
                        <div class="text-xs text-muted-foreground">
                          {{ formatShare(item.call_count, totalCalls) }}
                        </div>
                      </div>
                      <div class="mt-2 h-2 rounded-full bg-muted/55">
                        <div
                          class="h-full rounded-full bg-gradient-to-r"
                          :class="section.progressClass"
                          :style="{
                            width: progressWidth(
                              item.call_count,
                              maxCallCount(section.items),
                              item.call_count > 0 ? 12 : 0,
                            ),
                          }"
                        ></div>
                      </div>
                      <div
                        class="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground"
                      >
                        <span>
                          {{ $t(`${i18nPrefix}.summary.totalCalls`) }}
                          {{ formatNumber(item.call_count) }}
                        </span>
                        <span>
                          {{ $t(`${i18nPrefix}.summary.totalTokens`) }}
                          {{ formatNumber(item.total_tokens) }}
                        </span>
                        <span>
                          {{ $t(`${i18nPrefix}.summary.totalCost`) }}
                          {{ formatCost(item.total_cost) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section
          v-if="isAdmin"
          class="mt-5 grid items-start gap-5 xl:grid-cols-2"
        >
          <article
            v-for="section in topSections"
            :key="section.key"
            class="monitoring-surface"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-start gap-3">
                <span
                  class="flex size-11 items-center justify-center rounded-2xl"
                  :class="section.iconWrapClass"
                >
                  <IconifyIcon :icon="section.icon" class="size-5" />
                </span>
                <div>
                  <p class="monitoring-surface__eyebrow">
                    {{ section.title }}
                  </p>
                  <h3 class="monitoring-surface__title">
                    {{ section.title }}
                  </h3>
                </div>
              </div>
              <span class="monitoring-chip">
                {{ formatNumber(section.items.length) }}
              </span>
            </div>

            <Empty
              v-if="section.items.length === 0"
              class="py-8"
              :description="$t(`${i18nPrefix}.list.empty`)"
            />
            <div v-else class="monitoring-list-shell mt-4 space-y-2.5">
              <div
                v-for="(item, index) in section.items"
                :key="item.key"
                class="rounded-2xl border border-border/60 bg-accent/15 p-3"
              >
                <div class="flex items-start gap-3">
                  <span
                    class="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
                    :class="section.iconWrapClass"
                  >
                    {{ index + 1 }}
                  </span>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0 flex-1">
                        <IdentityTrigger
                          v-if="
                            section.key === 'users' &&
                            buildUsageActorIdentityModel(item)
                          "
                          :avatar-size="32"
                          :model="buildUsageActorIdentityModel(item)!"
                          :meta="buildUsageActorMeta(item)"
                          :context="section.title"
                        />
                        <div
                          v-else
                          class="truncate font-medium text-foreground"
                        >
                          {{ breakdownLabel(item) }}
                        </div>
                      </div>
                      <div class="text-xs text-muted-foreground">
                        {{ formatShare(item.call_count, totalCalls) }}
                      </div>
                    </div>
                    <div class="mt-2 h-2 rounded-full bg-muted/55">
                      <div
                        class="h-full rounded-full bg-gradient-to-r"
                        :class="section.progressClass"
                        :style="{
                          width: progressWidth(
                            item.call_count,
                            maxCallCount(section.items),
                            item.call_count > 0 ? 12 : 0,
                          ),
                        }"
                      ></div>
                    </div>
                    <div
                      class="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground"
                    >
                      <span>
                        {{ $t(`${i18nPrefix}.summary.totalCalls`) }}
                        {{ formatNumber(item.call_count) }}
                      </span>
                      <span>
                        {{ $t(`${i18nPrefix}.summary.totalTokens`) }}
                        {{ formatNumber(item.total_tokens) }}
                      </span>
                      <span>
                        {{ $t(`${i18nPrefix}.summary.totalCost`) }}
                        {{ formatCost(item.total_cost) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </section>
      </template>
    </Spin>
  </Page>
</template>

<style scoped>
.monitoring-usage-page :deep(.monitoring-range-picker.ant-picker) {
  min-height: 32px;
  border-radius: 12px;
}

.monitoring-usage-page :deep(.monitoring-range-picker.ant-picker:hover),
.monitoring-usage-page :deep(.monitoring-range-picker.ant-picker-focused) {
  box-shadow: none;
}

.monitoring-surface {
  width: 100%;
  height: auto;
  padding: 14px;
  background: hsl(var(--card));
  border: 1px solid hsl(var(--border) / 70%);
  border-radius: 24px;
  box-shadow: 0 10px 30px -24px rgb(15 23 42 / 28%);
}

.monitoring-surface__eyebrow {
  font-size: 11px;
  font-weight: 500;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.18em;
}

.monitoring-surface__title {
  margin-top: 4px;
  font-size: 1.1rem;
  font-weight: 600;
  line-height: 1.3;
  color: hsl(var(--foreground));
}

.monitoring-surface__desc {
  margin-top: 6px;
  font-size: 0.9rem;
  line-height: 1.5;
  color: hsl(var(--muted-foreground));
}

.monitoring-chart-shell {
  padding: 8px 10px;
  background: hsl(var(--background) / 82%);
  border: 1px solid hsl(var(--border) / 55%);
  border-radius: 20px;
}

.monitoring-list-shell {
  max-height: 360px;
  padding-right: 2px;
  overflow-y: auto;
}

.monitoring-chip {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  font-size: 12px;
  color: hsl(var(--muted-foreground));
  background: hsl(var(--background) / 88%);
  border: 1px solid hsl(var(--border) / 65%);
  border-radius: 9999px;
}

.monitoring-chip--sky {
  color: hsl(var(--primary));
  background: hsl(var(--primary) / 8%);
  border-color: hsl(var(--primary) / 16%);
}

.monitoring-chip--amber {
  color: hsl(var(--warning));
  background: hsl(var(--warning) / 12%);
  border-color: hsl(var(--warning) / 22%);
}

.monitoring-chip--violet {
  color: hsl(var(--primary));
  background: hsl(var(--primary) / 8%);
  border-color: hsl(var(--primary) / 16%);
}

.monitoring-chip--cyan {
  color: hsl(var(--success));
  background: hsl(var(--success) / 10%);
  border-color: hsl(var(--success) / 18%);
}

.monitoring-chip--rose {
  color: hsl(var(--destructive));
  background: hsl(var(--destructive) / 8%);
  border-color: hsl(var(--destructive) / 16%);
}
</style>
