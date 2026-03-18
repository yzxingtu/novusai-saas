<script lang="ts" setup>
/**
 * 枚举值编辑器 / Enum values editor
 *
 * 可增删：value + label_zh + label_en + color，支持拖拽排序
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

import { Button, Input, Select, message } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import Sortable from 'sortablejs';

import { $t } from '#/locales';

defineOptions({ name: 'EnumValuesEditor' });

const props = defineProps<{
  modelValue: Array<{ value: string; label_zh?: string; label_en?: string; color?: string; __id?: string }>;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', v: Array<{ value: string; label_zh?: string; label_en?: string; color?: string }>): void;
}>();

function genEnumItemId() {
  return `ev_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

type ItemWithId = { value: string; label_zh?: string; label_en?: string; color?: string; __id: string };

const items = ref<ItemWithId[]>([]);

watch(
  () => props.modelValue,
  (raw) => {
    const arr = raw || [];
    const prev = items.value;
    items.value = arr.map((item, i) => {
      const hasId = (item as { __id?: string }).__id;
      if (hasId) return { ...item, __id: hasId } as ItemWithId;
      const prevItem = prev[i];
      const keepId = prevItem && String(prevItem.value) === String(item.value) ? prevItem.__id : undefined;
      return { ...item, __id: keepId || genEnumItemId() } as ItemWithId;
    });
  },
  { immediate: true },
);

function stripAndEmit(arr: ItemWithId[]) {
  emit(
    'update:modelValue',
    arr.map(({ __id: _, ...rest }) => rest),
  );
}

const listRef = ref<HTMLElement | null>(null);
let sortableInstance: ReturnType<typeof Sortable.create> | null = null;

function initSortable() {
  if (!listRef.value || items.value.length === 0) return;
  sortableInstance?.destroy();
  sortableInstance = Sortable.create(listRef.value, {
    animation: 150,
    handle: '.enum-drag-handle',
    onEnd: (evt) => {
      const from = evt.oldIndex;
      const to = evt.newIndex;
      if (from == null || to == null || from === to) return;
      const arr = [...items.value];
      const [removed] = arr.splice(from, 1);
      arr.splice(to, 0, removed);
      items.value = arr;
      stripAndEmit(arr);
    },
  });
}

onMounted(() => nextTick(initSortable));
watch(
  () => items.value.length,
  () => nextTick(initSortable),
);
onUnmounted(() => {
  sortableInstance?.destroy();
  sortableInstance = null;
});

const colorOptions = computed(() => [
  { label: $t('admin.system.codegen.enum.colorOptions.default'), value: 'default' },
  { label: $t('admin.system.codegen.enum.colorOptions.success'), value: 'success' },
  { label: $t('admin.system.codegen.enum.colorOptions.warning'), value: 'warning' },
  { label: $t('admin.system.codegen.enum.colorOptions.error'), value: 'error' },
  { label: $t('admin.system.codegen.enum.colorOptions.processing'), value: 'processing' },
]);

function addItem() {
  const next = [...items.value, { value: '', label_zh: '', label_en: '', color: 'default', __id: genEnumItemId() } as ItemWithId];
  items.value = next;
  stripAndEmit(next);
}

function removeItem(idx: number) {
  const next = items.value.filter((_, i) => i !== idx);
  items.value = next;
  stripAndEmit(next);
}

function updateItem(idx: number, patch: Record<string, string>) {
  const next = [...items.value];
  const updated = { ...next[idx], ...patch } as ItemWithId;
  if (patch.value && patch.value.trim()) {
    const exists = next.some((it, i) => i !== idx && (it.value === patch.value || String(it.value).trim() === patch.value.trim()));
    if (exists) {
      message.warning($t('admin.system.codegen.property.duplicateEnumValue'));
      return;
    }
  }
  next[idx] = updated;
  items.value = next;
  stripAndEmit(next);
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div ref="listRef" class="flex flex-col gap-2">
      <div
        v-for="(item, idx) in items"
        :key="(item as { __id?: string }).__id || idx"
        class="flex flex-wrap items-center gap-2 rounded border border-border p-2"
      >
        <span class="enum-drag-handle cursor-grab touch-none shrink-0 text-muted-foreground active:cursor-grabbing" :title="$t('admin.system.codegen.field.dragSort')">
        <IconifyIcon icon="lucide:grip-vertical" class="size-4" />
      </span>
      <Input
        :value="item.value"
        :placeholder="$t('admin.system.codegen.field.enumValuePlaceholder')"
        size="small"
        class="min-w-16 flex-1 max-w-32"
        @update:value="(v: string) => updateItem(idx, { value: v })"
      />
      <Input
        :value="item.label_zh"
        :placeholder="$t('admin.system.codegen.field.enumLabelZh')"
        size="small"
        class="min-w-16 flex-1 max-w-28"
        @update:value="(v: string) => updateItem(idx, { label_zh: v })"
      />
      <Input
        :value="item.label_en"
        :placeholder="$t('admin.system.codegen.field.enumLabelEn')"
        size="small"
        class="min-w-16 flex-1 max-w-28"
        @update:value="(v: string) => updateItem(idx, { label_en: v })"
      />
      <Select
        :value="item.color"
        :options="colorOptions"
        size="small"
        class="min-w-16 flex-1 max-w-32"
        @change="(v: string) => updateItem(idx, { color: v })"
      />
        <Button type="text" danger size="small" @click="removeItem(idx)">
          {{ $t('common.delete') }}
        </Button>
      </div>
    </div>
    <Button type="dashed" size="small" class="add-enum-btn" @click="addItem">
      {{ $t('admin.system.codegen.field.addEnumValue') }}
    </Button>
  </div>
</template>
