<script lang="ts" setup>
import MonitoringConversationsPage from '#/features/ai-monitoring/pages/MonitoringConversationsPage.vue';
import { $t } from '#/locales';

defineOptions({ name: 'TenantConversationList' });
</script>

<template>
  <MonitoringConversationsPage
    i18n-prefix="tenant.ai.conversation"
    permission-resource="agent_conversation"
    resource="/tenant/ai/conversations"
    scope="tenant"
    :title="$t('tenant.ai.conversation.name')"
  />
</template>
