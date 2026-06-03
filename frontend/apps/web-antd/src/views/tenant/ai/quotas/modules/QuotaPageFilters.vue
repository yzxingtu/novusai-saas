<script lang="ts" setup>
import type {
  QuotaPageTab,
  SelectOption,
  SharedFilters,
} from '../composables/use-ai-quota-page';

import { Select } from 'ant-design-vue';

import {
  getActiveStateOptions,
  getPeriodOptions,
  getQuotaTypeOptions,
} from '../data';

defineOptions({ name: 'TenantAIQuotaPageFilters' });

defineProps<{
  activeTab: QuotaPageTab;
  modelOptions: SelectOption[];
  onActiveFilterChange: (value: unknown) => void;
  onModelFilterChange: (value: unknown) => void;
  onQuotaPeriodChange: (value: unknown) => void;
  onQuotaTypeChange: (value: unknown) => void;
  quotaPeriod?: string;
  quotaType?: string;
  sharedFilters: SharedFilters;
}>();
</script>

<template>
  <div class="mb-4 flex flex-wrap items-center gap-2">
    <Select
      allow-clear
      class="w-44"
      :options="modelOptions"
      :placeholder="$t('tenant.ai.quota.placeholder.allModels')"
      :value="sharedFilters.model_id"
      @change="onModelFilterChange"
    />
    <Select
      allow-clear
      class="w-36"
      :options="getActiveStateOptions()"
      :placeholder="$t('tenant.ai.quota.placeholder.allStatus')"
      :value="sharedFilters.is_active"
      @change="onActiveFilterChange"
    />
    <template v-if="activeTab === 'quotas'">
      <Select
        allow-clear
        class="w-36"
        :options="getPeriodOptions()"
        :placeholder="$t('tenant.ai.quota.placeholder.allPeriods')"
        :value="quotaPeriod"
        @change="onQuotaPeriodChange"
      />
      <Select
        allow-clear
        class="w-36"
        :options="getQuotaTypeOptions()"
        :placeholder="$t('tenant.ai.quota.placeholder.allTypes')"
        :value="quotaType"
        @change="onQuotaTypeChange"
      />
    </template>
  </div>
</template>
