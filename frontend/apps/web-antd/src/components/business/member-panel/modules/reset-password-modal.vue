<script lang="ts" setup>
/**
 * 重置密码弹窗
 * 用于在成员管理面板中重置管理员密码
 */
import { ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';

import { useVbenForm } from '#/adapter/form';
import { resetAdminPasswordApi } from '#/api/admin/admin-user';
import { resetTenantAdminPasswordApi } from '#/api/tenant/admin-user';
import { $t } from '#/locales';

import { useResetPasswordSchema } from '../data';

/** 重置密码所需的最小用户信息 */
interface ResetPasswordTarget {
  id: number;
  username: string;
}

const props = withDefaults(
  defineProps<{
    /** API 前缀 */
    apiPrefix?: 'admin' | 'tenant';
  }>(),
  {
    apiPrefix: 'admin',
  },
);

const emits = defineEmits<{
  success: [];
}>();

const adminData = ref<ResetPasswordTarget>();

// 表单
const [Form, formApi] = useVbenForm({
  schema: useResetPasswordSchema(),
  showDefaultActions: false,
});

// 弹窗
const [Modal, modalApi] = useVbenModal({
  async onConfirm() {
    const { valid } = await formApi.validate();
    if (!valid) return;

    const values = await formApi.getValues();
    if (!adminData.value?.id) return;

    modalApi.lock();
    try {
      const resetApi =
        props.apiPrefix === 'tenant'
          ? resetTenantAdminPasswordApi
          : resetAdminPasswordApi;

      await resetApi(
        adminData.value.id,
        { new_password: values.new_password },
        {
          showSuccessMessage: true,
          successMessage: $t(
            'admin.system.admin.messages.resetPasswordSuccess',
          ),
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
      adminData.value = data;
      await formApi.resetForm();
    }
  },

  title: $t('admin.system.admin.resetPassword'),
});

/**
 * 打开弹窗
 * @param record 包含 id 和 username 的用户信息
 */
function open(record: ResetPasswordTarget) {
  modalApi.setData(record).open();
}

defineExpose({ open });
</script>

<template>
  <Modal>
    <div v-if="adminData" class="mb-4 text-gray-500">
      {{
        $t('admin.system.admin.messages.resetPasswordFor', {
          name: adminData.username,
        })
      }}
    </div>
    <Form />
  </Modal>
</template>
