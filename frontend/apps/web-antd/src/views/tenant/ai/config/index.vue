<script lang="ts" setup>
import { Page } from '@vben/common-ui';

import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import { $t } from '#/locales';

import Models from '../models/index.vue';

defineOptions({ name: 'TenantAIConfig' });

const heroChips = [
  {
    key: 'focus',
    icon: 'lucide:brain-circuit',
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
    text: `${$t('tenant.ai.model.type')} / ${$t('tenant.ai.model.contextWindow')} / ${$t('tenant.ai.model.inputPrice')}`,
  },
  {
    key: 'capability',
    icon: 'lucide:sparkles',
    className: 'bg-background/90 text-foreground',
    text: `${$t('tenant.ai.model.capability.functionCalling')} / ${$t('tenant.ai.model.capability.vision')} / ${$t('tenant.ai.model.capability.streaming')}`,
  },
];
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AIPageHeroCard
      :chips="heroChips"
      :description="$t('tenant.ai.model.pageDesc')"
      icon="lucide:brain-circuit"
      icon-wrap-class="bg-primary/10 text-primary"
      :title="$t('tenant.ai.model.title')"
    />
    <Models />
  </Page>
</template>
