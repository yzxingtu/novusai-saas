<script lang="ts" setup>
import type { AgentListItem } from '#/api/tenant/agents';

import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Dropdown, Menu, MenuItem, Tag, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import {
  getExecutionModeText,
  getStatusText,
  isTenantOwnedAgent,
} from '../data';

defineOptions({ name: 'TenantAgentListCard' });

const props = defineProps<{
  agent: AgentListItem;
}>();

const emit = defineEmits<{
  delete: [agent: AgentListItem];
  edit: [agent: AgentListItem];
  publish: [agent: AgentListItem];
  versions: [agent: AgentListItem];
}>();

const router = useRouter();

function getExecutionModeIcon(mode: string): string {
  switch (mode) {
    case 'api': {
      return 'lucide:code';
    }
    case 'batch': {
      return 'lucide:layers';
    }
    case 'conversation': {
      return 'lucide:message-circle';
    }
    case 'task': {
      return 'lucide:list-checks';
    }
    default: {
      return 'lucide:bot';
    }
  }
}

function getStatusDotClass(status: string): string {
  switch (status) {
    case 'disabled': {
      return 'bg-red-400';
    }
    case 'published': {
      return 'bg-green-500';
    }
    default: {
      return 'bg-gray-400';
    }
  }
}

function openDetail() {
  router.push(`/tenant/ai/agents/${props.agent.id}`);
}

function openRouting() {
  router.push(`/tenant/ai/agents/${props.agent.id}?tab=routing`);
}
</script>

<template>
  <div
    class="group relative rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-primary/30 hover:shadow-md"
  >
    <div class="flex items-start gap-3.5">
      <div
        class="flex size-11 shrink-0 items-center justify-center rounded-xl text-base font-semibold"
        :class="
          props.agent.is_system
            ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
            : 'bg-primary/10 text-primary'
        "
      >
        <img
          v-if="props.agent.avatar && !String(props.agent.avatar).includes(':')"
          :src="toAvatarDisplayUrl(props.agent.avatar)"
          :alt="props.agent.name"
          class="size-full rounded-xl object-cover"
        />
        <IconifyIcon
          v-else-if="
            props.agent.avatar && String(props.agent.avatar).includes(':')
          "
          :icon="String(props.agent.avatar)"
          class="size-5"
        />
        <span v-else>{{
          props.agent.name?.charAt(0)?.toUpperCase() || '?'
        }}</span>
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <h3
            class="cursor-pointer truncate text-sm font-semibold text-foreground hover:text-primary"
            @click="openDetail"
          >
            {{ props.agent.name }}
          </h3>
          <Tag
            v-if="props.agent.is_system"
            color="purple"
            class="!mr-0 shrink-0 !text-[10px] !leading-4"
            style="padding: 0 5px"
          >
            {{ $t('tenant.ai.agent.system') }}
          </Tag>
        </div>
        <div class="mt-1 flex items-center gap-1.5">
          <span
            class="inline-block size-2 rounded-full"
            :class="getStatusDotClass(props.agent.status)"
          ></span>
          <span class="text-xs text-muted-foreground">
            {{ getStatusText(props.agent.status) }}
          </span>
        </div>
      </div>

      <Dropdown
        :trigger="['click']"
        placement="bottomRight"
        class="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
      >
        <button
          class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <IconifyIcon icon="lucide:more-vertical" class="size-4" />
        </button>
        <template #overlay>
          <Menu>
            <MenuItem key="detail" @click="openDetail">
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:settings" class="size-4" />
                <span>{{ $t('tenant.ai.agent.detail.title') }}</span>
              </div>
            </MenuItem>
            <MenuItem
              v-if="isTenantOwnedAgent(props.agent)"
              key="edit"
              @click="emit('edit', props.agent)"
            >
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:pencil" class="size-4" />
                <span>{{ $t('common.edit') }}</span>
              </div>
            </MenuItem>
            <MenuItem
              v-if="!props.agent.is_system && props.agent.status === 'draft'"
              key="publish"
              @click="emit('publish', props.agent)"
            >
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:rocket" class="size-4 text-success" />
                <span>{{ $t('tenant.ai.agent.actions.publish') }}</span>
              </div>
            </MenuItem>
            <MenuItem key="routing" @click="openRouting">
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:git-branch" class="size-4" />
                <span>{{ $t('tenant.ai.agent.detail.routing') }}</span>
              </div>
            </MenuItem>
            <MenuItem key="versions" @click="emit('versions', props.agent)">
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:history" class="size-4" />
                <span>{{ $t('tenant.ai.agent.actions.versions') }}</span>
              </div>
            </MenuItem>
            <MenuItem
              v-if="!props.agent.is_system && isTenantOwnedAgent(props.agent)"
              key="delete"
              class="!text-destructive"
              @click="emit('delete', props.agent)"
            >
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:trash-2" class="size-4" />
                <span>{{ $t('common.delete') }}</span>
              </div>
            </MenuItem>
          </Menu>
        </template>
      </Dropdown>
    </div>

    <p
      v-if="props.agent.description"
      class="mt-3 line-clamp-2 text-xs leading-relaxed text-muted-foreground"
    >
      {{ props.agent.description }}
    </p>
    <p v-else class="mt-3 text-xs italic text-muted-foreground/50">
      {{ $t('tenant.ai.agent.noDescription') }}
    </p>

    <div class="mt-4 flex flex-wrap items-center gap-2">
      <Tooltip
        v-if="props.agent.model_name"
        :title="$t('tenant.ai.agent.modelName')"
      >
        <div
          class="flex items-center gap-1.5 rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
        >
          <IconifyIcon icon="lucide:brain" class="size-3" />
          <span>{{ props.agent.model_name }}</span>
        </div>
      </Tooltip>

      <Tooltip :title="$t('tenant.ai.agent.executionMode')">
        <div
          class="flex items-center gap-1.5 rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
        >
          <IconifyIcon
            :icon="getExecutionModeIcon(props.agent.execution_mode)"
            class="size-3"
          />
          <span>{{ getExecutionModeText(props.agent.execution_mode) }}</span>
        </div>
      </Tooltip>

      <Tag
        :color="getScopeColor(props.agent.scope)"
        class="!mr-0 !text-[11px]"
        style="padding: 0 6px; line-height: 20px"
      >
        <div class="flex items-center gap-1">
          <IconifyIcon icon="lucide:share-2" class="size-3" />
          <span>{{ getScopeText(props.agent.scope) }}</span>
        </div>
      </Tag>

      <Tag
        v-for="skill in (props.agent.skills || []).slice(0, 3)"
        :key="skill.id"
        color="cyan"
        class="!mr-0 !text-[11px]"
        style="padding: 0 6px; line-height: 20px"
      >
        {{ skill.name }}
      </Tag>
      <Tooltip
        v-if="props.agent.skills && props.agent.skills.length > 3"
        :title="
          props.agent.skills
            .slice(3)
            .map((skill: { name: string }) => skill.name)
            .join(', ')
        "
      >
        <Tag
          color="cyan"
          class="!mr-0 !text-[11px]"
          style="padding: 0 6px; line-height: 20px"
        >
          +{{ props.agent.skills.length - 3 }}
        </Tag>
      </Tooltip>

      <span
        v-if="props.agent.published_version"
        class="rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
      >
        v{{ props.agent.published_version }}
      </span>
    </div>

    <div
      class="mt-4 flex items-center justify-between border-t border-border/50 pt-3 text-[11px] text-muted-foreground"
    >
      <Tooltip :title="formatDate(props.agent.created_at)">
        <span>{{ formatRelativeTime(props.agent.created_at) }}</span>
      </Tooltip>
      <div class="flex items-center gap-2">
        <button
          class="flex items-center gap-1 rounded-md px-2 py-1 text-primary transition-colors hover:bg-primary/10"
          @click="openDetail"
        >
          <IconifyIcon icon="lucide:settings" class="size-3" />
          <span>{{ $t('tenant.ai.agent.detail.title') }}</span>
        </button>
        <button
          v-if="isTenantOwnedAgent(props.agent)"
          class="flex items-center gap-1 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          @click="emit('edit', props.agent)"
        >
          <IconifyIcon icon="lucide:pencil" class="size-3" />
          <span>{{ $t('common.edit') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
