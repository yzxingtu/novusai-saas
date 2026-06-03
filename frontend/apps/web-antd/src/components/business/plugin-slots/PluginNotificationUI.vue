<script setup lang="ts">
import { computed } from 'vue';

import { usePluginSlotsStore } from '#/stores/plugin-slots';

const props = defineProps<{
  /** Notification data, passed to plugin component / 通知数据 */
  data?: Record<string, unknown>;
  /** Notification event name (corresponds to manifest notification_ui[].event) / 通知事件名 */
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
