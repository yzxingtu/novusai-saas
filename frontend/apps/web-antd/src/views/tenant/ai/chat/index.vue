<script lang="ts" setup>
/**
 * 租户端智能体对话页面
 *
 * Uses the shared AIChatPanel component in 'page' mode.
 * Loads agent detail on selection to provide welcome_message and suggested_questions.
 */
import type { AgentInfo } from '#/api/tenant/agents';

defineOptions({ name: 'TenantAIChat' });

import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';

import { AIChatPanel } from '#/components/business/ai-chat-panel';
import { getAgentDetailApi } from '#/api/tenant/agents';
import { getTenantSelectableKBApi } from '#/api/tenant/knowledge-bases';
import { $t } from '#/locales';

const agentDetail = ref<AgentInfo | null>(null);

async function onAgentChange(agentId: number) {
  try {
    agentDetail.value = await getAgentDetailApi(agentId);
  } catch {
    agentDetail.value = null;
  }
}

const welcomeMessage = computed(() => agentDetail.value?.welcome_message || '');

const suggestedQuestions = computed<string[]>(() => {
  const raw = agentDetail.value?.suggested_questions;
  if (!Array.isArray(raw)) return [];
  return raw.filter((q): q is string => typeof q === 'string' && q.trim() !== '');
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('tenant.ai.chat.pageDesc')"
    content-class="h-full"
  >
    <AIChatPanel
      mode="page"
      api-prefix="/tenant"
      upload-url="/tenant/attachments/upload"
      :show-kb-selector="true"
      :show-attachments="true"
      :fetch-kb-api="getTenantSelectableKBApi"
      :welcome-message="welcomeMessage"
      :suggested-questions="suggestedQuestions"
      @agent-change="onAgentChange"
    />
  </Page>
</template>
