<script setup lang="ts">
import { computed } from 'vue';

import { usePluginSlotsStore } from '#/stores/plugin-slots';

const props = defineProps<{
  /** 通知数据，传递给插件组件 */
  data?: Record<string, unknown>;
  /** 通知事件名（对应 manifest notification_ui[].event） */
  event: string;
}>();

const slotsStore = usePluginSlotsStore();

const matchingUI = computed(() =>
  slotsStore.notificationUI.find((ui) => ui.event === props.event),
);
</script>

<template>
  <component
    :is="matchingUI.component"
    v-if="matchingUI?.component"
    v-bind="data"
  />
</template>
