<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue';

import { Button, Empty } from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, FieldConfig } from '../types';
import { createDefaultField } from '../composables/field-inference';

import FieldCard from './FieldCard.vue';
import FieldCardExpanded from './FieldCardExpanded.vue';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
}>();

const emit = defineEmits<{
  'update:config': [config: CrudConfig];
  snapshot: [];
  openImport: [];
}>();

/** Track which field index is expanded */
const expandedIndex = ref<number | null>(null);

/** Container ref for SortableJS */
const listRef = ref<HTMLElement | null>(null);

function updateFields(fields: FieldConfig[]) {
  emit('update:config', { ...props.config, fields });
}

function updateFieldAt(index: number, field: FieldConfig) {
  const fields = [...props.config.fields];
  fields[index] = field;
  updateFields(fields);
}

function removeField(index: number) {
  const fields = props.config.fields.filter((_, i) => i !== index);
  updateFields(fields);
  if (expandedIndex.value === index) {
    expandedIndex.value = null;
  } else if (expandedIndex.value !== null && expandedIndex.value > index) {
    expandedIndex.value--;
  }
  emit('snapshot');
}

function addField() {
  const newField = createDefaultField();
  const fields = [...props.config.fields, newField];
  updateFields(fields);
  expandedIndex.value = fields.length - 1;
  emit('snapshot');

  // Auto-scroll to new field
  nextTick(() => {
    const container = listRef.value?.closest('.overflow-y-auto');
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  });
}

function toggleExpand(index: number) {
  expandedIndex.value = expandedIndex.value === index ? null : index;
}

/** Initialize SortableJS for drag-and-drop */
onMounted(async () => {
  if (!listRef.value) return;

  const SortableModule = await import(
    // @ts-expect-error - dynamic import
    'sortablejs/modular/sortable.complete.esm.js'
  );
  const Sortable = SortableModule?.default;
  if (!Sortable?.create) return;

  Sortable.create(listRef.value, {
    animation: 200,
    handle: '.drag-handle',
    ghostClass: 'sortable-ghost',
    chosenClass: 'sortable-chosen',
    onEnd: (evt: { newIndex?: number; oldIndex?: number }) => {
      const { oldIndex, newIndex } = evt;
      if (oldIndex === undefined || newIndex === undefined || oldIndex === newIndex) return;

      const fields = [...props.config.fields];
      const [moved] = fields.splice(oldIndex, 1);
      if (moved) {
        fields.splice(newIndex, 0, moved);
        updateFields(fields);
        emit('snapshot');

        // Update expanded index after reorder
        if (expandedIndex.value === oldIndex) {
          expandedIndex.value = newIndex;
        } else if (expandedIndex.value !== null) {
          if (oldIndex < expandedIndex.value && newIndex >= expandedIndex.value) {
            expandedIndex.value--;
          } else if (oldIndex > expandedIndex.value && newIndex <= expandedIndex.value) {
            expandedIndex.value++;
          }
        }
      }
    },
  });
});

/** Sync nameInput in FieldCard when field name changes externally */
watch(
  () => props.config.fields.length,
  () => {
    // Collapse expanded if out of bounds
    if (expandedIndex.value !== null && expandedIndex.value >= props.config.fields.length) {
      expandedIndex.value = null;
    }
  },
);
</script>

<template>
  <div class="field-list-section">
    <!-- Header actions -->
    <div class="mb-3 flex items-center justify-between">
      <span class="text-muted-foreground text-xs">
        {{ props.config.fields.length }} {{ $t(`${T}.history.files`) }}
      </span>
      <div class="flex items-center gap-1">
        <Button size="small" type="text" @click="emit('openImport')">
          <template #icon>
            <span class="icon-[lucide--upload] size-3.5" />
          </template>
          {{ $t(`${T}.field.import`) }}
        </Button>
        <Button size="small" type="primary" @click="addField">
          <template #icon>
            <span class="icon-[lucide--plus] size-3.5" />
          </template>
          {{ $t(`${T}.field.add`) }}
        </Button>
      </div>
    </div>

    <!-- Field cards -->
    <div v-if="config.fields.length > 0" ref="listRef" class="space-y-2">
      <div
        v-for="(field, idx) in config.fields"
        :key="`field-${idx}-${field.name}`"
        class="field-item"
      >
        <FieldCard
          :field="field"
          :index="idx"
          :expanded="expandedIndex === idx"
          @update:field="(f) => updateFieldAt(idx, f)"
          @remove="removeField(idx)"
          @toggle-expand="toggleExpand(idx)"
        >
          <template #expanded>
            <FieldCardExpanded
              :field="field"
              @update:field="(f) => updateFieldAt(idx, f)"
            />
          </template>
        </FieldCard>
      </div>
    </div>

    <!-- Empty state -->
    <Empty
      v-else
      :description="$t(`${T}.field.empty`)"
      class="py-8"
    >
      <Button type="primary" size="small" @click="addField">
        <template #icon>
          <span class="icon-[lucide--plus] size-3.5" />
        </template>
        {{ $t(`${T}.field.add`) }}
      </Button>
    </Empty>
  </div>
</template>

<style scoped>
.sortable-ghost {
  opacity: 0.4;
}
.sortable-chosen {
  box-shadow: 0 0 0 2px var(--primary);
  border-radius: 8px;
}
.field-item {
  transition: opacity 150ms ease, transform 150ms ease;
}
</style>
