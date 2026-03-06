<script lang="ts" setup>
import { onUnmounted } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';

import { Page } from '@vben/common-ui';

import { $t } from '#/locales';

import Models from '../models/index.vue';

defineOptions({ name: 'TenantAIConfig' });

const cleanupPageContext = registerPageContext('tenant/ai/config', () => ({
  page_key: 'tenant.ai.config',
  page_title: $t('tenant.ai.config.name'),
  page_data: {
    resource: '/tenant/ai/config',
  },
}));

onUnmounted(cleanupPageContext);
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <Models />
  </Page>
</template>
