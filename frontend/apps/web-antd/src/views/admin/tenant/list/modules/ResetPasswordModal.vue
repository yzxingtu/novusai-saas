<script lang="ts" setup>
/**
 * 重置租户管理员密码弹窗
 */
import { ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';

import { useVbenForm } from '#/adapter/form';
import { resetTenantOwnerPasswordApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

import { useResetPasswordSchema } from '../data';

/** 重置密码所需的租户信息 */
interface ResetPasswordTarget {
  id: number;
  name: string;
}

const emits = defineEmits<{
  success: [];
}>();

const tenantData = ref<ResetPasswordTarget>();

// Form / 表单
const [Form, formApi] = useVbenForm({
  schema: useResetPasswordSchema(),
  showDefaultActions: false,
});

// Modal / 弹窗
const [Modal, modalApi] = useVbenModal({
  async onConfirm() {
    const { valid } = await formApi.validate();
    if (!valid) return;

    const values = await formApi.getValues();
    if (!tenantData.value?.id) return;

    modalApi.lock();
    try {
      await resetTenantOwnerPasswordApi(
        tenantData.value.id,
        { new_password: values.new_password },
        {
          showSuccessMessage: true,
          successMessage: $t('admin.tenant.messages.resetPasswordSuccess'),
        },
      );
      emits('success');
      modalApi.close();
    } catch {
      modalApi.unlock();
    }
  },

  async onOpenChange(isOpen) {
    if (isOpen) {
      const data = modalApi.getData<ResetPasswordTarget>();
      tenantData.value = data;
      await formApi.resetForm();
    }
  },

  title: $t('admin.tenant.resetPassword'),
});

/**
 * 打开弹窗
 * @param record 包含 id 和 name 的租户信息
 */
function open(record: ResetPasswordTarget) {
  modalApi.setData(record).open();
}

defineExpose({ open });
</script>

<template>
  <Modal>
    <div v-if="tenantData" class="mb-4 text-gray-500">
      {{
        $t('admin.tenant.messages.resetPasswordFor', { name: tenantData.name })
      }}
    </div>
    <Form />
  </Modal>
</template>
