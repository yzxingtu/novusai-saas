<script lang="ts" setup>
/**
 * InputVariablesEditor — Input Variables Visual Editor
 * 输入变量可视化编辑器
 *
 * Replaces JSON textarea, provides row-by-row visual editing for agent input_variables.
 * 替代 JSON textarea，为智能体 input_variables 提供逐行可视化编辑体验。
 * Non-technical user friendly: name/label/type/required/default each with independent input.
 * 非技术人员友好：名称/标签/类型/必填/默认值每项独立输入。
 */
import type { InputVariable } from '#/types/ai-chat';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Input,
  Select,
  SelectOption,
  Switch,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'InputVariablesEditor' });

const props = defineProps<{
  disabled?: boolean;
  modelValue: InputVariable[] | null | undefined;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: InputVariable[]];
}>();

const vars = computed<InputVariable[]>(() => props.modelValue ?? []);

function update(newVars: InputVariable[]) {
  emit('update:modelValue', newVars);
}

function addVar() {
  update([
    ...vars.value,
    { name: '', label: '', type: 'string', required: false, default: '' },
  ]);
}

function removeVar(idx: number) {
  const next = vars.value.filter((_, i) => i !== idx);
  update(next);
}

function updateField(idx: number, field: keyof InputVariable, value: unknown) {
  const next = vars.value.map((v, i) =>
    i === idx ? { ...v, [field]: value } : v,
  );
  update(next);
}

const typeOptions = [
  { label: $t('shared.common.inputVarsEditor.typeString'), value: 'string' },
  { label: $t('shared.common.inputVarsEditor.typeText'), value: 'text' },
  { label: $t('shared.common.inputVarsEditor.typeNumber'), value: 'number' },
];
</script>

<template>
  <div class="space-y-2">
    <!-- Header labels (hidden on mobile) -->
    <div
      v-if="vars.length > 0"
      class="hidden grid-cols-[1fr_1fr_90px_56px_1fr_32px] gap-2 px-1 md:grid"
    >
      <span class="text-xs text-muted-foreground">{{
        $t('shared.common.inputVarsEditor.colName')
      }}</span>
      <span class="text-xs text-muted-foreground">{{
        $t('shared.common.inputVarsEditor.colLabel')
      }}</span>
      <span class="text-xs text-muted-foreground">{{
        $t('shared.common.inputVarsEditor.colType')
      }}</span>
      <span class="text-center text-xs text-muted-foreground">{{
        $t('shared.common.inputVarsEditor.colRequired')
      }}</span>
      <span class="text-xs text-muted-foreground">{{
        $t('shared.common.inputVarsEditor.colDefault')
      }}</span>
      <span></span>
    </div>

    <!-- Variable rows -->
    <div
      v-for="(v, idx) in vars"
      :key="idx"
      class="grid grid-cols-[1fr_32px] gap-2 rounded-lg border border-border bg-muted/30 p-2 md:grid-cols-[1fr_1fr_90px_56px_1fr_32px] md:items-center md:border-0 md:bg-transparent md:p-0"
    >
      <!-- Variable name (identifier) -->
      <div class="md:hidden">
        <span class="text-xs text-muted-foreground">{{
          $t('shared.common.inputVarsEditor.colName')
        }}</span>
      </div>
      <Input
        :value="v.name"
        :disabled="disabled"
        :placeholder="$t('shared.common.inputVarsEditor.namePlaceholder')"
        class="font-mono text-xs"
        @update:value="updateField(idx, 'name', $event)"
      />

      <!-- Display label -->
      <Input
        :value="v.label"
        :disabled="disabled"
        :placeholder="$t('shared.common.inputVarsEditor.labelPlaceholder')"
        class="text-xs"
        @update:value="updateField(idx, 'label', $event)"
      />

      <!-- Type -->
      <Select
        :value="v.type || 'string'"
        :disabled="disabled"
        class="w-full text-xs"
        size="small"
        @update:value="updateField(idx, 'type', $event)"
      >
        <SelectOption
          v-for="opt in typeOptions"
          :key="opt.value"
          :value="opt.value"
        >
          {{ opt.label }}
        </SelectOption>
      </Select>

      <!-- Required toggle -->
      <div class="flex items-center justify-center">
        <Tooltip :title="$t('shared.common.inputVarsEditor.colRequired')">
          <Switch
            :checked="!!v.required"
            :disabled="disabled"
            size="small"
            @update:checked="updateField(idx, 'required', $event)"
          />
        </Tooltip>
      </div>

      <!-- Default value -->
      <Input
        :value="v.default ?? ''"
        :disabled="disabled"
        :placeholder="$t('shared.common.inputVarsEditor.defaultPlaceholder')"
        class="text-xs"
        allow-clear
        @update:value="updateField(idx, 'default', $event || undefined)"
      />

      <!-- Delete -->
      <div class="flex items-center justify-end">
        <Tooltip :title="$t('common.delete')">
          <button
            :disabled="disabled"
            class="flex size-7 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:cursor-not-allowed disabled:opacity-40"
            @click="removeVar(idx)"
          >
            <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
          </button>
        </Tooltip>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-if="vars.length === 0"
      class="rounded-lg border border-dashed border-border py-4 text-center text-xs text-muted-foreground"
    >
      {{ $t('shared.common.inputVarsEditor.empty') }}
    </div>

    <!-- Add button -->
    <Button
      v-if="!disabled"
      type="dashed"
      size="small"
      class="w-full"
      @click="addVar"
    >
      <template #icon>
        <IconifyIcon icon="lucide:plus" class="size-3.5" />
      </template>
      {{ $t('shared.common.inputVarsEditor.addVar') }}
    </Button>
  </div>
</template>
