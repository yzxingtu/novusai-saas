<script lang="ts" setup>
import type { OverviewResponse, ProviderCode } from '../../../types';

const props = defineProps<{
  canConfigureAdmin: boolean;
  canReconcileAdmin: boolean;
  hasVisibleProviders: boolean;
  loadAll: () => void;
  manualBillingDate: string;
  manualBillingDateError: null | string;
  manualBillingDateStatus?: string;
  manualProviderCodes: ProviderCode[];
  manualRunHelpText: string;
  manualRunProviderOptions: Array<{ label: string; value: ProviderCode }>;
  overview: null | OverviewResponse;
  qiniuBillingMonth: string;
  qiniuMonthError: null | string;
  qiniuMonthStatus?: string;
  qiniuVisible: boolean;
  reconciliationScheduleSummary: string;
  saveProfiles: () => void;
  triggerQiniuMonthlyRun: () => void;
  triggerRun: () => void;
}>();

const emit = defineEmits<{
  'update:manualBillingDate': [value: string];
  'update:manualProviderCodes': [value: ProviderCode[]];
  'update:qiniuBillingMonth': [value: string];
}>();

function handleManualBillingDateChange(value: string): void {
  emit('update:manualBillingDate', value);
}

function handleManualProviderCodesChange(value: ProviderCode[]): void {
  emit('update:manualProviderCodes', value);
}

function handleQiniuBillingMonthChange(value: string): void {
  emit('update:qiniuBillingMonth', value);
}
</script>

<template>
  <div class="hero">
    <div>
      <div class="badge">{{ $t('plugin.storage-billing.admin.hero.badge') }}</div>
      <h1>{{ $t('plugin.storage-billing.admin.page.title') }}</h1>
      <p>{{ $t('plugin.storage-billing.admin.page.subtitle') }}</p>
    </div>
    <div class="hero-actions">
      <Space wrap class="toolbar-group">
        <Button @click="props.loadAll">{{ $t('plugin.storage-billing.admin.actions.refresh') }}</Button>
        <Button
          v-if="props.canConfigureAdmin"
          :disabled="!props.hasVisibleProviders"
          type="primary"
          @click="props.saveProfiles"
        >
          {{ $t('plugin.storage-billing.admin.providers.save') }}
        </Button>
      </Space>
      <div class="toolbar-stack">
        <Space wrap class="toolbar-group">
          <Input
            :status="props.manualBillingDateStatus"
            :value="props.manualBillingDate"
            class="toolbar-field"
            :placeholder="$t('plugin.storage-billing.admin.actions.dailyPlaceholder')"
            @update:value="handleManualBillingDateChange"
          />
          <Select
            :options="props.manualRunProviderOptions"
            :value="props.manualProviderCodes"
            class="toolbar-field toolbar-field-wide"
            mode="multiple"
            :placeholder="$t('plugin.storage-billing.admin.actions.providerPlaceholder')"
            @update:value="handleManualProviderCodesChange"
          />
          <Button
            v-if="props.canReconcileAdmin"
            :disabled="!props.hasVisibleProviders"
            @click="props.triggerRun"
          >
            {{ $t('plugin.storage-billing.admin.actions.triggerRun') }}
          </Button>
        </Space>
        <div class="toolbar-help" :class="{ 'toolbar-help-error': props.manualBillingDateError }">
          {{ props.manualRunHelpText }}
        </div>
      </div>
      <div v-if="props.qiniuVisible" class="toolbar-stack">
        <Space wrap class="toolbar-group">
          <Input
            :status="props.qiniuMonthStatus"
            :value="props.qiniuBillingMonth"
            class="toolbar-field"
            :placeholder="$t('plugin.storage-billing.admin.actions.qiniuMonthlyPlaceholder')"
            @update:value="handleQiniuBillingMonthChange"
          />
          <Button v-if="props.canReconcileAdmin" @click="props.triggerQiniuMonthlyRun">
            {{ $t('plugin.storage-billing.admin.actions.triggerQiniuMonthly') }}
          </Button>
        </Space>
        <div class="toolbar-help" :class="{ 'toolbar-help-error': props.qiniuMonthError }">
          {{ props.qiniuMonthError || $t('plugin.storage-billing.admin.actions.triggerQiniuMonthlyHint') }}
        </div>
      </div>
      <div v-if="!props.hasVisibleProviders" class="toolbar-help toolbar-help-error">
        {{ $t('plugin.storage-billing.admin.providers.noActiveDriver') }}
      </div>
    </div>
  </div>

  <div class="stats">
    <Card>
      <Statistic
        :title="$t('plugin.storage-billing.admin.overview.billableDrivers')"
        :value="props.overview?.billable_drivers.length ?? 0"
      />
    </Card>
    <Card>
      <Statistic
        :title="$t('plugin.storage-billing.admin.overview.enabledDrivers')"
        :value="props.overview?.host_snapshot.enabled_storage_drivers.length ?? 0"
      />
    </Card>
    <Card>
      <Statistic
        :title="$t('plugin.storage-billing.admin.overview.bindingTotal')"
        :value="props.overview?.ledger_snapshot.binding_total ?? 0"
      />
    </Card>
    <Card>
      <Statistic
        :title="$t('plugin.storage-billing.admin.overview.statementTotal')"
        :value="props.overview?.ledger_snapshot.statement_total ?? 0"
      />
    </Card>
  </div>

  <Alert
    class="block"
    :message="$t('plugin.storage-billing.admin.hero.lag')"
    :description="`${props.overview?.reconciliation_schedule.local_time ?? '03:00'} / ${props.reconciliationScheduleSummary} / ${props.overview?.mode ?? '-'}`"
    show-icon
    type="info"
  />
</template>
