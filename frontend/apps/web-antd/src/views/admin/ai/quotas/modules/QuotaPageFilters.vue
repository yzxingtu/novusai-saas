<script lang="ts" setup>
import type {
  QuotaPageTab,
  SelectOption,
  SharedFilters,
} from '../composables/use-ai-quota-page';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Select } from 'ant-design-vue';

import { $t } from '#/locales';

import {
  getActiveStateOptions,
  getPeriodOptions,
  getQuotaTypeOptions,
} from '../data';

defineOptions({ name: 'AIQuotaPageFilters' });

const props = defineProps<{
  activeTab: QuotaPageTab;
  modelOptions: SelectOption[];
  onActiveFilterChange: (value: unknown) => void;
  onCreate: () => void;
  onModelFilterChange: (value: unknown) => void;
  onQuotaPeriodChange: (value: unknown) => void;
  onQuotaTypeChange: (value: unknown) => void;
  onRefresh: () => Promise<void>;
  onTenantFilterChange: (value: unknown) => void;
  quotaPeriod?: string;
  quotaType?: string;
  sharedFilters: SharedFilters;
  tenantOptions: SelectOption[];
}>();

const createButtonLabel = computed(() =>
  props.activeTab === 'quotas'
    ? $t('admin.ai.quota.create')
    : $t('admin.ai.rateLimit.create'),
);

const createPermission = computed(() =>
  props.activeTab === 'quotas'
    ? ['ai_quota:create']
    : ['ai_quota:create_rate_limit'],
);
</script>

<template>
  <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-2">
      <Select
        allow-clear
        class="w-44"
        :options="tenantOptions"
        :placeholder="$t('admin.ai.quota.placeholder.allTenants')"
        :value="sharedFilters.tenant_id"
        @change="onTenantFilterChange"
      />
      <Select
        allow-clear
        class="w-44"
        :options="modelOptions"
        :placeholder="$t('admin.ai.usage.placeholder.selectModel')"
        :value="sharedFilters.model_id"
        @change="onModelFilterChange"
      />
      <Select
        allow-clear
        class="w-36"
        :options="getActiveStateOptions()"
        :placeholder="$t('admin.ai.quota.placeholder.allStatus')"
        :value="sharedFilters.is_active"
        @change="onActiveFilterChange"
      />
      <template v-if="activeTab === 'quotas'">
        <Select
          allow-clear
          class="w-36"
          :options="getPeriodOptions()"
          :placeholder="$t('admin.ai.quota.placeholder.allPeriods')"
          :value="quotaPeriod"
          @change="onQuotaPeriodChange"
        />
        <Select
          allow-clear
          class="w-36"
          :options="getQuotaTypeOptions()"
          :placeholder="$t('admin.ai.quota.placeholder.allTypes')"
          :value="quotaType"
          @change="onQuotaTypeChange"
        />
      </template>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <Button @click="onRefresh">
        <template #icon>
          <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
        </template>
        {{ $t('admin.ai.quota.refresh') }}
      </Button>
      <Button v-access:code="createPermission" type="primary" @click="onCreate">
        {{ createButtonLabel }}
      </Button>
    </div>
  </div>
</template>
