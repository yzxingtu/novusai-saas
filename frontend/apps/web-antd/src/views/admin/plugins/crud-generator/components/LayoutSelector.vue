<script setup lang="ts">
import { computed } from 'vue';

import { $t } from '#/locales';

import type { LayoutVariant } from '../types';

const props = defineProps<{
  value: LayoutVariant;
}>();

const emit = defineEmits<{
  change: [value: LayoutVariant];
}>();

const T = 'admin.dev.crudGenerator.layout';

interface LayoutOption {
  value: LayoutVariant;
  icon: string;
  titleKey: string;
  descKey: string;
}

const layouts = computed<LayoutOption[]>(() => [
  {
    value: 'standard',
    icon: 'icon-[lucide--table]',
    titleKey: 'standard',
    descKey: 'standardDesc',
  },
  {
    value: 'card_list',
    icon: 'icon-[lucide--layout-grid]',
    titleKey: 'cardList',
    descKey: 'cardListDesc',
  },
  {
    value: 'master_detail',
    icon: 'icon-[lucide--columns-2]',
    titleKey: 'masterDetail',
    descKey: 'masterDetailDesc',
  },
  {
    value: 'tree_table',
    icon: 'icon-[lucide--network]',
    titleKey: 'treeTable',
    descKey: 'treeTableDesc',
  },
  {
    value: 'kanban',
    icon: 'icon-[lucide--kanban]',
    titleKey: 'kanban',
    descKey: 'kanbanDesc',
  },
  {
    value: 'timeline',
    icon: 'icon-[lucide--calendar-clock]',
    titleKey: 'timeline',
    descKey: 'timelineDesc',
  },
]);

function select(val: LayoutVariant) {
  emit('change', val);
}
</script>

<template>
  <div class="grid grid-cols-3 gap-3 lg:grid-cols-6">
    <div
      v-for="layout in layouts"
      :key="layout.value"
      :class="[
        'cursor-pointer rounded-lg border-2 p-3 text-center transition-all',
        'hover:border-primary/50 hover:shadow-sm',
        value === layout.value
          ? 'border-primary bg-primary/5 shadow-sm'
          : 'border-border',
      ]"
      @click="select(layout.value)"
    >
      <span :class="[layout.icon, 'mx-auto mb-2 size-8 block opacity-60']" />
      <p class="text-sm font-medium">{{ $t(`${T}.${layout.titleKey}`) }}</p>
      <p class="text-muted-foreground mt-0.5 text-xs">
        {{ $t(`${T}.${layout.descKey}`) }}
      </p>
    </div>
  </div>
</template>
