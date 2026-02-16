<script setup lang="ts">
import { computed, ref } from 'vue';

import { Button, Input, Select, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

import type { FieldConfig, FieldType } from '../types';
import { getDefaultsByType, getFieldTypeOptions, inferFieldByName } from '../composables/field-inference';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  field: FieldConfig;
  index: number;
  expanded: boolean;
}>();

const emit = defineEmits<{
  'update:field': [field: FieldConfig];
  remove: [];
  toggleExpand: [];
}>();

const fieldTypeOptions = computed(() => getFieldTypeOptions());

/** Update a single field property */
function update<K extends keyof FieldConfig>(key: K, value: FieldConfig[K]) {
  emit('update:field', { ...props.field, [key]: value });
}

/** Batch update multiple properties */
function updateMulti(patch: Partial<FieldConfig>) {
  emit('update:field', { ...props.field, ...patch });
}

/** On field name blur — trigger smart inference */
const nameInput = ref<string>(props.field.name);

function onNameBlur() {
  const name = nameInput.value.trim();
  if (!name || name === props.field.name) return;

  const inferred = inferFieldByName(name);
  if (inferred) {
    updateMulti({ name, ...inferred });
  } else {
    update('name', name);
  }
}

/** On field type change — apply type defaults */
function onTypeChange(type: FieldType) {
  const defaults = getDefaultsByType(type);
  updateMulti({ type, ...defaults });
}

/** Toggle boolean field properties */
function toggleProp(key: 'in_form' | 'in_list' | 'required' | 'searchable') {
  update(key, !props.field[key]);
}
</script>

<template>
  <div
    class="field-card border-border hover:border-primary/30 hover:shadow-sm rounded-lg border bg-card transition-all duration-150"
    :class="{ 'border-primary/20 bg-accent/5 shadow-sm': expanded }"
  >
    <!-- Row 1: Core info -->
    <div class="flex items-center gap-1.5 px-3 py-2">
      <!-- Drag handle -->
      <span class="drag-handle icon-[lucide--grip-vertical] text-muted-foreground size-4 shrink-0 cursor-grab" />

      <!-- Field name (inline edit) -->
      <Input
        v-model:value="nameInput"
        :placeholder="$t(`${T}.field.namePlaceholder`)"
        size="small"
        class="w-[140px] font-mono text-xs"
        @blur="onNameBlur"
        @press-enter="onNameBlur"
      />

      <!-- Type select -->
      <Select
        :value="field.type"
        :options="fieldTypeOptions"
        size="small"
        class="w-[90px]"
        @change="(v: unknown) => onTypeChange(v as FieldType)"
      />

      <!-- Toggle buttons -->
      <div class="ml-auto flex items-center gap-0.5">
        <Tooltip :title="$t(`${T}.field.required`)">
          <Button
            size="small"
            :type="field.required ? 'primary' : 'text'"
            class="!h-6 !w-6 !p-0"
            @click="toggleProp('required')"
          >
            <span class="icon-[lucide--asterisk] size-3" />
          </Button>
        </Tooltip>

        <Tooltip :title="$t(`${T}.field.searchable`)">
          <Button
            size="small"
            :type="field.searchable ? 'primary' : 'text'"
            class="!h-6 !w-6 !p-0"
            @click="toggleProp('searchable')"
          >
            <span class="icon-[lucide--search] size-3" />
          </Button>
        </Tooltip>

        <Tooltip :title="$t(`${T}.field.inList`)">
          <Button
            size="small"
            :type="field.in_list ? 'primary' : 'text'"
            class="!h-6 !w-6 !p-0"
            @click="toggleProp('in_list')"
          >
            <span class="icon-[lucide--table] size-3" />
          </Button>
        </Tooltip>

        <Tooltip :title="$t(`${T}.field.inForm`)">
          <Button
            size="small"
            :type="field.in_form ? 'primary' : 'text'"
            class="!h-6 !w-6 !p-0"
            @click="toggleProp('in_form')"
          >
            <span class="icon-[lucide--square-pen] size-3" />
          </Button>
        </Tooltip>

        <div class="bg-border mx-0.5 h-4 w-px" />

        <!-- Expand/Collapse -->
        <Tooltip :title="$t(`${T}.field.detail`)">
          <Button
            size="small"
            type="text"
            class="!h-6 !w-6 !p-0"
            @click="emit('toggleExpand')"
          >
            <span
              :class="expanded ? 'icon-[lucide--chevron-up]' : 'icon-[lucide--settings]'"
              class="size-3"
            />
          </Button>
        </Tooltip>

        <!-- Delete -->
        <Tooltip :title="$t(`${T}.field.delete`)">
          <Button
            size="small"
            type="text"
            danger
            class="!h-6 !w-6 !p-0"
            @click="emit('remove')"
          >
            <span class="icon-[lucide--x] size-3" />
          </Button>
        </Tooltip>
      </div>
    </div>

    <!-- Row 2: Labels -->
    <div class="flex items-center gap-2 border-t px-3 py-1.5">
      <span class="text-muted-foreground shrink-0 text-xs">
        {{ $t(`${T}.field.labelZh`) }}:
      </span>
      <Input
        :value="field.label_zh"
        :placeholder="$t(`${T}.field.labelZhPlaceholder`)"
        size="small"
        class="flex-1 text-xs"
        @update:value="(v: string) => update('label_zh', v)"
      />
      <span class="text-muted-foreground shrink-0 text-xs">
        {{ $t(`${T}.field.labelEn`) }}:
      </span>
      <Input
        :value="field.label_en"
        :placeholder="$t(`${T}.field.labelEnPlaceholder`)"
        size="small"
        class="flex-1 text-xs"
        @update:value="(v: string) => update('label_en', v)"
      />
    </div>

    <!-- Expanded area (slot for FieldCardExpanded) -->
    <slot v-if="expanded" name="expanded" />
  </div>
</template>

<style scoped>
.field-card :deep(.ant-input) {
  font-size: 12px;
}
.field-card :deep(.ant-select-selection-item) {
  font-size: 12px;
}
</style>
