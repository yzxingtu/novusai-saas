<script lang="ts" setup>
import type { MonitoringScope } from '../api';

import MonitoringConversationsPageShell from './MonitoringConversationsPageShell.vue';

defineOptions({ name: 'MonitoringConversationsPage' });

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
  <MonitoringConversationsPageShell v-bind="$props" />
</template>
