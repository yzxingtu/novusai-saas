<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Input,
  Select,
  SelectOption,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { getAdminScopeOptions } from '#/utils/scope-helpers';

defineOptions({ name: 'AgentListToolbar' });

const props = defineProps<{
  filterScope?: string;
  filterStatus?: string;
  hasActiveFilters: boolean;
  recycleBinCount: number;
  searchKeyword: string;
}>();

const emit = defineEmits<{
  clearFilters: [];
  createAgent: [];
  openRecycleBin: [];
  search: [];
  'update:filterScope': [value: string | undefined];
  'update:filterStatus': [value: string | undefined];
  'update:searchKeyword': [value: string];
}>();

function onSearchKeywordChange(value: string) {
  emit('update:searchKeyword', value);
  emit('search');
}

function onScopeChange(value: string | undefined) {
  emit('update:filterScope', value);
  emit('search');
}

function onStatusChange(value: string | undefined) {
  emit('update:filterStatus', value);
  emit('search');
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-3">
    <Input
      :value="props.searchKeyword"
      :placeholder="$t('admin.ai.agent.placeholder.searchName')"
      allow-clear
      class="!w-64"
      @update:value="onSearchKeywordChange"
    >
      <template #prefix>
        <IconifyIcon
          icon="lucide:search"
          class="size-4 text-muted-foreground"
        />
      </template>
    </Input>

    <Select
      :value="props.filterScope"
      :placeholder="$t('common.scope.allScopes')"
      allow-clear
      class="!w-48"
      @update:value="onScopeChange"
    >
      <SelectOption
        v-for="option in getAdminScopeOptions()"
        :key="option.value"
        :value="option.value"
      >
        {{ option.label }}
      </SelectOption>
    </Select>

    <Select
      :value="props.filterStatus"
      :placeholder="$t('admin.ai.agent.status')"
      allow-clear
      class="!w-32"
      @update:value="onStatusChange"
    >
      <SelectOption value="published">
        {{ $t('admin.ai.agent.status_options.published') }}
      </SelectOption>
      <SelectOption value="disabled">
        {{ $t('admin.ai.agent.status_options.disabled') }}
      </SelectOption>
      <SelectOption value="draft">
        {{ $t('admin.ai.agent.status_options.draft') }}
      </SelectOption>
    </Select>

    <Button
      v-if="props.hasActiveFilters"
      type="link"
      size="small"
      @click="emit('clearFilters')"
    >
      {{ $t('admin.common.reset') }}
    </Button>

    <div class="flex-1"></div>

    <span v-access:code="['ai_agent:recycle_bin']">
      <Tooltip :title="$t('common.recycleBin.title')">
        <Badge :count="props.recycleBinCount" :offset="[-2, 2]" size="small">
          <Button @click="emit('openRecycleBin')">
            <template #icon>
              <IconifyIcon icon="lucide:trash-2" class="size-4" />
            </template>
          </Button>
        </Badge>
      </Tooltip>
    </span>

    <Button
      v-access:code="['ai_agent:create']"
      type="primary"
      @click="emit('createAgent')"
    >
      <template #icon>
        <IconifyIcon icon="lucide:plus" class="size-4" />
      </template>
      {{ $t('admin.ai.agent.create') }}
    </Button>
  </div>
</template>
