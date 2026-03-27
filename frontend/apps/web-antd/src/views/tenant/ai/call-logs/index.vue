<script lang="ts" setup>
import MonitoringCallLogsPage from '#/features/ai-monitoring/pages/MonitoringCallLogsPage.vue';
import { $t } from '#/locales';

defineOptions({ name: 'TenantAICallLogList' });
</script>

<template>
  <MonitoringCallLogsPage
    i18n-prefix="tenant.ai.callLog"
    permission-resource="ai_tenant_call_log"
    resource="/tenant/ai/call-logs"
    scope="tenant"
    :title="$t('tenant.ai.callLog.title')"
  />
</template>
