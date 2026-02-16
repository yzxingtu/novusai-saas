<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';

import { Input, Modal } from 'ant-design-vue';

import { $t } from '#/locales';

export interface CommandItem {
  key: string;
  label: string;
  icon: string;
  shortcut?: string;
  action: () => void;
}

const props = defineProps<{
  open: boolean;
  commands: CommandItem[];
}>();

const emit = defineEmits<{
  close: [];
}>();

const T = 'admin.dev.crudGenerator.command';

const query = ref('');
const selectedIndex = ref(0);
const inputRef = ref<HTMLInputElement>();

const filtered = computed(() => {
  if (!query.value) return props.commands;
  const q = query.value.toLowerCase();
  return props.commands.filter(
    (c) => c.label.toLowerCase().includes(q) || c.key.toLowerCase().includes(q),
  );
});

watch(
  () => props.open,
  (val) => {
    if (val) {
      query.value = '';
      selectedIndex.value = 0;
      nextTick(() => {
        inputRef.value?.focus();
      });
    }
  },
);

watch(query, () => {
  selectedIndex.value = 0;
});

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    selectedIndex.value = Math.min(selectedIndex.value + 1, filtered.value.length - 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    selectedIndex.value = Math.max(selectedIndex.value - 1, 0);
  } else if (e.key === 'Enter') {
    e.preventDefault();
    const item = filtered.value[selectedIndex.value];
    if (item) {
      item.action();
      emit('close');
    }
  } else if (e.key === 'Escape') {
    emit('close');
  }
}

function executeCommand(item: CommandItem) {
  item.action();
  emit('close');
}
</script>

<template>
  <Modal
    :closable="false"
    :footer="null"
    :mask-closable="true"
    :open="open"
    :width="480"
    class="command-palette-modal"
    @cancel="emit('close')"
  >
    <div class="command-palette" @keydown="onKeyDown">
      <div class="border-b p-2">
        <Input
          ref="inputRef"
          v-model:value="query"
          :bordered="false"
          :placeholder="$t(`${T}.placeholder`)"
          size="large"
        >
          <template #prefix>
            <span class="icon-[lucide--search] text-muted-foreground size-4" />
          </template>
        </Input>
      </div>

      <div class="max-h-[320px] overflow-auto p-1">
        <template v-if="filtered.length > 0">
          <div
            v-for="(cmd, idx) in filtered"
            :key="cmd.key"
            :class="[
              'flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm transition-colors',
              idx === selectedIndex
                ? 'bg-primary/10 text-primary'
                : 'hover:bg-accent',
            ]"
            @click="executeCommand(cmd)"
            @mouseenter="selectedIndex = idx"
          >
            <span class="flex items-center gap-2">
              <span :class="[cmd.icon, 'size-4 opacity-60']" />
              {{ cmd.label }}
            </span>
            <span
              v-if="cmd.shortcut"
              class="text-muted-foreground text-xs"
            >
              {{ cmd.shortcut }}
            </span>
          </div>
        </template>
        <div v-else class="text-muted-foreground py-8 text-center text-sm">
          {{ $t(`${T}.noResults`) }}
        </div>
      </div>
    </div>
  </Modal>
</template>

<style scoped>
:deep(.command-palette-modal .ant-modal-body) {
  padding: 0;
}
</style>
