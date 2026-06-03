<script lang="ts" setup>
import type { HeroChip, HeroMetric } from '../composables/use-ai-quota-page';

import { Alert, Spin } from 'ant-design-vue';

import AIPageHeroCard from '../../_shared/AIPageHeroCard.vue';

defineOptions({ name: 'AIQuotaPageSummary' });

defineProps<{
  chips: HeroChip[];
  metrics: HeroMetric[];
  summaryLoading: boolean;
}>();
</script>

<template>
  <div class="flex flex-col gap-4">
    <Spin :spinning="summaryLoading">
      <AIPageHeroCard
        :chips="chips"
        :description="$t('admin.ai.quota.pageDesc')"
        icon="lucide:gauge"
        icon-wrap-class="bg-primary/10 text-primary"
        :metrics="metrics"
        :title="$t('admin.ai.quota.title')"
      />
    </Spin>

    <div class="grid grid-cols-1 gap-3 xl:grid-cols-3">
      <Alert
        :message="$t('admin.ai.quota.helper.hardLimit')"
        show-icon
        type="error"
      />
      <Alert
        :message="$t('admin.ai.quota.helper.softLimit')"
        show-icon
        type="warning"
      />
      <Alert
        :message="$t('admin.ai.quota.helper.globalFallback')"
        show-icon
        type="info"
      />
    </div>
  </div>
</template>
