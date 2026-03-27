<script lang="ts" setup>
import MonitoringConversationsPage from '#/features/ai-monitoring/pages/MonitoringConversationsPage.vue';
import { $t } from '#/locales';

defineOptions({ name: 'AdminAIConversations' });
</script>

<template>
  <MonitoringConversationsPage
    i18n-prefix="admin.ai.conversation"
    permission-resource="ai_conversation"
    resource="/admin/ai/conversations"
    scope="admin"
    :show-tenant-column="true"
    :title="$t('admin.ai.conversation.title')"
  />
</template>
