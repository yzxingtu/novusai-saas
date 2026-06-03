<script lang="ts" setup>
import type { QuotaPageTab } from '../composables/use-ai-quota-page';

import type {
  AIQuotaDiagnosticInfo,
  AIRateLimitDiagnosticInfo,
  AIRateLimitInfo,
} from '#/api/admin/ai-quotas';

import QuotaPageContentShell from './QuotaPageContentShell.vue';

defineOptions({ name: 'AIQuotaPageContent' });

defineProps<{
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
</script>

<template>
  <QuotaPageContentShell v-bind="$props" />
</template>
