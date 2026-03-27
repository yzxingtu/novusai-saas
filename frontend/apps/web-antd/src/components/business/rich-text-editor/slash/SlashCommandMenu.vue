<script lang="ts" setup>
import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

interface CommandItem {
  key: string;
  icon: string;
  label: string;
  description: string;
}

const props = defineProps<{
  items: CommandItem[];
  query: string;
}>();

const emit = defineEmits<{
  select: [item: CommandItem];
}>();

const selectedIndex = ref(0);

const filteredItems = computed(() => {
  const q = props.query.toLowerCase();
  if (!q) return props.items;
  return props.items.filter(
    (item) =>
      item.label.toLowerCase().includes(q) ||
      item.key.toLowerCase().includes(q),
  );
});

watch(
  () => props.query,
  () => {
    selectedIndex.value = 0;
  },
);

function onKeydown(e: KeyboardEvent) {
  switch (e.key) {
    case 'ArrowDown': {
      e.preventDefault();
      selectedIndex.value =
        (selectedIndex.value + 1) % filteredItems.value.length;

      break;
    }
    case 'ArrowUp': {
      e.preventDefault();
      selectedIndex.value =
        (selectedIndex.value - 1 + filteredItems.value.length) %
        filteredItems.value.length;

      break;
    }
    case 'Enter': {
      e.preventDefault();
      const item = filteredItems.value[selectedIndex.value];
      if (item) emit('select', item);

      break;
    }
    // No default
  }
}

defineExpose({ onKeydown });
</script>

<template>
  <div
    v-if="filteredItems.length > 0"
    class="fixed z-[9000] min-w-[220px] rounded-lg border border-border bg-popover p-1.5 shadow-lg"
  >
    <button
      v-for="(item, index) in filteredItems"
      :key="item.key"
      class="flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm transition-colors"
      :class="
        index === selectedIndex
          ? 'bg-accent text-foreground'
          : 'text-muted-foreground hover:bg-accent/50'
      "
      @click="emit('select', item)"
      @mouseenter="selectedIndex = index"
    >
      <IconifyIcon :icon="item.icon" class="size-4 shrink-0" />
      <div class="flex-1">
        <div class="font-medium text-foreground">{{ item.label }}</div>
        <div class="text-xs text-muted-foreground">{{ item.description }}</div>
      </div>
    </button>
  </div>
</template>
