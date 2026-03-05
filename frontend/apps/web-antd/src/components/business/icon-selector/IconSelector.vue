<script lang="ts" setup>
/**
 * 图标选择器表单组件
 *
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
