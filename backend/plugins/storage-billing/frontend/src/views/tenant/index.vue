<script lang="ts" setup>
import type {
  TenantPrerequisitesResponse,
  TenantStatementChargesResponse,
  TenantStatementChargeRow,
  TenantStatementResponse,
  TenantStatementSummary,
} from '../../types';
import { computed, onMounted, ref } from 'vue';
import { Page } from '@vben/common-ui';
import { Alert, Button, Card, Descriptions, DescriptionsItem, Empty, Space, Spin, Statistic, Table, Tag, message } from 'ant-design-vue';
import { $t, downloadBlob } from '@novus/plugin-shared';
import {
  exportTenantStatementChargesCsvApi,
  getCurrentStatementApi,
  getTenantPrerequisitesApi,
  getTenantStatementChargesApi,
  getTenantStatementsApi,
} from '../../api/tenant';

defineOptions({ name: 'StorageBillingTenantPage' });

const loading = ref(false);
const chargeLoading = ref(false);
const exportLoading = ref(false);
const prerequisites = ref<null | TenantPrerequisitesResponse>(null);
const statement = ref<null | TenantStatementResponse>(null);
const recentStatements = ref<TenantStatementSummary[]>([]);
const selectedBillingDate = ref('');
const selectedPeriodType = ref('');
const selectedStatement = ref<null | TenantStatementSummary>(null);
const charges = ref<null | TenantStatementChargesResponse>(null);
const chargeRows = computed<TenantStatementChargeRow[]>(() => charges.value?.items ?? []);

const bindingColumns = computed(() => [
  { title: $t('plugin.storageBilling.admin.bindings.table.provider'), key: 'provider' },
  { title: $t('plugin.storageBilling.admin.bindings.table.scope'), key: 'scope' },
  { title: $t('plugin.storageBilling.admin.bindings.table.status'), key: 'status' },
]);
const statementColumns = computed(() => [
  { title: $t('plugin.storageBilling.tenant.statements.table.billingDate'), key: 'billing_date' },
  { title: $t('plugin.storageBilling.tenant.statements.table.amount'), key: 'amount_total' },
  { title: $t('plugin.storageBilling.tenant.statements.table.chargeCount'), key: 'charge_count' },
  { title: $t('plugin.storageBilling.tenant.statements.table.status'), key: 'status' },
  { title: $t('plugin.storageBilling.tenant.statements.table.actions'), key: 'actions' },
]);
const chargeColumns = computed(() => [
  { title: $t('plugin.storageBilling.tenant.charges.table.provider'), key: 'provider_code' },
  { title: $t('plugin.storageBilling.tenant.charges.table.chargeBasis'), key: 'charge_basis' },
  { title: $t('plugin.storageBilling.tenant.charges.table.usage'), key: 'usage_bytes' },
  { title: $t('plugin.storageBilling.tenant.charges.table.amount'), key: 'amount_total' },
  { title: $t('plugin.storageBilling.tenant.charges.table.currency'), key: 'currency' },
]);

const bindings = computed(() => prerequisites.value?.bindings.items.filter((item) => item.is_active) ?? []);
const selectedAmount = computed(() => selectedStatement.value?.amount_total ?? '0');
const selectedChargeCount = computed(() => selectedStatement.value?.charge_count ?? 0);
const chargeTotal = computed(() => charges.value?.total ?? 0);
const tenantCapabilityEntries = computed(() =>
  Object.entries(prerequisites.value?.provider_capabilities ?? {}).map(([code, capability]) => ({
    code,
    ...capability,
  })),
);

function providerLabel(code: string) {
  return $t(`plugin.storageBilling.common.provider.${code}`);
}

function statusLabel(status: string) {
  const key = `plugin.storageBilling.common.status.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

function statusColor(status: string) {
  switch (status) {
    case 'published':
    case 'generated':
    case 'valid':
    case 'completed':
      return 'success';
    case 'completed_with_gaps':
    case 'pending':
      return 'orange';
    case 'failed':
    case 'invalid':
      return 'error';
    default:
      return 'default';
  }
}

function reasonLabel(reason: string) {
  return $t(`plugin.storageBilling.tenant.prerequisites.reason.${reason}`);
}

function chargeBasisLabel(basis: string) {
  const key = `plugin.storageBilling.common.chargeBasis.${basis}`;
  const translated = $t(key);
  return translated === key ? basis : translated;
}

function capabilityModeLabel(value?: string) {
  if (!value) return '-';
  const map: Record<string, string> = {
    strict_daily_reconciliation: $t('plugin.storageBilling.common.capabilities.mode.strictDailyReconciliation'),
    monthly_settled: $t('plugin.storageBilling.common.capabilities.mode.monthlySettled'),
  };
  return map[value] ?? value;
}

function capabilityCycleLabel(value?: string) {
  if (!value) return '-';
  const map: Record<string, string> = {
    daily: $t('plugin.storageBilling.common.capabilities.cycle.daily'),
    monthly: $t('plugin.storageBilling.common.capabilities.cycle.monthly'),
  };
  return map[value] ?? value;
}

function capabilityPeriodSummary(values?: string[]) {
  if (!values?.length) return '-';
  const map: Record<string, string> = {
    daily: $t('plugin.storageBilling.common.periodType.daily'),
    monthly: $t('plugin.storageBilling.common.periodType.monthly'),
  };
  return values.map((item) => map[item] ?? item).join(' / ');
}

function capabilityTargetRuleSummary(value?: string) {
  if (!value) return '-';
  const map: Record<string, string> = {
    'per-provider': $t('plugin.storageBilling.common.capabilities.targetRule.perProvider'),
  };
  return map[value] ?? value;
}

function scopeTypeSummary(values?: string[]) {
  if (!values?.length) return '-';
  return values
    .map((item) => $t(`plugin.storageBilling.admin.bindings.scope.${item}`))
    .join(' / ');
}

function boolLabel(value?: boolean) {
  return value ? $t('plugin.storageBilling.common.yes') : $t('plugin.storageBilling.common.no');
}

function formatBytes(value: number): string {
  if (value <= 0) {
    return '0 B';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const exp = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const size = value / 1024 ** exp;
  return `${size.toFixed(size >= 100 || exp === 0 ? 0 : 2)} ${units[exp]}`;
}

function resolveInitialBillingDate(
  current: null | TenantStatementResponse,
  statements: TenantStatementSummary[],
): string {
  if (current?.statement?.billing_date) {
    return current.statement.billing_date;
  }
  if (statements.length > 0) {
    return statements[0]?.billing_date ?? '';
  }
  return '';
}

function statementPeriodLabel(statementItem: null | TenantStatementSummary): string {
  return statementItem?.period_label || statementItem?.billing_date || '-';
}

async function loadChargesForDate(
  billingDate: string,
  periodType?: string,
) {
  if (!billingDate) {
    selectedBillingDate.value = '';
    selectedPeriodType.value = '';
    selectedStatement.value = null;
    charges.value = null;
    return;
  }

  selectedBillingDate.value = billingDate;
  selectedPeriodType.value = periodType || '';
  chargeLoading.value = true;
  try {
    const [statementData, chargeData] = await Promise.all([
      getCurrentStatementApi(billingDate, periodType),
      getTenantStatementChargesApi(billingDate, periodType),
    ]);
    statement.value = statementData;
    charges.value = chargeData;
    selectedStatement.value = chargeData.statement || statementData.statement;
    selectedPeriodType.value = String(
      chargeData.period_type || chargeData.statement?.period_type || statementData.statement?.period_type || periodType || '',
    );
  } finally {
    chargeLoading.value = false;
  }
}

async function exportCurrentCharges(): Promise<void> {
  if (!selectedBillingDate.value) {
    return;
  }
  exportLoading.value = true;
  try {
    const blob = await exportTenantStatementChargesCsvApi(
      selectedBillingDate.value,
      selectedPeriodType.value,
    );
    downloadBlob(blob, {
      filename: `storage-billing-${selectedPeriodType.value || 'daily'}-${selectedBillingDate.value}.csv`,
    });
    message.success($t('plugin.storageBilling.tenant.messages.exportSuccess'));
  } catch {
    message.error($t('plugin.storageBilling.tenant.messages.requestFailed'));
  } finally {
    exportLoading.value = false;
  }
}

async function loadPage() {
  loading.value = true;
  try {
    const [p, s, listData] = await Promise.all([
      getTenantPrerequisitesApi(),
      getCurrentStatementApi(),
      getTenantStatementsApi(30),
    ]);
    prerequisites.value = p;
    statement.value = s;
    recentStatements.value = listData.items;

    const initialDate = resolveInitialBillingDate(s, listData.items);
    await loadChargesForDate(
      initialDate,
      s?.statement?.period_type || listData.items[0]?.period_type,
    );
  } finally {
    loading.value = false;
  }
}

onMounted(() => void loadPage());
</script>

<template>
  <Page class="storage-billing-tenant">
    <Spin :spinning="loading">
      <div class="hero">
        <div>
          <div class="badge">{{ $t('plugin.storageBilling.tenant.summary.localFree') }}</div>
          <h1>{{ $t('plugin.storageBilling.tenant.page.title') }}</h1>
          <p>{{ $t('plugin.storageBilling.tenant.page.subtitle') }}</p>
          <Space wrap>
            <Tag :color="prerequisites?.prerequisites.ready ? 'success' : 'orange'">
              {{
                prerequisites?.prerequisites.ready
                  ? $t('plugin.storageBilling.tenant.summary.ready')
                  : $t('plugin.storageBilling.tenant.summary.notReady')
              }}
            </Tag>
            <Tag color="blue">
              {{ $t('plugin.storageBilling.tenant.summary.currentDriver') }}:
              {{ prerequisites?.prerequisites.current_driver || '-' }}
            </Tag>
          </Space>
        </div>
        <Button @click="loadPage">{{ $t('plugin.storageBilling.admin.actions.refresh') }}</Button>
      </div>

      <div class="stats">
        <Card><Statistic :title="$t('plugin.storageBilling.tenant.summary.currentDriver')" :value="prerequisites?.prerequisites.current_driver || '-'" /></Card>
        <Card><Statistic :title="$t('plugin.storageBilling.tenant.summary.activeBindings')" :value="bindings.length" /></Card>
        <Card><Statistic :title="$t('plugin.storageBilling.tenant.statement.amount')" :value="selectedAmount" /></Card>
        <Card><Statistic :title="$t('plugin.storageBilling.tenant.statement.chargeCount')" :value="selectedChargeCount" /></Card>
        <Card><Statistic :title="$t('plugin.storageBilling.tenant.summary.selectedBillingDate')" :value="statementPeriodLabel(selectedStatement)" /></Card>
      </div>

      <Alert
        v-if="prerequisites && !prerequisites.prerequisites.ready"
        :description="prerequisites.prerequisites.missing_reasons.map((item) => reasonLabel(item)).join(' | ')"
        show-icon
        type="warning"
        class="block"
      />

      <div class="grid">
        <Card :title="$t('plugin.storageBilling.tenant.prerequisites.title')">
          <Descriptions :column="1" bordered size="small">
            <DescriptionsItem :label="$t('plugin.storageBilling.tenant.prerequisites.plan')">
              {{ prerequisites?.plan.name || '-' }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storageBilling.tenant.prerequisites.featureEnabled')">
              <Tag :color="prerequisites?.plan.storage_billing_enabled ? 'success' : 'orange'">
                {{ boolLabel(prerequisites?.plan.storage_billing_enabled) }}
              </Tag>
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storageBilling.tenant.summary.currentDriver')">
              {{ prerequisites?.prerequisites.current_driver || '-' }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storageBilling.tenant.prerequisites.missing')">
              <div v-if="prerequisites?.prerequisites.missing_reasons.length">
                <Tag v-for="item in prerequisites?.prerequisites.missing_reasons" :key="item" color="orange">
                  {{ reasonLabel(item) }}
                </Tag>
              </div>
              <span v-else>{{ $t('plugin.storageBilling.tenant.prerequisites.none') }}</span>
            </DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storageBilling.tenant.prerequisites.providerCapabilities')">
              <div v-if="tenantCapabilityEntries.length" class="capability-list">
                <div v-for="item in tenantCapabilityEntries" :key="item.code" class="capability-card">
                  <div class="capability-head">
                    <strong>{{ providerLabel(item.code) }}</strong>
                    <Space wrap size="small">
                      <Tag v-if="item.manual_pull_supported" color="blue">{{ $t('plugin.storageBilling.common.capabilities.manualPullSupported') }}</Tag>
                      <Tag v-if="item.strict_reconciliation_supported" color="success">{{ $t('plugin.storageBilling.common.capabilities.strictDailySupported') }}</Tag>
                      <Tag v-if="item.scheduled_daily_supported" color="processing">{{ $t('plugin.storageBilling.common.capabilities.scheduledDailySupported') }}</Tag>
                    </Space>
                  </div>
                  <div class="capability-meta">
                    <span>{{ $t('plugin.storageBilling.tenant.prerequisites.mode') }}: {{ capabilityModeLabel(item.settlement_mode) }}</span>
                    <span>{{ $t('plugin.storageBilling.tenant.prerequisites.cycle') }}: {{ capabilityCycleLabel(item.settlement_cycle) }}</span>
                    <span>{{ $t('plugin.storageBilling.tenant.prerequisites.lagDays') }}: {{ item.official_billing_lag_days ?? '-' }}</span>
                    <span>{{ $t('plugin.storageBilling.tenant.prerequisites.periodTypes') }}: {{ capabilityPeriodSummary(item.supported_period_types) }}</span>
                    <span>{{ $t('plugin.storageBilling.tenant.prerequisites.targetRule') }}: {{ capabilityTargetRuleSummary(item.official_target_rule) }}</span>
                    <span>{{ $t('plugin.storageBilling.tenant.prerequisites.recommendedScopes') }}: {{ scopeTypeSummary(item.recommended_scope_types) }}</span>
                  </div>
                  <div v-if="item.capability_message" class="subtle">{{ item.capability_message }}</div>
                </div>
              </div>
              <span v-else>{{ $t('plugin.storageBilling.tenant.prerequisites.none') }}</span>
            </DescriptionsItem>
          </Descriptions>
        </Card>

        <Card :title="$t('plugin.storageBilling.tenant.statement.title')">
          <Descriptions v-if="selectedStatement" :column="1" bordered size="small">
            <DescriptionsItem :label="$t('plugin.storageBilling.tenant.statement.amount')">{{ selectedStatement.amount_total }}</DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storageBilling.tenant.statement.currency')">{{ selectedStatement.currency }}</DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storageBilling.tenant.statement.billingDate')">{{ statementPeriodLabel(selectedStatement) }}</DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storageBilling.tenant.statement.chargeCount')">{{ selectedStatement.charge_count }}</DescriptionsItem>
            <DescriptionsItem :label="$t('plugin.storageBilling.tenant.summary.statementStatus')">
              <Tag :color="statusColor(selectedStatement.status)">{{ statusLabel(selectedStatement.status) }}</Tag>
            </DescriptionsItem>
          </Descriptions>
          <Empty v-else :description="statement?.message || $t('plugin.storageBilling.tenant.statement.empty')" />
        </Card>
      </div>

      <Card :title="$t('plugin.storageBilling.tenant.statements.title')" class="block">
        <template #extra>
          <span class="subtle">{{ $t('plugin.storageBilling.tenant.statements.subtitle') }}</span>
        </template>
        <Table
          :columns="statementColumns"
          :data-source="recentStatements"
          :locale="{ emptyText: $t('plugin.storageBilling.tenant.statements.empty') }"
          :pagination="false"
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'billing_date'">{{ statementPeriodLabel(record) }}</template>
            <template v-else-if="column.key === 'amount_total'">{{ record.amount_total }}</template>
            <template v-else-if="column.key === 'charge_count'">{{ record.charge_count }}</template>
            <template v-else-if="column.key === 'status'">
              <Tag :color="statusColor(record.status)">
                {{ statusLabel(record.status) }}
              </Tag>
            </template>
            <template v-else-if="column.key === 'actions'">
              <Button size="small" type="link" @click="loadChargesForDate(record.billing_date, record.period_type)">
                {{ $t('plugin.storageBilling.tenant.statements.table.view') }}
              </Button>
            </template>
          </template>
        </Table>
      </Card>

      <Card :title="$t('plugin.storageBilling.tenant.charges.title')" class="block">
        <template #extra>
          <Space>
            <Tag color="blue">{{ $t('plugin.storageBilling.tenant.statement.billingDate') }}: {{ statementPeriodLabel(selectedStatement) }}</Tag>
            <Tag color="purple">{{ $t('plugin.storageBilling.tenant.charges.total') }}: {{ chargeTotal }}</Tag>
            <Button
              :disabled="!selectedBillingDate"
              :loading="exportLoading"
              size="small"
              @click="exportCurrentCharges"
            >
              {{ $t('plugin.storageBilling.tenant.charges.export') }}
            </Button>
          </Space>
        </template>
        <div class="subtle block-xs">{{ $t('plugin.storageBilling.tenant.charges.subtitle') }}</div>
        <Spin :spinning="chargeLoading">
          <Empty
            v-if="!selectedBillingDate"
            :description="$t('plugin.storageBilling.tenant.charges.noDate')"
          />
          <Table
            v-else
            :columns="chargeColumns"
            :data-source="chargeRows"
            :locale="{ emptyText: $t('plugin.storageBilling.tenant.charges.empty') }"
            :pagination="false"
            row-key="id"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'provider_code'">{{ providerLabel(record.provider_code) }}</template>
              <template v-else-if="column.key === 'charge_basis'">{{ chargeBasisLabel(record.charge_basis) }}</template>
              <template v-else-if="column.key === 'usage_bytes'">{{ formatBytes(record.usage_bytes || 0) }}</template>
              <template v-else-if="column.key === 'amount_total'">{{ record.amount_total }}</template>
              <template v-else-if="column.key === 'currency'">{{ record.currency || selectedStatement?.currency || '-' }}</template>
            </template>
          </Table>
        </Spin>
      </Card>

      <Card :title="$t('plugin.storageBilling.tenant.bindings.title')">
        <Table :columns="bindingColumns" :data-source="bindings" :locale="{ emptyText: $t('plugin.storageBilling.tenant.bindings.empty') }" :pagination="false" row-key="id">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key==='provider'">{{ providerLabel(record.provider_code) }}</template>
            <template v-else-if="column.key==='scope'"><Space><Tag color="blue">{{ $t(`plugin.storageBilling.admin.bindings.scope.${record.scope_type}`) }}</Tag><span>{{ record.scope_value }}</span></Space></template>
            <template v-else-if="column.key==='status'"><Tag :color="statusColor(record.validation_status)">{{ statusLabel(record.validation_status) }}</Tag></template>
          </template>
        </Table>
      </Card>
    </Spin>
  </Page>
</template>

<style scoped>
.storage-billing-tenant{--bg:linear-gradient(135deg,#f8fafc,#eff6ff 50%,#fff7ed)}
.hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:20px;padding:24px;border-radius:24px;background:var(--bg);border:1px solid rgba(37,99,235,.12)}
.badge{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#2563eb;margin-bottom:8px}
.hero h1{margin:0 0 8px;font-size:28px}
.hero p{margin:0;color:#475569;max-width:720px}
.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:20px}
.block{margin-bottom:20px}
.block-xs{margin-bottom:8px}
.subtle{color:#64748b;font-size:12px}
.capability-list{display:grid;gap:12px}
.capability-card{padding:12px;border-radius:14px;background:#f8fafc;border:1px solid rgba(148,163,184,.18)}
.capability-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:8px}
.capability-meta{display:grid;gap:6px;margin-bottom:8px;color:#334155;font-size:12px}
@media (max-width:960px){.hero{flex-direction:column}.stats,.grid{grid-template-columns:1fr}}
</style>
