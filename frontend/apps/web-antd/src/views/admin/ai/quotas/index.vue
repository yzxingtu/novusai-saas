<script lang="ts" setup>
import type { VNodeRef } from 'vue';

import { Page } from '@vben/common-ui';

import { Card } from 'ant-design-vue';

import { useAIQuotaPage } from './composables/use-ai-quota-page';
import type { RateLimitFormExposed } from './composables/use-ai-quota-page';
import QuotaPageContent from './modules/QuotaPageContent.vue';
import QuotaPageFilters from './modules/QuotaPageFilters.vue';
import QuotaPageSummary from './modules/QuotaPageSummary.vue';
import RateLimitForm from './modules/RateLimitForm.vue';

defineOptions({ name: 'AIQuotaDiagnosticsPage' });

const {
  activeTab,
  heroChips,
  heroMetrics,
  modelOptions,
  quotaLoading,
  quotaPage,
  quotaPageSize,
  quotaPeriod,
  quotaTotal,
  quotas,
  QuotaFormDrawer,
  rateLimitFormRef,
  rateLimitLoading,
  rateLimitPage,
  rateLimitPageSize,
  rateLimitTotal,
  rateLimits,
  sharedFilters,
  summaryLoading,
  tenantOptions,
  quotaType,
  editQuota,
  handleActiveFilterChange,
  handleModelFilterChange,
  handleQuotaDelete,
  handleQuotaMutationSuccess,
  handleQuotaPeriodChange,
  handleQuotaTypeChange,
  handleRateLimitDelete,
  handleRateLimitMutationSuccess,
  handleTabChange,
  handleTenantFilterChange,
  openCreate,
  openRateLimitEdit,
  onQuotaPageChange,
  onRateLimitPageChange,
  refreshAll,
} = useAIQuotaPage();

const setRateLimitFormRef: VNodeRef = (value) => {
  rateLimitFormRef.value = value as unknown as RateLimitFormExposed | undefined;
};
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <QuotaFormDrawer @success="handleQuotaMutationSuccess" />
    <RateLimitForm
      :ref="setRateLimitFormRef"
      @success="handleRateLimitMutationSuccess"
    />

    <QuotaPageSummary
      :chips="heroChips"
      :metrics="heroMetrics"
      :summary-loading="summaryLoading"
    />

    <Card :body-style="{ padding: '20px' }">
      <QuotaPageFilters
        :active-tab="activeTab"
        :model-options="modelOptions"
        :on-active-filter-change="handleActiveFilterChange"
        :on-create="openCreate"
        :on-model-filter-change="handleModelFilterChange"
        :on-quota-period-change="handleQuotaPeriodChange"
        :on-quota-type-change="handleQuotaTypeChange"
        :on-refresh="refreshAll"
        :on-tenant-filter-change="handleTenantFilterChange"
        :quota-period="quotaPeriod"
        :quota-type="quotaType"
        :shared-filters="sharedFilters"
        :tenant-options="tenantOptions"
      />
      <QuotaPageContent
        :active-tab="activeTab"
        :on-quota-delete="handleQuotaDelete"
        :on-quota-edit="editQuota"
        :on-quota-page-change="onQuotaPageChange"
        :on-rate-limit-delete="handleRateLimitDelete"
        :on-rate-limit-edit="openRateLimitEdit"
        :on-rate-limit-page-change="onRateLimitPageChange"
        :on-tab-change="handleTabChange"
        :quota-loading="quotaLoading"
        :quota-page="quotaPage"
        :quota-page-size="quotaPageSize"
        :quota-total="quotaTotal"
        :quotas="quotas"
        :rate-limit-loading="rateLimitLoading"
        :rate-limit-page="rateLimitPage"
        :rate-limit-page-size="rateLimitPageSize"
        :rate-limit-total="rateLimitTotal"
        :rate-limits="rateLimits"
      />
    </Card>
  </Page>
</template>
