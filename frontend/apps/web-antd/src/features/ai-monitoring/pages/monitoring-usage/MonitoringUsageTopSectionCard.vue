<script lang="ts" setup>
import type {
  MonitoringScope,
  MonitoringUsageBreakdownItem,
} from '../../api';

import { IconifyIcon } from '@vben/icons';

import { Empty } from 'ant-design-vue';

import { $t } from '#/locales';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import {
  createMonitoringUsageActorDetailMeta,
  createMonitoringUsageActorIdentityModel,
} from '../../identity';
import {
  formatCost,
  formatNumber,
  formatShare,
  maxCallCount,
  progressWidth,
} from './formatters';
import type { UsageSection } from './use-monitoring-usage-dashboard';

defineOptions({ name: 'MonitoringUsageTopSectionCard' });

defineProps<{
  breakdownLabel: (item: MonitoringUsageBreakdownItem) => string;
  i18nPrefix: string;
  scope: MonitoringScope;
  section: UsageSection;
  tenantId?: number | null;
  tenantName?: string | null;
  totalCalls: number;
}>();
</script>

<template>
  <article class="monitoring-surface">
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
                    createMonitoringUsageActorIdentityModel(item)
                  "
                  :avatar-size="30"
                  badge-wrap="nowrap"
                  :model="createMonitoringUsageActorIdentityModel(item)!"
                  :meta="
                    createMonitoringUsageActorDetailMeta(item, {
                      scope,
                      tenantId,
                      tenantName,
                    })
                  "
                  :context="section.title"
                  :show-secondary-text="false"
                  vertical-align="center"
                />
                <div v-else class="truncate font-medium text-foreground">
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
</template>
