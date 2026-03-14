<script lang="ts" setup>
/**
 * 重置企业管理员密码弹窗
 */
import { ref } from 'vue';

import { Input, message, Modal } from 'ant-design-vue';

import { updateTenantAdminApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

defineOptions({ name: 'TenantAdminResetPwdModal' });

const props = defineProps<{
  tenantId: number;
}>();

const visible = ref(false);
const loading = ref(false);
const adminId = ref(0);
const adminName = ref('');
const newPassword = ref('');
const confirmPassword = ref('');

function open(id: number, name: string) {
  adminId.value = id;
  adminName.value = name;
  newPassword.value = '';
  confirmPassword.value = '';
  visible.value = true;
}

async function handleSubmit() {
  if (!newPassword.value || newPassword.value.length < 6) {
    message.warning($t('admin.tenant.validation.passwordMin'));
    return;
  }
  if (newPassword.value !== confirmPassword.value) {
    message.warning($t('admin.tenant.messages.passwordMismatch'));
    return;
  }

  loading.value = true;
  try {
    await updateTenantAdminApi(props.tenantId, adminId.value, {
      password: newPassword.value,
    });
    message.success($t('admin.tenant.messages.resetPasswordSuccess'));
    visible.value = false;
  } catch {
    message.error($t('common.requestFailed'));
  } finally {
    loading.value = false;
  }
}

defineExpose({ open });
</script>

<template>
  <Modal
    v-model:open="visible"
    :title="$t('admin.tenant.resetPassword')"
    :confirm-loading="loading"
    :ok-text="$t('shared.common.confirm')"
    :cancel-text="$t('shared.common.cancel')"
    destroy-on-close
    @ok="handleSubmit"
  >
    <div class="mb-4 text-sm text-muted-foreground">
      {{ $t('admin.tenant.messages.resetPasswordFor', { name: adminName }) }}
    </div>
    <div class="space-y-3">
      <div>
        <label class="mb-1 block text-sm font-medium">
          {{ $t('admin.tenant.newPassword') }}
        </label>
        <Input.Password
          v-model:value="newPassword"
          :placeholder="$t('admin.tenant.placeholder.inputNewPassword')"
        />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium">
          {{ $t('admin.tenant.confirmPassword') }}
        </label>
        <Input.Password
          v-model:value="confirmPassword"
          :placeholder="$t('admin.tenant.placeholder.confirmPassword')"
        />
      </div>
    </div>
  </Modal>
</template>
