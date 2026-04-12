<script lang="ts" setup>
import type { MonitoringUsageBreakdownItem } from '../../api';

import { Empty } from 'ant-design-vue';

import { $t } from '#/locales';

import {
  formatCost,
  formatNumber,
  formatShare,
  maxCallCount,
  progressWidth,
} from './formatters';

defineOptions({ name: 'MonitoringUsageTopTenantsCard' });

defineProps<{
  breakdownLabel: (item: MonitoringUsageBreakdownItem) => string;
  i18nPrefix: string;
  tenantLeaders: MonitoringUsageBreakdownItem[];
  topTenant: MonitoringUsageBreakdownItem | null;
  totalCalls: number;
}>();
</script>

<template>
  <article class="monitoring-surface">
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
          {{ topTenant ? formatCost(topTenant.total_cost) : formatCost(0) }}
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
</template>
