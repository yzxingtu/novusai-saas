<script lang="ts" setup>
/**
 * Icon Selector Form Component
 * 图标选择器表单组件
 *
 * Custom component for VbenForm, wraps IconPicker with v-model:value
 * 用于 VbenForm 的自定义组件，封装 IconPicker 提供 v-model:value
 */
import { IconPicker } from '#/components/business/icon-picker';

defineOptions({ name: 'IconSelector' });

defineProps<{
  placeholder?: string;
  value?: string;
}>();

defineEmits<{
  'update:value': [value: string];
}>();
</script>

<template>
  <IconPicker
    :value="value"
    :placeholder="placeholder"
    @update:value="$emit('update:value', $event)"
  />
</template>
