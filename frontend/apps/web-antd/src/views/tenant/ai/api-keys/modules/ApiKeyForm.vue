<script lang="ts" setup>
/**
 * 租户端创建 API Key 弹窗表单
 */
import { Modal } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { $t } from '#/locales';

import { useCreateFormSchema } from '../data';

defineOptions({ name: 'TenantAIApiKeyForm' });

const emits = defineEmits<{ submit: [values: Record<string, unknown>] }>();
const open = defineModel<boolean>('open', { default: false });
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
  <Modal
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
  </Modal>
</template>
