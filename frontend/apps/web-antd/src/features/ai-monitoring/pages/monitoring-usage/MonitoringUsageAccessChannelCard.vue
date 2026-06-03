<script lang="ts" setup>
import type { MonitoringUsageBreakdownItem } from '../../api';

import { Empty } from 'ant-design-vue';

import { $t } from '#/locales';

import {
  formatCost,
  formatNumber,
  formatShare,
  progressWidth,
} from './formatters';

defineOptions({ name: 'MonitoringUsageAccessChannelCard' });

defineProps<{
  breakdownLabel: (item: MonitoringUsageBreakdownItem) => string;
  i18nPrefix: string;
  items: MonitoringUsageBreakdownItem[];
  totalCalls: number;
}>();
</script>

<template>
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
        {{ formatNumber(items.length) }}
      </span>
    </div>

    <Empty
      v-if="items.length === 0"
      :description="$t(`${i18nPrefix}.list.empty`)"
    />
    <div v-else class="monitoring-list-shell mt-4 space-y-2.5">
      <div
        v-for="item in items"
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
</template>
