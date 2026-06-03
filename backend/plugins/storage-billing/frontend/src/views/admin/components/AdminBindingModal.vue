<script lang="ts" setup>
import type { BillingMode, BindingScopeType, ProviderCode } from '../../../types';

type BindingFormState = {
  account_identifier: string;
  billing_mode: BillingMode;
  bucket_name: string;
  domain_name: string;
  is_active: boolean;
  provider_code: ProviderCode;
  scope_type: BindingScopeType;
  tag_key: string;
  tag_value: string;
  tenant_id: null | number;
};

const props = defineProps<{
  bindingLoading: boolean;
  clearScopeFields: (scopeType: BindingScopeType) => void;
  currentModeOptions: Array<{ label: string; value: BillingMode }>;
  currentScopeOptions: Array<{ label: string; value: BindingScopeType }>;
  form: BindingFormState;
  handleProviderChange: (code: ProviderCode) => void;
  modalOkText: string;
  modalTitle: string;
  open: boolean;
  providerOptions: Array<{ label: string; value: ProviderCode }>;
  resetForm: () => void;
  searchTenants: (keyword: string) => void | Promise<void>;
  submitBinding: () => void | Promise<void>;
  tenants: Array<{ label: string; value: number }>;
}>();

const emit = defineEmits<{
  'update:open': [value: boolean];
}>();

function handleCancel(): void {
  props.resetForm();
  emit('update:open', false);
}
</script>

<template>
  <Modal
    :confirm-loading="props.bindingLoading"
    :ok-text="props.modalOkText"
    :open="props.open"
    :title="props.modalTitle"
    @cancel="handleCancel"
    @ok="props.submitBinding"
  >
    <Form layout="vertical">
      <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.tenant')">
        <Select
          v-model:value="props.form.tenant_id"
          :filter-option="false"
          :options="props.tenants"
          show-search
          @search="props.searchTenants"
        />
      </FormItem>
      <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.provider')">
        <Select
          v-model:value="props.form.provider_code"
          :disabled="props.providerOptions.length <= 1"
          :options="props.providerOptions"
          @change="props.handleProviderChange"
        />
      </FormItem>
      <Alert
        v-if="props.form.provider_code === 'qiniu-kodo'"
        class="block"
        :message="$t('plugin.storage-billing.admin.bindingForm.qiniuRestrictionTitle')"
        :description="$t('plugin.storage-billing.admin.bindingForm.qiniuRestrictionDesc')"
        show-icon
        type="info"
      />
      <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.mode')">
        <Select v-model:value="props.form.billing_mode" :options="props.currentModeOptions" />
      </FormItem>
      <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.scopeType')">
        <Select
          v-model:value="props.form.scope_type"
          :options="props.currentScopeOptions"
          @change="props.clearScopeFields"
        />
      </FormItem>
      <FormItem
        v-if="props.form.scope_type === 'bucket'"
        :label="$t('plugin.storage-billing.admin.bindingForm.bucketName')"
      >
        <Input
          v-model:value="props.form.bucket_name"
          :placeholder="$t('plugin.storage-billing.admin.bindingForm.scopePlaceholder.bucket')"
        />
      </FormItem>
      <FormItem
        v-if="props.form.scope_type === 'domain'"
        :label="$t('plugin.storage-billing.admin.bindingForm.domainName')"
      >
        <Input
          v-model:value="props.form.domain_name"
          :placeholder="$t('plugin.storage-billing.admin.bindingForm.scopePlaceholder.domain')"
        />
      </FormItem>
      <FormItem
        v-if="props.form.scope_type === 'account'"
        :label="$t('plugin.storage-billing.admin.bindingForm.accountIdentifier')"
      >
        <Input
          v-model:value="props.form.account_identifier"
          :placeholder="$t('plugin.storage-billing.admin.bindingForm.scopePlaceholder.account')"
        />
      </FormItem>
      <template v-if="props.form.scope_type === 'tag'">
        <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.tagKey')">
          <Input
            v-model:value="props.form.tag_key"
            :placeholder="$t('plugin.storage-billing.admin.bindingForm.scopePlaceholder.tagKey')"
          />
        </FormItem>
        <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.tagValue')">
          <Input
            v-model:value="props.form.tag_value"
            :placeholder="$t('plugin.storage-billing.admin.bindingForm.scopePlaceholder.tagValue')"
          />
        </FormItem>
      </template>
      <FormItem :label="$t('plugin.storage-billing.admin.bindingForm.isActive')">
        <Switch v-model:checked="props.form.is_active" />
      </FormItem>
    </Form>
  </Modal>
</template>
