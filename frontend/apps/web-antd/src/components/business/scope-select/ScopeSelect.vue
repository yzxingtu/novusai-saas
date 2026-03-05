<script setup lang="ts">
/**
 * ScopeSelect — 统一作用域下拉选择组件
 *
 * 替代各模块分散的 scope 下拉框硬编码。
 * 通过 allowedScopes prop 控制可选范围。
 */
import { computed } from 'vue';

import { Select } from 'ant-design-vue';

import { getScopeOptions } from '#/utils/scope-helpers';

const props = withDefaults(
  defineProps<{
    allowClear?: boolean;
    allowedScopes?: string[];
    disabled?: boolean;
    modelValue?: string;
    placeholder?: string;
    size?: 'large' | 'middle' | 'small';
  }>(),
  {
    modelValue: undefined,
    allowedScopes: undefined,
    disabled: false,
    placeholder: undefined,
    size: 'middle',
    allowClear: false,
  },
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const options = computed(() => getScopeOptions(props.allowedScopes));

function handleChange(value: unknown) {
  emit('update:modelValue', String(value ?? ''));
}
</script>

<template>
  <Select
    :value="modelValue"
    :options="options"
    :disabled="disabled"
    :placeholder="placeholder"
    :size="size"
    :allow-clear="allowClear"
    @change="handleChange"
  />
</template>
