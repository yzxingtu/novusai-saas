<script lang="ts" setup>
import type { SelectValue } from 'ant-design-vue/es/select';

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

defineOptions({ name: 'TenantAgentListToolbar' });

const props = defineProps<{
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
  'update:filterStatus': [value: string | undefined];
  'update:searchKeyword': [value: string];
}>();

function onSearchKeywordChange(value: string) {
  emit('update:searchKeyword', value);
  emit('search');
}

function normalizeSelectValue(value: SelectValue) {
  return typeof value === 'string' ? value : undefined;
}

function onStatusChange(value: SelectValue) {
  emit('update:filterStatus', normalizeSelectValue(value));
  emit('search');
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-3">
    <Input
      :value="props.searchKeyword"
      :placeholder="$t('tenant.ai.agent.placeholder.searchName')"
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
      :value="props.filterStatus"
      :placeholder="$t('tenant.ai.agent.status')"
      allow-clear
      class="!w-32"
      @update:value="onStatusChange"
    >
      <SelectOption value="published">
        {{ $t('tenant.ai.agent.status_options.published') }}
      </SelectOption>
      <SelectOption value="disabled">
        {{ $t('tenant.ai.agent.status_options.disabled') }}
      </SelectOption>
      <SelectOption value="draft">
        {{ $t('tenant.ai.agent.status_options.draft') }}
      </SelectOption>
    </Select>

    <Button
      v-if="props.hasActiveFilters"
      type="link"
      size="small"
      @click="emit('clearFilters')"
    >
      {{ $t('common.reset') }}
    </Button>

    <div class="flex-1"></div>

    <span v-access:code="['agent:recycle_bin']">
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
      v-access:code="['agent:create']"
      type="primary"
      @click="emit('createAgent')"
    >
      <template #icon>
        <IconifyIcon icon="lucide:plus" class="size-4" />
      </template>
      {{ $t('tenant.ai.agent.create') }}
    </Button>
  </div>
</template>
