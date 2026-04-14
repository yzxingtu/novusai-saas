<script lang="ts" setup>
import type { MonitoringScope } from '../api';

import MonitoringCallLogDrawerShell from './MonitoringCallLogDrawerShell.vue';

defineOptions({ name: 'MonitoringCallLogDrawer' });

const props = defineProps<{
  i18nPrefix: string;
  logId: null | number;
  open: boolean;
  scope: MonitoringScope;
}>();

const emit = defineEmits<{ 'update:open': [value: boolean] }>();

const forwardListeners = {
  'update:open': (value: boolean) => emit('update:open', value),
};
</script>

<template>
  <MonitoringCallLogDrawerShell v-bind="props" v-on="forwardListeners" />
</template>
