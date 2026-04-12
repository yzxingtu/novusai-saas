<script lang="ts" setup>
import type { MonitoringScope } from '../api';

import MonitoringUsagePageShell from './MonitoringUsagePageShell.vue';

defineOptions({ name: 'MonitoringUsagePage' });

const props = defineProps<{
  i18nPrefix: string;
  scope: MonitoringScope;
  showTopTenants?: boolean;
  title: string;
}>();
</script>

<template>
  <MonitoringUsagePageShell v-bind="props" />
</template>
