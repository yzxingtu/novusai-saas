<script lang="ts" setup>
import { Page } from '@vben/common-ui';

import { Card } from 'ant-design-vue';

import { useAIQuotaPage } from './composables/use-ai-quota-page';
import QuotaPageContent from './modules/QuotaPageContent.vue';
import QuotaPageFilters from './modules/QuotaPageFilters.vue';
import QuotaPageSummary from './modules/QuotaPageSummary.vue';

defineOptions({ name: 'TenantAIQuotas' });

const {
  activeTab,
  displayedQuotas,
  effectiveRateLimitLoading,
  effectiveRateLimitMap,
  heroChips,
  heroMetrics,
  modelOptions,
  pageLoading,
  quotaLoading,
  quotaPeriod,
  quotaType,
  rateLimitLoading,
  rateLimits,
  sharedFilters,
  handleActiveFilterChange,
  handleModelFilterChange,
  handleQuotaPeriodChange,
  handleQuotaTypeChange,
  handleTabChange,
} = useAIQuotaPage();
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <QuotaPageSummary
      :chips="heroChips"
      :loading="pageLoading"
      :metrics="heroMetrics"
    />

    <Card :body-style="{ padding: '20px' }">
      <QuotaPageFilters
        :active-tab="activeTab"
        :model-options="modelOptions"
        :on-active-filter-change="handleActiveFilterChange"
        :on-model-filter-change="handleModelFilterChange"
        :on-quota-period-change="handleQuotaPeriodChange"
        :on-quota-type-change="handleQuotaTypeChange"
        :quota-period="quotaPeriod"
        :quota-type="quotaType"
        :shared-filters="sharedFilters"
      />
      <QuotaPageContent
        :active-tab="activeTab"
        :displayed-quotas="displayedQuotas"
        :effective-rate-limit-loading="effectiveRateLimitLoading"
        :effective-rate-limit-map="effectiveRateLimitMap"
        :on-tab-change="handleTabChange"
        :quota-loading="quotaLoading"
        :rate-limit-loading="rateLimitLoading"
        :rate-limits="rateLimits"
      />
    </Card>
  </Page>
</template>
