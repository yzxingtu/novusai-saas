<script lang="ts" setup>
defineOptions({ name: 'TenantAIApiKeyForm' });
/**
 * 租户端创建 API Key 弹窗表单
 */
import { useVbenForm } from '#/adapter/form';
import { $t } from '#/locales';

import { useCreateFormSchema } from '../data';

const open = defineModel<boolean>('open', { default: false });
const emits = defineEmits<{ submit: [values: Record<string, unknown>] }>();

const [Form, formApi] = useVbenForm({
  schema: useCreateFormSchema(),
  showDefaultActions: false,
});

async function handleOk() {
  const { valid, values } = await formApi.validate();
  if (valid && values) {
    emits('submit', values as Record<string, unknown>);
    await formApi.resetForm();
  }
}

function handleCancel() {
  open.value = false;
  formApi.resetForm();
}
</script>

<template>
  <a-modal
    v-model:open="open"
    :title="$t('tenant.ai.apiKey.create')"
    :ok-text="$t('common.confirm')"
    :cancel-text="$t('common.cancel')"
    width="500px"
    destroy-on-close
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <Form class="pt-4" />
  </a-modal>
</template>
