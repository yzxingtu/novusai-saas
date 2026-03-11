<script lang="ts" setup>
/**
 * Reset Password Modal
 * 重置密码弹窗
 *
 * Used to reset admin password in the member management panel.
 * 用于在成员管理面板中重置管理员密码。
 */
import { ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';

import { message } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { adminApi, tenantApi } from '#/api';
import { $t } from '#/locales';

import { useResetPasswordSchema } from '../data';

/** Minimum user info required for password reset / 重置密码所需的最小用户信息 */
interface ResetPasswordTarget {
  id: number;
  username: string;
  roleId?: number;
}

const props = withDefaults(
  defineProps<{
    /** API prefix / API 前缀 */
    apiPrefix?: 'admin' | 'tenant';
    /** Role ID (required for org API calls) / 角色 ID */
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
    if (!adminData.value?.id) return;

    modalApi.lock();
    try {
      const { new_password } = values;
      const adminId = adminData.value.id;
      // Prefer passed roleId (member's role), fallback to props.roleId (current selected node) / 优先使用传入的 roleId
      const roleId = adminData.value.roleId ?? props.roleId;

      const options = {
        showSuccessMessage: true,
        successMessage: $t('admin.system.admin.messages.resetPasswordSuccess'),
      };

      if (props.apiPrefix === 'tenant') {
        // Tenant side (requires roleId) / 租户端（目前需要 roleId）
        // Note: When called from member panel, roleId should be passed via props. / 注意：从成员面板调用时，roleId 应由 props 传入
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
          // Stop execution and keep modal open (choose not to throw, but logic is interrupted) / 停止执行并保持弹窗打开
          modalApi.unlock();
          return;
        }
      } else {
        // Platform side / 平台端
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
 * Open modal / 打开弹窗
 * @param record User info containing id and username / 包含 id 和 username 的用户信息
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
