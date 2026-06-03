<script lang="ts" setup>
import MonitoringCallLogsPage from '#/features/ai-monitoring/pages/MonitoringCallLogsPage.vue';
import { $t } from '#/locales';

defineOptions({ name: 'AICallLogList' });
</script>

<template>
  <MonitoringCallLogsPage
    i18n-prefix="admin.ai.callLog"
    permission-resource="ai_call_log"
    resource="/admin/ai/call-logs"
    scope="admin"
    :show-tenant-column="true"
    :title="$t('admin.ai.callLog.title')"
  />
</template>
