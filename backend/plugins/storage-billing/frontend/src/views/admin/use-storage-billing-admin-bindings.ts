import type { ComputedRef } from 'vue';
import type { BindingRecord, ProviderCode, TenantSelectOption } from '../../types';

import { computed, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { $t } from '@novus/plugin-shared';

import {
  createBindingApi,
  getTenantSelectOptionsApi,
  updateBindingApi,
  validateBindingApi,
} from '../../api/admin';
import {
  buildBindingPayload,
  emptyForm,
  type BindingFormState,
} from './storage-billing-admin-contracts';

type UseStorageBillingAdminBindingsOptions = {
  canConfigureAdmin: ComputedRef<boolean>;
  loadAll: () => Promise<void>;
  providerLabel: (code: ProviderCode) => string;
  visibleProviderCodes: ComputedRef<ProviderCode[]>;
};

export function useStorageBillingAdminBindings(
  options: UseStorageBillingAdminBindingsOptions,
) {
  const bindingOpen = ref(false);
  const bindingLoading = ref(false);
  const editingId = ref<null | number>(null);
  const tenants = ref<TenantSelectOption[]>([]);
  const form = reactive<BindingFormState>(emptyForm());

  const modeOptions = computed(() => [
    {
      label: $t('plugin.storage-billing.admin.bindings.mode.official_reconciled'),
      value: 'official_reconciled',
    },
    {
      label: $t('plugin.storage-billing.admin.bindings.mode.official_pass_through'),
      value: 'official_pass_through',
    },
  ]);

  const scopeOptions = computed(() => [
    { label: $t('plugin.storage-billing.admin.bindings.scope.bucket'), value: 'bucket' },
    { label: $t('plugin.storage-billing.admin.bindings.scope.domain'), value: 'domain' },
    { label: $t('plugin.storage-billing.admin.bindings.scope.account'), value: 'account' },
    { label: $t('plugin.storage-billing.admin.bindings.scope.tag'), value: 'tag' },
  ]);

  const providerOptions = computed(() =>
    options.visibleProviderCodes.value.map((code) => ({
      label: options.providerLabel(code),
      value: code,
    })),
  );

  const currentModeOptions = computed(() =>
    form.provider_code === 'qiniu-kodo'
      ? modeOptions.value.filter((item) => item.value === 'official_reconciled')
      : modeOptions.value,
  );

  const currentScopeOptions = computed(() =>
    form.provider_code === 'qiniu-kodo'
      ? scopeOptions.value.filter((item) => item.value === 'account')
      : scopeOptions.value,
  );

  const modalTitle = computed(() =>
    editingId.value === null
      ? $t('plugin.storage-billing.admin.bindingModal.createTitle')
      : $t('plugin.storage-billing.admin.bindingModal.editTitle'),
  );

  const modalOkText = computed(() =>
    editingId.value === null
      ? $t('plugin.storage-billing.admin.bindingModal.submitCreate')
      : $t('plugin.storage-billing.admin.bindingModal.submitUpdate'),
  );

  function clearScopeFields(scopeType: BindingFormState['scope_type']): void {
    if (scopeType !== 'bucket') form.bucket_name = '';
    if (scopeType !== 'domain') form.domain_name = '';
    if (scopeType !== 'account') form.account_identifier = '';
    if (scopeType !== 'tag') {
      form.tag_key = '';
      form.tag_value = '';
    }
  }

  function handleProviderChange(code: ProviderCode): void {
    if (code === 'qiniu-kodo') {
      form.billing_mode = 'official_reconciled';
      if (form.scope_type !== 'account') {
        form.scope_type = 'account';
        clearScopeFields('account');
      }
    }
  }

  function syncVisibleProviderSelection(): void {
    const defaultProvider = options.visibleProviderCodes.value[0];
    if (!defaultProvider) {
      return;
    }
    if (!options.visibleProviderCodes.value.includes(form.provider_code)) {
      form.provider_code = defaultProvider;
    }
    handleProviderChange(form.provider_code);
  }

  function resetForm(): void {
    Object.assign(form, emptyForm());
    syncVisibleProviderSelection();
  }

  async function searchTenants(keyword: string): Promise<void> {
    if (!options.canConfigureAdmin.value) {
      tenants.value = [];
      return;
    }
    tenants.value = await getTenantSelectOptionsApi(keyword.trim());
  }

  async function openCreate(): Promise<void> {
    if (!options.canConfigureAdmin.value) return;
    editingId.value = null;
    resetForm();
    tenants.value = await getTenantSelectOptionsApi();
    bindingOpen.value = true;
  }

  function openEdit(record: BindingRecord): void {
    if (!options.canConfigureAdmin.value) return;
    editingId.value = record.id;
    Object.assign(form, emptyForm(), {
      tenant_id: record.tenant_id,
      provider_code: record.provider_code,
      billing_mode: record.billing_mode,
      scope_type: record.scope_type,
      bucket_name: record.bucket_name ?? '',
      domain_name: record.domain_name ?? '',
      account_identifier: record.account_identifier ?? '',
      tag_key: record.tag_key ?? '',
      tag_value: record.tag_value ?? '',
      is_active: record.is_active,
    });
    if (!tenants.value.some((item) => item.value === record.tenant_id)) {
      tenants.value = [...tenants.value, { label: `#${record.tenant_id}`, value: record.tenant_id }];
    }
    bindingOpen.value = true;
  }

  async function submitBinding(): Promise<void> {
    if (!options.canConfigureAdmin.value) return;
    if (!form.tenant_id) {
      message.warning($t('plugin.storage-billing.admin.bindingForm.selectTenant'));
      return;
    }

    bindingLoading.value = true;
    try {
      const result = editingId.value === null
        ? await createBindingApi(buildBindingPayload(form))
        : await updateBindingApi(editingId.value, buildBindingPayload(form));
      bindingOpen.value = false;
      await options.loadAll();
      message[
        result.validation.validation_status === 'valid' ? 'success' : 'warning'
      ](
        $t(
          result.validation.validation_status === 'valid'
            ? 'plugin.storage-billing.admin.messages.bindingSaved'
            : 'plugin.storage-billing.admin.messages.bindingInvalid',
        ),
      );
    } finally {
      bindingLoading.value = false;
    }
  }

  async function revalidateBinding(record: BindingRecord): Promise<void> {
    if (!options.canConfigureAdmin.value) return;
    const result = await validateBindingApi(record.id);
    message[
      result.validation.validation_status === 'valid' ? 'success' : 'warning'
    ](
      result.validation.validation_message
        || $t('plugin.storage-billing.admin.messages.bindingValidated'),
    );
    await options.loadAll();
  }

  return {
    bindingLoading,
    bindingOpen,
    clearScopeFields,
    currentModeOptions,
    currentScopeOptions,
    editingId,
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
    syncVisibleProviderSelection,
    tenants,
  };
}
