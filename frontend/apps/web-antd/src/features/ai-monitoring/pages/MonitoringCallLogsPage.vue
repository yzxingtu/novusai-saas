<script lang="ts" setup>
import type { MonitoringScope } from '../api';

import MonitoringCallLogsPageShell from './MonitoringCallLogsPageShell.vue';

defineOptions({ name: 'MonitoringCallLogsPage' });

defineProps<{
  i18nPrefix: string;
  permissionResource: string;
  resource: string;
  scope: MonitoringScope;
  showTenantColumn?: boolean;
  title: string;
}>();
</script>

<template>
  <MonitoringCallLogsPageShell v-bind="$props" />
</template>
