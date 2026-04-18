<script lang="ts" setup>
import type { HeroChip, HeroMetric } from '../composables/use-ai-quota-page';

import { Spin } from 'ant-design-vue';

import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';

defineOptions({ name: 'TenantAIQuotaPageSummary' });

defineProps<{
  chips: HeroChip[];
  loading: boolean;
  metrics: HeroMetric[];
}>();
</script>

<template>
  <Spin :spinning="loading">
    <AIPageHeroCard
      :chips="chips"
      :description="$t('tenant.ai.quota.pageDesc')"
      icon="lucide:gauge"
      icon-wrap-class="bg-primary/10 text-primary"
      :metrics="metrics"
      :title="$t('tenant.ai.quota.title')"
    />
  </Spin>
</template>
