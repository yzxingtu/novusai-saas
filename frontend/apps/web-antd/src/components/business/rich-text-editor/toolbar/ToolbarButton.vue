<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Tooltip } from 'ant-design-vue';

defineProps<{
  active?: boolean;
  disabled?: boolean;
  icon: string;
  title: string;
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
