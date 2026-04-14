<script lang="ts" setup>
import type { MonitoringConversationInfo, MonitoringScope } from '../../api';

import type { Component } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Card, Tag, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import {
  createMonitoringActorDetailMeta,
  createMonitoringActorIdentityModel,
} from '../../identity';

defineOptions({ name: 'MonitoringConversationsGridCard' });

const props = defineProps<{
  bodyStyle: Record<string, string>;
  gridComponent: Component;
  i18nPrefix: string;
  scope: MonitoringScope;
}>();

function isIconAvatar(avatar: null | string | undefined): boolean {
  return Boolean(avatar && String(avatar).includes(':'));
}

function getConversationAgentName(row: MonitoringConversationInfo) {
  if (row.agent_name) {
    return row.agent_name;
  }
  if (row.agent_id) {
    return `#${row.agent_id}`;
  }
  return '-';
}

function buildActorMeta(row: MonitoringConversationInfo) {
  return createMonitoringActorDetailMeta(row.actor, {
    scope: props.scope,
    tenantId: row.actor?.tenant_id ?? row.tenant_id,
    tenantName: row.actor?.tenant_name ?? row.tenant_name,
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

function formatTokens(tokens?: null | number) {
  return Number(tokens || 0).toLocaleString();
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
              :alt="getConversationAgentName(row)"
              :src="toAvatarDisplayUrl(row.agent_avatar)"
              class="size-full object-cover"
            />
            <span v-else class="text-sm font-semibold">
              {{ getConversationAgentName(row).charAt(0).toUpperCase() }}
            </span>
          </div>
          <div class="min-w-0">
            <div class="truncate text-sm font-medium text-foreground">
              {{ getConversationAgentName(row) }}
            </div>
            <div class="truncate text-xs text-muted-foreground">
              #{{ row.id }}
            </div>
          </div>
        </div>
      </template>

      <template #title_cell="{ row }">
        <div class="min-w-0">
          <Tooltip :title="row.title || $t(`${i18nPrefix}.untitled`)">
            <div class="truncate text-sm font-medium text-foreground">
              {{ row.title || $t(`${i18nPrefix}.untitled`) }}
            </div>
          </Tooltip>
          <div class="truncate text-xs text-muted-foreground">
            {{ row.last_call_at ? formatRelativeTime(row.last_call_at) : '-' }}
          </div>
        </div>
      </template>

      <template #tenant_cell="{ row }">
        <span class="truncate text-sm text-foreground">
          {{ row.tenant_name || '-' }}
        </span>
      </template>

      <template #actor_cell="{ row }">
        <IdentityTrigger
          v-if="row.actor"
          :avatar-size="30"
          badge-wrap="nowrap"
          :model="createMonitoringActorIdentityModel(row.actor)!"
          :meta="buildActorMeta(row)"
          :show-secondary-text="false"
          vertical-align="center"
        />
        <span v-else class="text-muted-foreground">-</span>
      </template>

      <template #status_cell="{ row }">
        <Tag :color="row.status === 'active' ? 'success' : 'default'">
          {{ getStatusText(row.status) }}
        </Tag>
      </template>

      <template #tokens_cell="{ row }">
        <span class="font-mono text-sm text-muted-foreground">
          {{ formatTokens(row.total_tokens) }}
        </span>
      </template>

      <template #cost_cell="{ row }">
        <span class="font-mono text-sm text-muted-foreground">
          {{ formatCost(row.total_cost) }}
        </span>
      </template>

      <template #lastCall_cell="{ row }">
        <Tooltip :title="row.last_call_at ? formatDate(row.last_call_at) : '-'">
          <span class="text-muted-foreground">
            {{ row.last_call_at ? formatRelativeTime(row.last_call_at) : '-' }}
          </span>
        </Tooltip>
      </template>

      <template #createdAt_cell="{ row }">
        <Tooltip :title="formatDate(row.created_at)">
          <span class="text-muted-foreground">
            {{ formatRelativeTime(row.created_at) }}
          </span>
        </Tooltip>
      </template>
    </component>
  </Card>
</template>
