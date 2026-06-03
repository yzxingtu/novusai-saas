<script lang="ts" setup>
import MonitoringUsagePage from '#/features/ai-monitoring/pages/MonitoringUsagePage.vue';
import { $t } from '#/locales';

defineOptions({ name: 'AdminAIUsage' });
</script>

<template>
  <MonitoringUsagePage
    i18n-prefix="admin.ai.usage"
    scope="admin"
    :show-top-tenants="true"
    :title="$t('admin.ai.usage.title')"
  />
</template>
