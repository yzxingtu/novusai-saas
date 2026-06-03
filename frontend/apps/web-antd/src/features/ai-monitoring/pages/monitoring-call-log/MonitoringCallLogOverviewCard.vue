<script lang="ts" setup>
import type { MonitoringCallLogInfo, MonitoringScope } from '../../api';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { IdentitySummaryCard } from '#/components/business/identity-display';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import { createMonitoringCallerIdentityModel } from '../../identity';
import {
  buildMonitoringCallLogCallerMeta,
  createMonitoringCallLogDetailFields,
  getInitialLetter,
  getMonitoringCallLogStatusText,
  isIconAvatar,
} from './monitoring-call-log-presentation';

defineOptions({ name: 'MonitoringCallLogOverviewCard' });

const props = defineProps<{
  detail: MonitoringCallLogInfo;
  drawerTitle: string;
  i18nPrefix: string;
  scope: MonitoringScope;
}>();

const detailAgentName = computed(() => props.detail.agent_name || '-');
const callerContextLabel = computed(() => $t(`${props.i18nPrefix}.callerName`));
const callerIdentityModel = computed(() =>
  createMonitoringCallerIdentityModel(props.detail),
);
const statusText = computed(() =>
  getMonitoringCallLogStatusText(props.i18nPrefix, props.detail.status),
);
const detailFields = computed(() =>
  createMonitoringCallLogDetailFields(
    props.detail,
    props.i18nPrefix,
    props.scope,
    formatDate(props.detail.created_at),
    statusText.value,
  ),
);
</script>

<template>
  <section
    class="mt-4 rounded-2xl border border-border/70 bg-card px-4 py-4 shadow-sm"
  >
    <div
      class="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground"
    >
      <IconifyIcon icon="lucide:list-tree" class="size-4 text-primary" />
      <span>{{ drawerTitle }}</span>
    </div>

    <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
      <div
        class="rounded-xl border border-border/60 bg-background/70 px-3 py-3"
      >
        <div class="text-xs text-muted-foreground">
          {{ $t(`${i18nPrefix}.agentName`) }}
        </div>
        <div class="mt-2 flex items-center gap-3">
          <div
            class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-primary/10 text-primary"
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
              class="size-5"
            />
            <span v-else class="text-sm font-semibold">
              {{ getInitialLetter(detailAgentName) }}
            </span>
          </div>
          <div class="min-w-0">
            <div class="truncate text-sm font-semibold text-foreground">
              {{ detailAgentName }}
            </div>
            <div
              v-if="detail.conversation_id"
              class="text-xs text-muted-foreground"
            >
              #{{ detail.conversation_id }}
            </div>
          </div>
        </div>
      </div>

      <IdentityTrigger
        v-if="callerIdentityModel"
        :model="callerIdentityModel"
        :meta="buildMonitoringCallLogCallerMeta(detail, scope)"
        :context="callerContextLabel"
      >
        <template #default="{ detailRequest }">
          <IdentitySummaryCard
            :detail-request="detailRequest"
            :model="callerIdentityModel"
            mode="embedded"
          />
        </template>
      </IdentityTrigger>

      <div
        v-else
        class="rounded-xl border border-border/60 bg-background/70 px-3 py-3"
      >
        <div class="text-xs text-muted-foreground">
          {{ $t(`${i18nPrefix}.callerName`) }}
        </div>
        <div class="mt-2 text-sm text-muted-foreground">-</div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-x-4 gap-y-3 md:grid-cols-2">
      <div
        v-for="field in detailFields"
        :key="field.key"
        class="rounded-xl border border-border/60 bg-background/70 px-3 py-2"
      >
        <div class="text-xs text-muted-foreground">{{ field.label }}</div>
        <div class="mt-1 break-all text-sm font-medium text-foreground">
          {{ field.value }}
        </div>
      </div>
    </div>
  </section>
</template>
