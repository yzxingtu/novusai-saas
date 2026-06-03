<script lang="ts" setup>
import type { QuotaPageTab } from '../composables/use-ai-quota-page';

import type {
  AIQuotaDiagnosticInfo,
  AIRateLimitDiagnosticInfo,
  AIRateLimitInfo,
} from '#/api/admin/ai-quotas';

import { TabPane, Tabs } from 'ant-design-vue';

import { $t } from '#/locales';

import QuotaPageQuotaPanel from './QuotaPageQuotaPanel.vue';
import QuotaPageRateLimitPanel from './QuotaPageRateLimitPanel.vue';

defineOptions({ name: 'AIQuotaPageContent' });

const props = defineProps<{
  activeTab: QuotaPageTab;
  onQuotaDelete: (item: AIQuotaDiagnosticInfo) => Promise<void>;
  onQuotaEdit: (item: AIQuotaDiagnosticInfo) => void;
  onQuotaPageChange: (page: number) => void;
  onRateLimitDelete: (item: AIRateLimitDiagnosticInfo) => Promise<void>;
  onRateLimitEdit: (item: AIRateLimitInfo) => void;
  onRateLimitPageChange: (page: number) => void;
  onTabChange: (tab: string) => void;
  quotaLoading: boolean;
  quotaPage: number;
  quotaPageSize: number;
  quotas: AIQuotaDiagnosticInfo[];
  quotaTotal: number;
  rateLimitLoading: boolean;
  rateLimitPage: number;
  rateLimitPageSize: number;
  rateLimits: AIRateLimitDiagnosticInfo[];
  rateLimitTotal: number;
}>();

function handleTabChange(tab: number | string) {
  props.onTabChange(String(tab));
}
</script>

<template>
  <Tabs :active-key="activeTab" @change="handleTabChange">
    <TabPane key="quotas" :tab="$t('admin.ai.quota.title')">
      <QuotaPageQuotaPanel
        :on-quota-delete="onQuotaDelete"
        :on-quota-edit="onQuotaEdit"
        :on-quota-page-change="onQuotaPageChange"
        :quota-loading="quotaLoading"
        :quota-page="quotaPage"
        :quota-page-size="quotaPageSize"
        :quota-total="quotaTotal"
        :quotas="quotas"
      />
    </TabPane>

    <TabPane key="rateLimits" :tab="$t('admin.ai.rateLimit.title')">
      <QuotaPageRateLimitPanel
        :on-rate-limit-delete="onRateLimitDelete"
        :on-rate-limit-edit="onRateLimitEdit"
        :on-rate-limit-page-change="onRateLimitPageChange"
        :rate-limit-loading="rateLimitLoading"
        :rate-limit-page="rateLimitPage"
        :rate-limit-page-size="rateLimitPageSize"
        :rate-limit-total="rateLimitTotal"
        :rate-limits="rateLimits"
      />
    </TabPane>
  </Tabs>
</template>
