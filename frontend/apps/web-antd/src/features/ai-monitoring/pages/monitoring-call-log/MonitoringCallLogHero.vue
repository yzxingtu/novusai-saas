<script lang="ts" setup>
import type { MonitoringCallLogInfo, MonitoringScope } from '../../api';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Tag } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import { createMonitoringCallerIdentityModel } from '../../identity';
import {
  buildMonitoringCallLogCallerMeta,
  createMonitoringCallLogMetricCards,
  createMonitoringCallLogSummaryChips,
  getInitialLetter,
  getMonitoringCallLogStatusColor,
  getMonitoringCallLogStatusText,
  isIconAvatar,
} from './monitoring-call-log-presentation';

defineOptions({ name: 'MonitoringCallLogHero' });

const props = defineProps<{
  detail: MonitoringCallLogInfo;
  drawerTitle: string;
  i18nPrefix: string;
  scope: MonitoringScope;
  summaryDescription: string;
}>();

const detailAgentName = computed(() => props.detail.agent_name || '-');
const callerIdentityModel = computed(() =>
  createMonitoringCallerIdentityModel(props.detail),
);
const callerContextLabel = computed(() => $t(`${props.i18nPrefix}.callerName`));
const statusText = computed(() =>
  getMonitoringCallLogStatusText(props.i18nPrefix, props.detail.status),
);
const summaryChips = computed(() =>
  createMonitoringCallLogSummaryChips(props.detail, props.i18nPrefix),
);
const metricCards = computed(() =>
  createMonitoringCallLogMetricCards(props.detail, props.i18nPrefix),
);
</script>

<template>
  <section
    class="rounded-[20px] border border-border/70 bg-gradient-to-br from-primary/10 via-background to-background px-5 py-4 shadow-sm"
  >
    <div
      class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between"
    >
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <span
            class="flex size-9 items-center justify-center rounded-xl bg-primary/15 text-primary"
          >
            <IconifyIcon icon="lucide:radar" class="size-5" />
          </span>
          <h3 class="text-base font-semibold text-foreground">
            {{ drawerTitle }}
          </h3>
        </div>
        <p class="mt-2 text-xs leading-5 text-muted-foreground">
          {{ summaryDescription }}
        </p>

        <div class="mt-3 flex flex-wrap gap-2">
          <span
            class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-2 py-1 text-xs"
          >
            <span
              class="flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-primary/10 text-primary"
            >
              <img
                v-if="detail.agent_avatar && !isIconAvatar(detail.agent_avatar)"
                :alt="detailAgentName"
                :src="toAvatarDisplayUrl(detail.agent_avatar)"
                class="size-full object-cover"
              />
              <IconifyIcon
                v-else-if="isIconAvatar(detail.agent_avatar)"
                :icon="String(detail.agent_avatar)"
                class="size-4"
              />
              <span v-else class="text-[11px] font-semibold">
                {{ getInitialLetter(detailAgentName) }}
              </span>
            </span>
            <span class="max-w-[180px] truncate text-foreground">
              {{ detailAgentName }}
            </span>
          </span>
          <span
            class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-3 py-1 text-xs"
          >
            <span class="font-mono text-foreground">#{{ detail.id }}</span>
          </span>
          <div
            class="inline-flex items-center rounded-2xl border border-border/70 bg-background/90 px-2 py-1"
          >
            <span class="mr-2 text-xs text-muted-foreground">
              {{ callerContextLabel }}
            </span>
            <IdentityTrigger
              v-if="callerIdentityModel"
              :avatar-size="28"
              :model="callerIdentityModel"
              :meta="buildMonitoringCallLogCallerMeta(detail, scope)"
              :context="callerContextLabel"
              :show-status-badge="false"
            />
          </div>
          <span
            v-for="chip in summaryChips"
            :key="chip.key"
            class="inline-flex max-w-full items-center gap-2 rounded-full border border-border/70 bg-background/90 px-3 py-1 text-xs"
          >
            <span class="text-muted-foreground">{{ chip.label }}</span>
            <span class="max-w-[220px] truncate text-foreground">
              {{ chip.value }}
            </span>
          </span>
        </div>
      </div>

      <div class="flex flex-col items-start gap-2 xl:items-end">
        <Tag :color="getMonitoringCallLogStatusColor(detail.status)">
          {{ statusText }}
        </Tag>
        <div class="rounded-xl border border-border/70 bg-card/90 px-3 py-2">
          <div class="text-[11px] text-muted-foreground">
            {{ $t(`${i18nPrefix}.createdAt`) }}
          </div>
          <div class="mt-1 text-xs font-medium text-foreground">
            {{ formatDate(detail.created_at) }}
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
    <article
      v-for="metric in metricCards"
      :key="metric.key"
      class="rounded-2xl border border-border/70 bg-card px-4 py-3 shadow-sm"
    >
      <div class="flex items-center gap-2 text-xs text-muted-foreground">
        <IconifyIcon :icon="metric.icon" class="size-4" />
        <span>{{ metric.label }}</span>
      </div>
      <div class="mt-2 text-lg font-semibold text-foreground">
        {{ metric.value }}
      </div>
    </article>
  </section>
</template>
