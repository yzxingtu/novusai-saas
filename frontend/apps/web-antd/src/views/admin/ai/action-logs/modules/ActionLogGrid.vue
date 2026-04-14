<script lang="ts" setup>
import type { Component } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Tag, Tooltip } from 'ant-design-vue';

import { PLATFORM_TENANT_ID } from '#/constants';
import { formatDate, formatRelativeTime } from '#/utils/common';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import {
  buildOperatorMeta,
  getAgentAvatarUrl,
  getAgentDisplayName,
  getOperatorIdentityModel,
  isIconAvatar,
} from '../action-log-detail-helpers';
import {
  getLevelColor,
  getLevelText,
  getStatusColor,
  getStatusText,
  getTenantDisplay,
  getTypeColor,
  getTypeText,
} from '../data';

defineOptions({ name: 'ActionLogGrid' });

defineProps<{
  gridComponent: Component;
}>();
</script>

<template>
  <component :is="gridComponent">
    <template #createdAt_cell="{ row }">
      <Tooltip :title="formatDate(row.created_at)">
        <span class="text-muted-foreground">
          {{ formatRelativeTime(row.created_at) }}
        </span>
      </Tooltip>
    </template>

    <template #actionName_cell="{ row }">
      <div class="flex items-center gap-1.5">
        <IconifyIcon icon="lucide:zap" class="size-3.5 text-primary" />
        <code class="rounded bg-accent px-1 py-0.5 text-xs font-medium">
          {{ row.action_name }}
        </code>
      </div>
    </template>

    <template #actionType_cell="{ row }">
      <Tag :color="getTypeColor(row.action_type)">
        {{ getTypeText(row.action_type) }}
      </Tag>
    </template>

    <template #actionLevel_cell="{ row }">
      <Tag :color="getLevelColor(row.action_level)">
        {{ getLevelText(row.action_level) }}
      </Tag>
    </template>

    <template #status_cell="{ row }">
      <Tag :color="getStatusColor(row.status)">
        {{ getStatusText(row.status) }}
      </Tag>
    </template>

    <template #agent_cell="{ row }">
      <div class="flex items-center gap-2">
        <div
          class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-primary/10 text-primary shadow-sm"
        >
          <img
            v-if="getAgentAvatarUrl(row.agent_avatar)"
            :alt="getAgentDisplayName(row)"
            :src="getAgentAvatarUrl(row.agent_avatar) ?? undefined"
            class="size-full object-cover"
          />
          <IconifyIcon
            v-else-if="isIconAvatar(row.agent_avatar)"
            :icon="String(row.agent_avatar)"
            class="size-4.5"
          />
          <span v-else class="text-sm font-semibold">
            {{ getAgentDisplayName(row).charAt(0).toUpperCase() }}
          </span>
        </div>
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm font-medium text-foreground">
            {{ getAgentDisplayName(row) }}
          </div>
          <div
            v-if="row.agent_id"
            class="truncate text-xs text-muted-foreground"
          >
            #{{ row.agent_id }}
          </div>
        </div>
      </div>
    </template>

    <template #tenantInfo_cell="{ row }">
      <div class="flex min-w-0 flex-col">
        <span class="truncate font-medium">
          {{ getTenantDisplay(row) }}
        </span>
        <span
          v-if="row.tenant_id !== PLATFORM_TENANT_ID && row.tenant_code"
          class="text-xs text-muted-foreground"
        >
          {{ row.tenant_code }}
        </span>
      </div>
    </template>

    <template #operator_cell="{ row }">
      <IdentityTrigger
        :avatar-size="30"
        :model="getOperatorIdentityModel(row)"
        :meta="buildOperatorMeta(row)"
        :show-status-badge="false"
      />
    </template>

    <template #duration_cell="{ row }">
      <span v-if="row.duration_ms" class="text-muted-foreground">
        {{ row.duration_ms }}ms
      </span>
      <span v-else class="text-muted-foreground">-</span>
    </template>

    <template #trace_cell="{ row }">
      <div class="flex min-w-0 flex-col">
        <code
          v-if="row.trace_id"
          class="truncate rounded bg-accent px-1 py-0.5 text-xs"
        >
          {{ row.trace_id }}
        </code>
        <span v-else class="text-muted-foreground">-</span>
        <span
          v-if="row.tool_call_id"
          class="truncate text-[11px] text-muted-foreground"
        >
          {{ row.tool_call_id }}
        </span>
      </div>
    </template>
  </component>
</template>
