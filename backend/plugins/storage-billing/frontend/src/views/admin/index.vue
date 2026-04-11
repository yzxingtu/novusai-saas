<script lang="ts" setup>
import { Page } from '@vben/common-ui';
import { Spin } from 'ant-design-vue';

import AdminBindingModal from './components/AdminBindingModal.vue';
import AdminBindingsCard from './components/AdminBindingsCard.vue';
import AdminOverviewHero from './components/AdminOverviewHero.vue';
import AdminProvidersCard from './components/AdminProvidersCard.vue';
import AdminRunsCard from './components/AdminRunsCard.vue';
import { PROFILE_FIELDS } from './storage-billing-admin-contracts';
import { useStorageBillingAdminPage } from './use-storage-billing-admin-page';

defineOptions({ name: 'StorageBillingAdminPage' });

const profileFields = PROFILE_FIELDS;

const {
  applyRunChargeFilters,
  auditedSources,
  bindings,
  bindingsWorkflow,
  canConfigureAdmin,
  canReconcileAdmin,
  canViewAdmin,
  exportCurrentRunCharges,
  loadAll,
  loadRunDetail,
  loading,
  manualBillingDate,
  manualProviderCodes,
  overview,
  presenters,
  profiles,
  providerLabel,
  providerLabelFromAny,
  qiniuBillingMonth,
  resetRunChargeFilters,
  runChargeActiveFilters,
  runChargeExporting,
  runChargeFilters,
  runChargeLoading,
  runChargeProviderOptions,
  runChargeSourceOptions,
  runDetailLoading,
  runs,
  saveProfiles,
  selectedRun,
  selectedRunChargeResponse,
  selectedRunCharges,
  selectedRunDetail,
  selectedRunProviderResults,
  saving,
  sourceLabelFromCharge,
  triggerQiniuMonthlyRun,
  triggerRun,
  validateProvider,
  validations,
  visibleProviderCodes,
} = useStorageBillingAdminPage();

const {
  bindingLoading,
  bindingOpen,
  clearScopeFields,
  currentModeOptions,
  currentScopeOptions,
  form,
  handleProviderChange,
  modalOkText,
  modalTitle,
  openCreate,
  openEdit,
  providerOptions,
  resetForm,
  revalidateBinding,
  searchTenants,
  submitBinding,
  tenants,
} = bindingsWorkflow;

const {
  billSourceOptions,
  bindingColumns,
  capabilityCycleLabel,
  capabilityModeLabel,
  capabilityPeriodLabel,
  capabilityTargetRuleLabel,
  chargeBasisLabel,
  chargeColumns,
  fieldLabel,
  formatBytes,
  formatTimestamp,
  hasVisibleProviders,
  manualBillingDateError,
  manualBillingDateStatus,
  manualRunHelpText,
  manualRunProviderOptions,
  prettyStatus,
  profileWarnings,
  providerCapabilitySummary,
  providerCapabilityTags,
  providerRuntimeValue,
  providerStorageContext,
  providerStorageMatch,
  providerStorageReady,
  qiniuMonthError,
  qiniuMonthStatus,
  qiniuVisible,
  reconciliationScheduleSummary,
  runColumns,
  runProviderSummaries,
  runRequestedScope,
  scopeProviderCodes,
  scopeProviderPlans,
  scopeValue,
  selectedRunScopePayload,
  selectedRunScopeSummary,
  sourceAllocationAudit,
  sourceAllocationSummary,
  sourceColumns,
  statusColor,
} = presenters;
</script>

<template>
  <Page class="storage-billing-admin">
    <Spin :spinning="loading || saving">
      <AdminOverviewHero
        :can-configure-admin="canConfigureAdmin"
        :can-reconcile-admin="canReconcileAdmin"
        :has-visible-providers="hasVisibleProviders"
        :load-all="loadAll"
        :manual-billing-date="manualBillingDate"
        :manual-billing-date-error="manualBillingDateError"
        :manual-billing-date-status="manualBillingDateStatus"
        :manual-provider-codes="manualProviderCodes"
        :manual-run-help-text="manualRunHelpText"
        :manual-run-provider-options="manualRunProviderOptions"
        :overview="overview"
        :qiniu-billing-month="qiniuBillingMonth"
        :qiniu-month-error="qiniuMonthError"
        :qiniu-month-status="qiniuMonthStatus"
        :qiniu-visible="qiniuVisible"
        :reconciliation-schedule-summary="reconciliationScheduleSummary"
        :save-profiles="saveProfiles"
        :trigger-qiniu-monthly-run="triggerQiniuMonthlyRun"
        :trigger-run="triggerRun"
        @update:manual-billing-date="manualBillingDate = $event"
        @update:manual-provider-codes="manualProviderCodes = $event"
        @update:qiniu-billing-month="qiniuBillingMonth = $event"
      />

      <AdminProvidersCard
        :bill-source-options="billSourceOptions"
        :can-configure-admin="canConfigureAdmin"
        :capability-cycle-label="capabilityCycleLabel"
        :capability-mode-label="capabilityModeLabel"
        :capability-period-label="capabilityPeriodLabel"
        :capability-target-rule-label="capabilityTargetRuleLabel"
        :field-label="fieldLabel"
        :has-visible-providers="hasVisibleProviders"
        :pretty-status="prettyStatus"
        :profile-fields="profileFields"
        :profile-warnings="profileWarnings"
        :profiles="profiles"
        :provider-capability-summary="providerCapabilitySummary"
        :provider-capability-tags="providerCapabilityTags"
        :provider-label="providerLabel"
        :provider-label-from-any="providerLabelFromAny"
        :provider-runtime-value="providerRuntimeValue"
        :provider-storage-context="providerStorageContext"
        :provider-storage-match="providerStorageMatch"
        :provider-storage-ready="providerStorageReady"
        :status-color="statusColor"
        :validate-provider="validateProvider"
        :validations="validations"
        :visible-provider-codes="visibleProviderCodes"
      />

      <AdminBindingsCard
        :binding-columns="bindingColumns"
        :bindings="bindings"
        :can-configure-admin="canConfigureAdmin"
        :has-visible-providers="hasVisibleProviders"
        :open-create="openCreate"
        :open-edit="openEdit"
        :pretty-status="prettyStatus"
        :provider-label="providerLabel"
        :revalidate-binding="revalidateBinding"
        :scope-value="scopeValue"
        :status-color="statusColor"
      />

      <AdminRunsCard
        :apply-run-charge-filters="applyRunChargeFilters"
        :audited-sources="auditedSources"
        :can-view-admin="canViewAdmin"
        :capability-target-rule-label="capabilityTargetRuleLabel"
        :charge-basis-label="chargeBasisLabel"
        :charge-columns="chargeColumns"
        :export-current-run-charges="exportCurrentRunCharges"
        :format-bytes="formatBytes"
        :format-timestamp="formatTimestamp"
        :load-run-detail="loadRunDetail"
        :pretty-status="prettyStatus"
        :provider-label-from-any="providerLabelFromAny"
        :reset-run-charge-filters="resetRunChargeFilters"
        :run-charge-active-filters="runChargeActiveFilters"
        :run-charge-exporting="runChargeExporting"
        :run-charge-filters="runChargeFilters"
        :run-charge-loading="runChargeLoading"
        :run-charge-provider-options="runChargeProviderOptions"
        :run-charge-source-options="runChargeSourceOptions"
        :run-columns="runColumns"
        :run-detail-loading="runDetailLoading"
        :run-provider-summaries="runProviderSummaries"
        :run-requested-scope="runRequestedScope"
        :runs="runs"
        :scope-provider-codes="scopeProviderCodes"
        :scope-provider-plans="scopeProviderPlans"
        :selected-run="selectedRun"
        :selected-run-charge-response="selectedRunChargeResponse"
        :selected-run-charges="selectedRunCharges"
        :selected-run-detail="selectedRunDetail"
        :selected-run-provider-results="selectedRunProviderResults"
        :selected-run-scope-payload="selectedRunScopePayload"
        :selected-run-scope-summary="selectedRunScopeSummary"
        :source-allocation-audit="sourceAllocationAudit"
        :source-allocation-summary="sourceAllocationSummary"
        :source-columns="sourceColumns"
        :source-label-from-charge="sourceLabelFromCharge"
        :status-color="statusColor"
      />

      <AdminBindingModal
        :binding-loading="bindingLoading"
        :clear-scope-fields="clearScopeFields"
        :current-mode-options="currentModeOptions"
        :current-scope-options="currentScopeOptions"
        :form="form"
        :handle-provider-change="handleProviderChange"
        :modal-ok-text="modalOkText"
        :modal-title="modalTitle"
        :open="bindingOpen"
        :provider-options="providerOptions"
        :reset-form="resetForm"
        :search-tenants="searchTenants"
        :submit-binding="submitBinding"
        :tenants="tenants"
        @update:open="bindingOpen = $event"
      />
    </Spin>
  </Page>
</template>

<style>
.storage-billing-admin{--hero:linear-gradient(135deg,#fff7ed,#f8fafc 50%,#eff6ff)}
.storage-billing-admin .hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:20px;padding:24px;border-radius:24px;background:var(--hero);border:1px solid rgba(180,83,9,.14)}
.storage-billing-admin .badge{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#b45309;margin-bottom:8px}
.storage-billing-admin .hero h1{margin:0 0 8px;font-size:28px}
.storage-billing-admin .hero p{margin:0;color:#475569;max-width:760px}
.storage-billing-admin .hero-actions{display:flex;flex-direction:column;gap:12px;min-width:320px}
.storage-billing-admin .toolbar-group{justify-content:flex-end}
.storage-billing-admin .toolbar-stack{display:flex;flex-direction:column;gap:6px}
.storage-billing-admin .toolbar-field{min-width:180px}
.storage-billing-admin .toolbar-field-wide{min-width:240px}
.storage-billing-admin .toolbar-help{font-size:12px;color:#64748b;max-width:360px}
.storage-billing-admin .toolbar-help-error{color:#dc2626}
.storage-billing-admin .stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:20px}
.storage-billing-admin .block{margin-bottom:20px}
.storage-billing-admin .providers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.storage-billing-admin .section-subtitle,
.storage-billing-admin .muted{color:#64748b}
.storage-billing-admin .section-subtitle{margin-bottom:16px}
.storage-billing-admin .capability-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:16px}
.storage-billing-admin .capability-item{padding:12px;border-radius:14px;background:#f8fafc;border:1px solid rgba(148,163,184,.18)}
.storage-billing-admin .capability-item-wide{grid-column:1/-1}
.storage-billing-admin .provider-runtime{margin-bottom:16px;padding:12px;border-radius:14px;background:#f8fafc;border:1px solid rgba(148,163,184,.18)}
.storage-billing-admin .capability-label{display:block;margin-bottom:6px;font-size:12px;color:#64748b}
.storage-billing-admin .actions{display:flex;justify-content:flex-end}
.storage-billing-admin .empty{margin-top:12px}
.storage-billing-admin .run-detail{margin-top:16px}
.storage-billing-admin .run-scope-summary{line-height:1.6;color:#0f172a}
.storage-billing-admin .run-scope-tags{margin-top:8px}
.storage-billing-admin .run-plan-list,
.storage-billing-admin .run-provider-results{display:grid;gap:12px;margin-top:16px}
.storage-billing-admin .run-plan-card,
.storage-billing-admin .run-provider-card{padding:12px;border-radius:14px;background:#f8fafc;border:1px solid rgba(148,163,184,.18)}
.storage-billing-admin .run-scope-details{margin-top:8px}
.storage-billing-admin .run-scope-details summary{cursor:pointer;color:#64748b}
.storage-billing-admin .run-scope-details pre{margin:8px 0 0;padding:12px;border-radius:12px;background:#0f172a;color:#e2e8f0;overflow:auto;max-height:320px}
.storage-billing-admin .run-charge-summary{display:flex;margin:12px 0}
.storage-billing-admin .run-charge-toolbar{display:flex;margin-bottom:12px}
.storage-billing-admin .toolbar-source{min-width:260px}
.storage-billing-admin .run-charge-card{margin-top:16px}
.storage-billing-admin .audit-list{display:grid;gap:12px;margin-top:16px}
.storage-billing-admin .audit-card{padding:16px;border-radius:16px;background:#f8fafc;border:1px solid rgba(148,163,184,.2)}
.storage-billing-admin .audit-head,
.storage-billing-admin .audit-summary{margin-bottom:12px}
.storage-billing-admin .audit-details summary{cursor:pointer;color:#0f172a;font-weight:600}
.storage-billing-admin .audit-details pre{margin-top:12px;padding:12px;border-radius:12px;background:#0f172a;color:#e2e8f0;overflow:auto;max-height:320px}
@media (max-width:1200px){
  .storage-billing-admin .stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  .storage-billing-admin .providers{grid-template-columns:1fr}
}
@media (max-width:768px){
  .storage-billing-admin .hero{flex-direction:column}
  .storage-billing-admin .hero-actions{min-width:0;width:100%}
  .storage-billing-admin .stats{grid-template-columns:1fr}
  .storage-billing-admin .capability-grid{grid-template-columns:1fr}
}
</style>
