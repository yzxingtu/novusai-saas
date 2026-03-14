<script lang="ts" setup>
import { Tooltip } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';

defineProps<{
  icon: string;
  title: string;
  active?: boolean;
  disabled?: boolean;
}>();

defineEmits<{
  click: [];
}>();
</script>

<template>
  <Tooltip :title="title">
    <button
      class="rte-tbtn"
      :class="{ active }"
      :disabled="disabled"
      @click="$emit('click')"
    >
      <IconifyIcon :icon="icon" class="size-4" />
    </button>
  </Tooltip>
</template>
