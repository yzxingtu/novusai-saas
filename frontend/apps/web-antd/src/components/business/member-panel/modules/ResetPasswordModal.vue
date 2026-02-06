<script lang="ts" setup>
/**
 * 重置密码弹窗
 * 用于在成员管理面板中重置管理员密码
 */
import { ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';

import { message } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { adminApi, tenantApi } from '#/api';
import { $t } from '#/locales';

import { useResetPasswordSchema } from '../data';

/** 重置密码所需的最小用户信息 */
interface ResetPasswordTarget {
  id: number;
  username: string;
  roleId?: number;
}

const props = withDefaults(
  defineProps<{
    /** API 前缀 */
    apiPrefix?: 'admin' | 'tenant';
    /** 角色 ID（调用组织架构 API 需要） */
    roleId?: number;
  }>(),
  {
    apiPrefix: 'admin',
    roleId: undefined,
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
      const { new_password } = values;
      const adminId = adminData.value.id;
      // 优先使用传入的 roleId (成员所属角色)，否则使用 props.roleId (当前选中节点)
      const roleId = adminData.value.roleId ?? props.roleId;

      const options = {
        showSuccessMessage: true,
        successMessage: $t('admin.system.admin.messages.resetPasswordSuccess'),
      };

      if (props.apiPrefix === 'tenant') {
        // 租户端 (目前需要 roleId)
        // 注意：如果是从成员面板调用，roleId 应由 props 传入
        // 如果是从其他地方调用且没有 roleId，这个 API 可能会失败，
        // 但目前 member-panel 主要用于组织架构管理，应该都有 roleId
        if (roleId) {
          await tenantApi.resetTenantMemberPasswordApi(
            roleId,
            adminId,
            { new_password },
            options,
          );
        } else {
          message.error($t('common.error.missingRequiredParam'));
          console.error('Missing roleId for tenant member password reset');
          // 停止执行并保持弹窗打开（或者关闭？这里选择不抛出错误，但逻辑已中断）
          modalApi.unlock();
          return;
        }
      } else {
        // 平台端
        if (roleId) {
          await adminApi.resetMemberPasswordApi(
            roleId,
            adminId,
            { new_password },
            options,
          );
        } else {
          message.error($t('common.error.missingRequiredParam'));
          console.error('Missing roleId for admin member password reset');
          modalApi.unlock();
          return;
        }
      }

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
