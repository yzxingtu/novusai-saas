<script lang="ts" setup>
import type { MonitoringScope } from '../api';

import MonitoringConversationDrawerShell from './MonitoringConversationDrawerShell.vue';

defineOptions({ name: 'MonitoringConversationDrawer' });

const props = defineProps<{
  conversationId: null | number;
  i18nPrefix: string;
  open: boolean;
  scope: MonitoringScope;
}>();

const emit = defineEmits<{ 'update:open': [value: boolean] }>();

const forwardListeners = {
  'update:open': (value: boolean) => emit('update:open', value),
};
</script>

<template>
  <MonitoringConversationDrawerShell
    v-bind="props"
    v-on="forwardListeners"
  />
</template>
