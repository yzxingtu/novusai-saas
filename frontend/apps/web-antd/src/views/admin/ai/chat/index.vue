<script lang="ts" setup>
/**
 * Admin AI Chat Page
 *
 * Uses the shared AIChatPanel component in 'page' mode.
 * Provides full-page layout with agent sidebar, conversation history, and chat area.
 */
defineOptions({ name: 'AdminAIChat' });

import { Page } from '@vben/common-ui';

import { AIChatPanel } from '#/components/business/ai-chat-panel';
import { getAdminSelectableKBApi } from '#/api/admin/knowledge-bases';
import { $t } from '#/locales';
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
    />
  </Page>
</template>
