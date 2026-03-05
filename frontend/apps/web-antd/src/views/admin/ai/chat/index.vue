<script lang="ts" setup>
/**
 * Admin AI Chat Page
 *
 * Uses the shared AIChatPanel component in 'page' mode.
 * Persists selected agent and conversation in URL query params
 * so that page refresh restores the previous state.
 *
 * NOTE: Uses history.replaceState instead of router.replace to avoid
 * Vue Router key change (getTabKey uses fullPath) which would destroy
 * and recreate the component on every query param update.
 */
import { Page } from '@vben/common-ui';

import { getAdminSelectableKBApi } from '#/api/admin/knowledge-bases';
import { AIChatPanel } from '#/components/business/ai-chat-panel';
import { $t } from '#/locales';

defineOptions({ name: 'AdminAIChat' });

function _readQuery(): URLSearchParams {
  return new URLSearchParams(window.location.search);
}

function _updateQuery(key: string, value: null | string) {
  const params = _readQuery();
  if (value) {
    params.set(key, value);
  } else {
    params.delete(key);
  }
  const qs = params.toString();
  const newUrl = `${window.location.pathname}${qs ? `?${qs}` : ''}`;
  window.history.replaceState(window.history.state, '', newUrl);
}

const initParams = _readQuery();
const initialAgentId = initParams.has('agent')
  ? Number(initParams.get('agent'))
  : undefined;
const initialConversationId = initParams.has('conv')
  ? Number(initParams.get('conv'))
  : undefined;

function onAgentChange(agentId: number) {
  _updateQuery('agent', String(agentId));
  _updateQuery('conv', null);
}

function onConversationChange(conversationId: null | number) {
  _updateQuery('conv', conversationId ? String(conversationId) : null);
}
</script>

<template>
  <Page
    auto-content-height
    :description="$t('common.globalAiChat.pageDesc')"
    content-class="h-full"
  >
    <AIChatPanel
      mode="page"
      api-prefix="/admin"
      upload-url="/admin/attachments/upload"
      :show-kb-selector="true"
      :show-attachments="true"
      :fetch-kb-api="getAdminSelectableKBApi"
      :initial-agent-id="initialAgentId"
      :initial-conversation-id="initialConversationId"
      @agent-change="onAgentChange"
      @conversation-change="onConversationChange"
    />
  </Page>
</template>
