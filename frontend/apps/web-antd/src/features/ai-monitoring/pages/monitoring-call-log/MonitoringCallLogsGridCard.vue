<script lang="ts" setup>
import type { Component } from 'vue';

import type { MonitoringCallLogInfo, MonitoringScope } from '../../api';

import { IconifyIcon } from '@vben/icons';

import { Card, Tag, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import {
  createMonitoringCallerDetailMeta,
  createMonitoringCallerIdentityModel,
} from '../../identity';

defineOptions({ name: 'MonitoringCallLogsGridCard' });

const props = defineProps<{
  bodyStyle: Record<string, string>;
  gridComponent: Component;
  i18nPrefix: string;
  scope: MonitoringScope;
}>();

function isIconAvatar(avatar: null | string | undefined): boolean {
  return Boolean(avatar && String(avatar).includes(':'));
}

function getAgentDisplayName(row: MonitoringCallLogInfo) {
  if (row.agent_name) {
    return row.agent_name;
  }
  if (row.agent_id) {
    return `#${row.agent_id}`;
  }
  return '-';
}

function buildCallerMeta(row: MonitoringCallLogInfo) {
  return createMonitoringCallerDetailMeta(row, {
    createdAt: row.created_at,
    scope: props.scope,
    tenantId: row.tenant_id,
    tenantName: row.tenant_name,
  });
}

function getStatusText(status?: null | string) {
  if (!status) {
    return '-';
  }
  const key = `${props.i18nPrefix}.status_options.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

function formatCost(cost?: null | number) {
  return `$${Number(cost || 0).toFixed(4)}`;
}
</script>

<template>
  <Card class="flex-1" :body-style="bodyStyle">
    <component :is="gridComponent" class="monitoring-grid">
      <template #agent_cell="{ row }">
        <div class="flex items-center gap-2.5">
          <div
            class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-primary/10 text-primary shadow-sm"
          >
            <IconifyIcon
              v-if="isIconAvatar(row.agent_avatar)"
              :icon="String(row.agent_avatar)"
              class="size-4"
            />
            <img
              v-else-if="row.agent_avatar"
              :alt="getAgentDisplayName(row)"
              :src="toAvatarDisplayUrl(row.agent_avatar)"
              class="size-full object-cover"
            />
            <span v-else class="text-sm font-semibold">
              {{ getAgentDisplayName(row).charAt(0).toUpperCase() }}
            </span>
          </div>
          <div class="min-w-0">
            <div class="truncate text-sm font-medium text-foreground">
              {{ getAgentDisplayName(row) }}
            </div>
            <div class="truncate text-xs text-muted-foreground">
              {{ row.conversation_id ? `#${row.conversation_id}` : '-' }}
            </div>
          </div>
        </div>
      </template>
      <template #model_cell="{ row }">
        <div class="min-w-0">
          <div class="truncate font-medium text-foreground">
            {{ row.model_name || '-' }}
          </div>
          <div class="text-xs text-muted-foreground">
            {{ Number(row.total_tokens ?? 0).toLocaleString() }}
            {{ $t(`${i18nPrefix}.totalTokens`) }}
          </div>
        </div>
      </template>
      <template #provider_cell="{ row }">
        <div class="flex items-center gap-2">
          <span
            class="inline-flex size-6 shrink-0 items-center justify-center rounded-lg bg-muted/70 text-muted-foreground"
          >
            <IconifyIcon icon="lucide:cpu" class="size-3" />
          </span>
          <span class="truncate text-sm text-foreground">
            {{ row.provider_name || '-' }}
          </span>
        </div>
      </template>
      <template #caller_cell="{ row }">
        <IdentityTrigger
          :avatar-size="30"
          badge-wrap="nowrap"
          :model="createMonitoringCallerIdentityModel(row)"
          :meta="buildCallerMeta(row)"
          :context="$t(`${i18nPrefix}.callerName`)"
          :show-secondary-text="false"
          vertical-align="center"
        />
      </template>
      <template #requestType_cell="{ row }">
        <Tag color="blue">
          {{ row.request_type }}
        </Tag>
      </template>
      <template #createdAt_cell="{ row }">
        <Tooltip :title="formatDate(row.created_at)">
          <span class="text-muted-foreground">
            {{ formatRelativeTime(row.created_at) }}
          </span>
        </Tooltip>
      </template>
      <template #status_cell="{ row }">
        <Tag
          :color="
            row.status === 'success'
              ? 'success'
              : row.status === 'timeout'
                ? 'warning'
                : 'error'
          "
        >
          {{ getStatusText(row.status) }}
        </Tag>
      </template>
      <template #cost_cell="{ row }">
        <span class="font-mono text-sm text-muted-foreground">
          {{ formatCost(row.cost) }}
        </span>
      </template>
    </component>
  </Card>
</template>
