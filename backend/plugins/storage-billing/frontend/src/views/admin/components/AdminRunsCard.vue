<script lang="ts" setup>
import type {
  ReconciliationChargeRow,
  ReconciliationProviderPlan,
  ReconciliationRequestedScope,
  ReconciliationRun,
  ReconciliationRunDetailResponse,
  ReconciliationSourceRecord,
} from '../../../types';

type ChargeFilterBadge = {
  key: string;
  label: string;
  value: string;
};

type AllocationAudit = {
  ambiguous_item_samples: unknown[];
  unmatched_item_samples: unknown[];
};

type AllocationSummary = {
  ambiguous_items: number;
  matched_items: number;
  unmatched_items: number;
  written_charge_rows: number;
};

type ProviderSummary = {
  charge_item_count?: number;
  matched_items?: number;
  provider_code: string;
  source_status: string;
  written_charge_rows?: number;
};

const props = defineProps<{
  applyRunChargeFilters: () => void;
  auditedSources: ReconciliationSourceRecord[];
  canViewAdmin: boolean;
  capabilityTargetRuleLabel: (rule: string | undefined) => string;
  chargeBasisLabel: (basis: string | undefined) => string;
  chargeColumns: Array<{ key: string; title: string }>;
  exportCurrentRunCharges: () => void;
  formatBytes: (value: null | number | undefined) => string;
  formatTimestamp: (value: null | string | undefined) => string;
  loadRunDetail: (runId: number) => void;
  prettyStatus: (status: string) => string;
  providerLabelFromAny: (providerCode: string) => string;
  resetRunChargeFilters: () => void;
  runChargeActiveFilters: ChargeFilterBadge[];
  runChargeExporting: boolean;
  runChargeFilters: {
    provider_code: string;
    source_id: null | number;
    tenant_id: string;
  };
  runChargeLoading: boolean;
  runChargeProviderOptions: Array<{ label: string; value: string }>;
  runChargeSourceOptions: Array<{ label: string; value: number }>;
  runColumns: Array<{ key: string; title: string }>;
  runDetailLoading: boolean;
  runs: ReconciliationRun[];
  scopeProviderCodes: (scope: ReconciliationRequestedScope) => string[];
  scopeProviderPlans: (scope: ReconciliationRequestedScope) => ReconciliationProviderPlan[];
  selectedRun: null | ReconciliationRun;
  selectedRunChargeResponse: null | {
    source_total?: number;
    total?: number;
  };
  selectedRunCharges: ReconciliationChargeRow[];
  selectedRunDetail: null | ReconciliationRunDetailResponse;
  selectedRunProviderResults: ProviderSummary[];
  selectedRunScopePayload: (run: ReconciliationRun) => string;
  selectedRunScopeSummary: (run: ReconciliationRun) => string;
  sourceAllocationAudit: (source: ReconciliationSourceRecord) => AllocationAudit;
  sourceAllocationSummary: (source: ReconciliationSourceRecord) => AllocationSummary;
  sourceColumns: Array<{ key: string; title: string }>;
  sourceLabelFromCharge: (row: ReconciliationChargeRow) => string;
  statusColor: (status: string) => string;
  runProviderSummaries: (run: ReconciliationRun) => ProviderSummary[];
  runRequestedScope: (run: ReconciliationRun) => ReconciliationRequestedScope;
}>();
</script>

<template>
  <Card :title="$t('plugin.storage-billing.admin.runs.title')" class="block">
    <div class="section-subtitle">{{ $t('plugin.storage-billing.admin.runs.subtitle') }}</div>
    <Table
      :columns="props.runColumns"
      :data-source="props.runs"
      :locale="{ emptyText: $t('plugin.storage-billing.admin.runs.empty') }"
      :pagination="false"
      row-key="id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'billing_date'">{{ record.period_label || record.billing_date }}</template>
        <template v-else-if="column.key === 'status'">
          <Tag :color="props.statusColor(record.status)">{{ props.prettyStatus(record.status) }}</Tag>
        </template>
        <template v-else-if="column.key === 'trigger_type'">{{ record.trigger_type }}</template>
        <template v-else-if="column.key === 'providers'">
          <Space wrap>
            <Tag
              v-for="provider in props.runProviderSummaries(record)"
              :key="`${record.id}-${provider.provider_code}`"
              :color="props.statusColor(provider.source_status)"
            >
              {{ props.providerLabelFromAny(provider.provider_code) }} · {{ provider.matched_items ?? 0 }}/{{ provider.charge_item_count ?? 0 }}
            </Tag>
          </Space>
        </template>
        <template v-else-if="column.key === 'finished_at'">{{ props.formatTimestamp(record.completed_at) }}</template>
        <template v-else-if="column.key === 'actions'">
          <Button v-if="props.canViewAdmin" size="small" @click="props.loadRunDetail(record.id)">
            {{ $t('plugin.storage-billing.admin.runs.view') }}
          </Button>
        </template>
      </template>
    </Table>
    <div v-if="!props.runs.length" class="empty"><Empty :description="$t('plugin.storage-billing.admin.runs.empty')" /></div>

    <Card v-if="props.selectedRun" class="run-detail" size="small">
      <template #title>{{ $t('plugin.storage-billing.admin.runs.detailTitle') }} · {{ props.selectedRun.period_label || props.selectedRun.billing_date }}</template>
      <template #extra>
        <Button
          v-if="props.canViewAdmin"
          :loading="props.runChargeExporting"
          size="small"
          @click="props.exportCurrentRunCharges"
        >
          {{ $t('plugin.storage-billing.admin.runs.charges.export') }}
        </Button>
      </template>
      <Spin :spinning="props.runDetailLoading">
        <Descriptions :column="3" size="small">
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.runs.detail.status')">
            <Tag :color="props.statusColor(props.selectedRun.status)">{{ props.prettyStatus(props.selectedRun.status) }}</Tag>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.runs.detail.trigger')">{{ props.selectedRun.trigger_type }}</Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.runs.detail.statementCount')">{{ props.selectedRun.summary.statement_count ?? 0 }}</Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.runs.detail.requestedScope')" :span="3">
            <div class="run-scope-summary">{{ props.selectedRunScopeSummary(props.selectedRun) }}</div>
            <Space v-if="props.scopeProviderCodes(props.runRequestedScope(props.selectedRun)).length" wrap class="run-scope-tags">
              <Tag
                v-for="providerCode in props.scopeProviderCodes(props.runRequestedScope(props.selectedRun))"
                :key="`scope-provider-${providerCode}`"
                color="blue"
              >
                {{ props.providerLabelFromAny(providerCode) }}
              </Tag>
            </Space>
            <div v-if="props.scopeProviderPlans(props.runRequestedScope(props.selectedRun)).length" class="run-plan-list">
              <div
                v-for="plan in props.scopeProviderPlans(props.runRequestedScope(props.selectedRun))"
                :key="`plan-${plan.provider_code}-${plan.billing_date}`"
                class="run-plan-card"
              >
                <Space wrap>
                  <Tag color="blue">{{ props.providerLabelFromAny(plan.provider_code) }}</Tag>
                  <Tag color="processing">{{ plan.billing_date }}</Tag>
                  <Tag>{{ props.capabilityTargetRuleLabel(plan.official_target_rule) }}</Tag>
                  <Tag>{{ $t('plugin.storage-billing.admin.runs.detail.lagDays') }} {{ plan.official_billing_lag_days ?? '-' }}</Tag>
                </Space>
              </div>
            </div>
            <details class="run-scope-details">
              <summary>{{ $t('plugin.storage-billing.admin.runs.detail.scopeToggle') }}</summary>
              <pre>{{ props.selectedRunScopePayload(props.selectedRun) }}</pre>
            </details>
          </Descriptions.Item>
        </Descriptions>

        <div v-if="props.selectedRunProviderResults.length" class="run-provider-results">
          <div
            v-for="provider in props.selectedRunProviderResults"
            :key="`provider-result-${provider.provider_code}`"
            class="run-provider-card"
          >
            <Space wrap>
              <Tag :color="props.statusColor(provider.source_status)">
                {{ props.providerLabelFromAny(provider.provider_code) }}
              </Tag>
              <Tag>{{ props.prettyStatus(provider.source_status) }}</Tag>
              <Tag>{{ $t('plugin.storage-billing.admin.runs.audit.matched') }} {{ provider.matched_items ?? 0 }}</Tag>
              <Tag>{{ $t('plugin.storage-billing.admin.runs.detail.chargeItems') }} {{ provider.charge_item_count ?? 0 }}</Tag>
              <Tag>{{ $t('plugin.storage-billing.admin.runs.detail.writtenRows') }} {{ provider.written_charge_rows ?? 0 }}</Tag>
            </Space>
          </div>
        </div>

        <Table
          :columns="props.sourceColumns"
          :data-source="props.selectedRunDetail?.sources ?? []"
          :locale="{ emptyText: $t('plugin.storage-billing.admin.runs.sources.empty') }"
          :pagination="false"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'provider'">
              <Space direction="vertical" size="small">
                <span>{{ props.providerLabelFromAny(record.provider_code) }}</span>
                <span class="muted">{{ record.source_ref || record.source_key }}</span>
              </Space>
            </template>
            <template v-else-if="column.key === 'status'">
              <Tag :color="props.statusColor(record.source_status)">{{ props.prettyStatus(record.source_status) }}</Tag>
            </template>
            <template v-else-if="column.key === 'amount'">{{ record.amount_total }} {{ record.currency }}</template>
            <template v-else-if="column.key === 'usage'">{{ props.formatBytes(record.usage_bytes) }}</template>
            <template v-else-if="column.key === 'allocation'">
              <Space wrap>
                <Tag color="success">{{ $t('plugin.storage-billing.admin.runs.audit.matched') }} {{ props.sourceAllocationSummary(record).matched_items }}</Tag>
                <Tag color="warning">{{ $t('plugin.storage-billing.admin.runs.audit.unmatched') }} {{ props.sourceAllocationSummary(record).unmatched_items }}</Tag>
                <Tag color="error">{{ $t('plugin.storage-billing.admin.runs.audit.ambiguous') }} {{ props.sourceAllocationSummary(record).ambiguous_items }}</Tag>
              </Space>
            </template>
            <template v-else-if="column.key === 'error'">
              <span class="muted">{{ record.error_message || '-' }}</span>
            </template>
          </template>
        </Table>

        <Card class="run-charge-card" size="small">
          <template #title>{{ $t('plugin.storage-billing.admin.runs.charges.title') }}</template>
          <div class="section-subtitle">{{ $t('plugin.storage-billing.admin.runs.charges.subtitle') }}</div>
          <Space wrap class="run-charge-summary">
            <Tag color="blue">{{ $t('plugin.storage-billing.admin.runs.charges.rowTotal') }} {{ props.selectedRunChargeResponse?.total ?? props.selectedRunCharges.length }}</Tag>
            <Tag color="cyan">{{ $t('plugin.storage-billing.admin.runs.charges.sourceTotal') }} {{ props.selectedRunChargeResponse?.source_total ?? (props.selectedRunDetail?.sources?.length ?? 0) }}</Tag>
            <Tag v-if="!props.runChargeActiveFilters.length" color="default">{{ $t('plugin.storage-billing.admin.runs.charges.filterNone') }}</Tag>
            <Tag v-for="filter in props.runChargeActiveFilters" :key="`charge-filter-${filter.key}`" color="processing">
              {{ filter.label }}: {{ filter.value }}
            </Tag>
          </Space>
          <Space wrap class="run-charge-toolbar">
            <Select
              v-model:value="props.runChargeFilters.provider_code"
              allow-clear
              class="toolbar-field"
              :options="props.runChargeProviderOptions"
              :placeholder="$t('plugin.storage-billing.admin.runs.charges.filterProvider')"
            />
            <Select
              v-model:value="props.runChargeFilters.source_id"
              allow-clear
              class="toolbar-field toolbar-source"
              :options="props.runChargeSourceOptions"
              :placeholder="$t('plugin.storage-billing.admin.runs.charges.filterSource')"
            />
            <Input
              v-model:value="props.runChargeFilters.tenant_id"
              class="toolbar-field"
              :placeholder="$t('plugin.storage-billing.admin.runs.charges.filterTenant')"
            />
            <Button @click="props.applyRunChargeFilters">
              {{ $t('plugin.storage-billing.admin.runs.charges.applyFilters') }}
            </Button>
            <Button @click="props.resetRunChargeFilters">
              {{ $t('plugin.storage-billing.admin.runs.charges.resetFilters') }}
            </Button>
          </Space>
          <Spin :spinning="props.runChargeLoading">
            <Table
              :columns="props.chargeColumns"
              :data-source="props.selectedRunCharges"
              :locale="{ emptyText: $t('plugin.storage-billing.admin.runs.charges.empty') }"
              :pagination="false"
              row-key="id"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'billing_date'">{{ record.period_label || record.billing_date }}</template>
                <template v-else-if="column.key === 'tenant_id'">#{{ record.tenant_id }}</template>
                <template v-else-if="column.key === 'provider'">{{ props.providerLabelFromAny(record.provider_code) }}</template>
                <template v-else-if="column.key === 'source'">{{ props.sourceLabelFromCharge(record) }}</template>
                <template v-else-if="column.key === 'charge_basis'">{{ props.chargeBasisLabel(record.charge_basis) }}</template>
                <template v-else-if="column.key === 'usage_bytes'">{{ props.formatBytes(record.usage_bytes) }}</template>
                <template v-else-if="column.key === 'amount_total'">{{ record.amount_total }}</template>
                <template v-else-if="column.key === 'currency'">{{ record.currency }}</template>
              </template>
            </Table>
          </Spin>
        </Card>

        <div v-if="props.auditedSources.length" class="audit-list">
          <div v-for="source in props.auditedSources" :key="`audit-${source.id}`" class="audit-card">
            <div class="audit-head">
              <Space wrap>
                <Tag color="blue">{{ props.providerLabelFromAny(source.provider_code) }}</Tag>
                <Tag :color="props.statusColor(source.source_status)">{{ props.prettyStatus(source.source_status) }}</Tag>
              </Space>
            </div>
            <div class="audit-summary">
              <Tag color="warning">{{ $t('plugin.storage-billing.admin.runs.audit.unmatchedSamples') }} {{ props.sourceAllocationAudit(source).unmatched_item_samples.length }}</Tag>
              <Tag color="error">{{ $t('plugin.storage-billing.admin.runs.audit.ambiguousSamples') }} {{ props.sourceAllocationAudit(source).ambiguous_item_samples.length }}</Tag>
            </div>
            <details class="audit-details">
              <summary>{{ $t('plugin.storage-billing.admin.runs.audit.toggle') }}</summary>
              <pre>{{ JSON.stringify(source.raw_payload_json, null, 2) }}</pre>
            </details>
          </div>
        </div>
      </Spin>
    </Card>
  </Card>
</template>
