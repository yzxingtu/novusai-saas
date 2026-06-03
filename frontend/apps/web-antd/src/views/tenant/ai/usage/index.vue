<script lang="ts" setup>
import MonitoringUsagePage from '#/features/ai-monitoring/pages/MonitoringUsagePage.vue';
import { $t } from '#/locales';

defineOptions({ name: 'TenantAIUsage' });
</script>

<template>
  <MonitoringUsagePage
    i18n-prefix="tenant.ai.usage"
    scope="tenant"
    :title="$t('tenant.ai.usage.title')"
  />
</template>
