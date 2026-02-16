<script lang="ts" setup>
/**
 * 租户端智能体对话页面
 *
 * Uses the shared AIChatPanel component in 'page' mode.
 * Welcome message and suggested questions are now handled internally
 * by AIChatPanel from the agent list data.
 */
defineOptions({ name: 'TenantAIChat' });

import { Page } from '@vben/common-ui';

import { AIChatPanel } from '#/components/business/ai-chat-panel';
import { getTenantSelectableKBApi } from '#/api/tenant/knowledge-bases';
import { $t } from '#/locales';
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
    />
  </Page>
</template>
