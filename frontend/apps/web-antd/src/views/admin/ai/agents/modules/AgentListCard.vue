<script lang="ts" setup>
import type { AIAgentInfo } from '#/api/admin/ai-agents';

import { computed } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Dropdown, Menu, MenuItem, Tag, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import { getExecutionModeText, getStatusText } from '../data';
import PluginSourceBadge from './PluginSourceBadge.vue';

defineOptions({ name: 'AgentListCard' });

const props = defineProps<{
  agent: AIAgentInfo;
}>();

const emit = defineEmits<{
  delete: [agent: AIAgentInfo];
  edit: [agent: AIAgentInfo];
  publish: [agent: AIAgentInfo];
  toggleStatus: [agent: AIAgentInfo];
  versions: [agent: AIAgentInfo];
}>();

const router = useRouter();

const hasRoutingEnabled = computed(() =>
  Boolean(
    (props.agent.routing_config as null | Record<string, unknown>)
      ?.enable_routing,
  ),
);

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
  router.push(`/admin/ai/agents/${props.agent.id}`);
}

function openRouting() {
  router.push(`/admin/ai/agents/${props.agent.id}?tab=routing`);
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
            v-if="props.agent.source_plugin || props.agent.is_system"
            color="purple"
            class="!mr-0 shrink-0 !text-[10px] !leading-4"
            style="padding: 0 5px"
          >
            {{
              props.agent.source_plugin
                ? $t('admin.ai.skillPackage.sourcePlugin')
                : $t('admin.ai.agent.system')
            }}
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
                <span>{{ $t('admin.ai.agent.detail.title') }}</span>
              </div>
            </MenuItem>
            <MenuItem key="edit" @click="emit('edit', props.agent)">
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:pencil" class="size-4" />
                <span>{{ $t('admin.common.edit') }}</span>
              </div>
            </MenuItem>
            <MenuItem
              v-if="!props.agent.is_system && props.agent.status !== 'draft'"
              key="toggle"
              @click="emit('toggleStatus', props.agent)"
            >
              <div class="flex items-center gap-2">
                <IconifyIcon
                  :icon="
                    props.agent.status === 'published'
                      ? 'lucide:pause-circle'
                      : 'lucide:play-circle'
                  "
                  class="size-4"
                />
                <span>
                  {{
                    props.agent.status === 'published'
                      ? $t('admin.ai.agent.status_options.disabled')
                      : $t('admin.ai.agent.status_options.published')
                  }}
                </span>
              </div>
            </MenuItem>
            <MenuItem
              v-if="!props.agent.is_system && props.agent.status === 'draft'"
              key="publish"
              @click="emit('publish', props.agent)"
            >
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:rocket" class="size-4 text-success" />
                <span>{{ $t('admin.ai.agent.actions.publish') }}</span>
              </div>
            </MenuItem>
            <MenuItem key="routing" @click="openRouting">
              <div class="flex items-center gap-2">
                <IconifyIcon
                  icon="lucide:git-branch"
                  :class="
                    hasRoutingEnabled ? 'size-4 text-green-500' : 'size-4'
                  "
                />
                <span>{{ $t('admin.ai.agent.detail.routing') }}</span>
              </div>
            </MenuItem>
            <MenuItem key="versions" @click="emit('versions', props.agent)">
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:history" class="size-4" />
                <span>{{ $t('admin.ai.agent.actions.versions') }}</span>
              </div>
            </MenuItem>
            <MenuItem
              v-if="!props.agent.is_system"
              key="delete"
              class="!text-destructive"
              @click="emit('delete', props.agent)"
            >
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:trash-2" class="size-4" />
                <span>{{ $t('admin.common.delete') }}</span>
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
      {{ $t('admin.ai.agent.noDescription') }}
    </p>

    <div class="mt-4 flex flex-wrap items-center gap-2">
      <Tooltip
        v-if="props.agent.model_name"
        :title="$t('admin.ai.agent.modelName')"
      >
        <div
          class="flex items-center gap-1.5 rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
        >
          <IconifyIcon icon="lucide:brain" class="size-3" />
          <span>{{ props.agent.model_name }}</span>
        </div>
      </Tooltip>

      <Tooltip :title="$t('admin.ai.agent.executionMode')">
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

      <PluginSourceBadge
        v-if="props.agent.source_plugin"
        :source-plugin="props.agent.source_plugin"
        :source-plugin-display-name="props.agent.source_plugin_display_name"
        :source-plugin-enabled="props.agent.source_plugin_enabled"
      />

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

      <Tooltip
        v-if="hasRoutingEnabled"
        :title="$t('admin.ai.agent.routing.statusEnabled')"
      >
        <div
          class="flex items-center gap-1 rounded-md bg-green-500/10 px-2 py-1 text-[11px] font-medium text-green-600 dark:text-green-400"
        >
          <IconifyIcon icon="lucide:git-branch" class="size-3" />
          <span>{{ $t('admin.ai.agent.routing.statusEnabled') }}</span>
        </div>
      </Tooltip>

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
          <span>{{ $t('admin.ai.agent.detail.title') }}</span>
        </button>
        <button
          class="flex items-center gap-1 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          @click="emit('edit', props.agent)"
        >
          <IconifyIcon icon="lucide:pencil" class="size-3" />
          <span>{{ $t('admin.common.edit') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
