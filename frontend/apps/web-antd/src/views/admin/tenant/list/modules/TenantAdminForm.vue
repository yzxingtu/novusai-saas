<script lang="ts" setup>
/**
 * 创建企业子管理员表单（Drawer）；从企业列表的管理员展开面板调用。
 * Create/edit tenant sub-admin form (drawer); invoked from tenant list admin panel.
 */
import type { TenantAdminItem } from '#/api/admin/tenant';

import { ref } from 'vue';

import {
  Button,
  Drawer,
  Form,
  FormItem,
  Input,
  message,
  Switch,
} from 'ant-design-vue';

import { createTenantAdminApi, updateTenantAdminApi } from '#/api/admin/tenant';
import { $t } from '#/locales';
import { useAccess } from '#/utils';
import { showRequestError } from '#/utils/error-helpers';

defineOptions({ name: 'TenantAdminForm' });

const emit = defineEmits<{ success: [] }>();

const visible = ref(false);
const loading = ref(false);
const tenantId = ref(0);
const tenantName = ref('');
const { hasAccessByCodes } = useAccess();
const canManageAi = hasAccessByCodes(['tenant_admin:manage_ai']);

const editingAdmin = ref<null | TenantAdminItem>(null);
const isEdit = ref(false);

const form = ref({
  username: '',
  email: '',
  password: '',
  nickname: '',
  ai_enabled: true,
});

/** 打开表单（创建或编辑） / Open form (create or edit) */
function open(tId: number, tName: string, admin?: TenantAdminItem) {
  tenantId.value = tId;
  tenantName.value = tName;
  if (admin) {
    isEdit.value = true;
    editingAdmin.value = admin;
    form.value = {
      username: admin.username,
      email: admin.email,
      password: '',
      nickname: admin.nickname || '',
      ai_enabled: admin.ai_enabled ?? true,
    };
  } else {
    isEdit.value = false;
    editingAdmin.value = null;
    form.value = {
      username: '',
      email: '',
      password: '',
      nickname: '',
      ai_enabled: true,
    };
  }
  visible.value = true;
}

/** 关闭表单 / Close form */
function close() {
  visible.value = false;
}

/** 提交 / Submit */
async function handleSubmit() {
  if (
    !isEdit.value &&
    (!form.value.username || !form.value.email || !form.value.password)
  ) {
    message.warning($t('admin.tenant.adminPanel.formRequired'));
    return;
  }
  if (isEdit.value && !form.value.email) {
    message.warning($t('admin.tenant.adminPanel.formRequired'));
    return;
  }

  loading.value = true;
  try {
    if (isEdit.value && editingAdmin.value) {
      await updateTenantAdminApi(tenantId.value, editingAdmin.value.id, {
        email: form.value.email,
        nickname: form.value.nickname || undefined,
        password: form.value.password || undefined,
        ...(canManageAi ? { ai_enabled: form.value.ai_enabled } : {}),
      });
      message.success($t('common.saveSuccess'));
    } else {
      await createTenantAdminApi(tenantId.value, {
        username: form.value.username,
        email: form.value.email,
        password: form.value.password,
        nickname: form.value.nickname || undefined,
        ...(canManageAi ? { ai_enabled: form.value.ai_enabled } : {}),
      });
      message.success($t('tenant_admin.created'));
    }
    visible.value = false;
    emit('success');
  } catch (error) {
    showRequestError(error, 'common.requestFailed');
  } finally {
    loading.value = false;
  }
}

defineExpose({ open });
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="
      isEdit
        ? $t('admin.tenant.adminPanel.editTitle', { name: tenantName })
        : $t('admin.tenant.adminPanel.createTitle', { name: tenantName })
    "
    :width="400"
    destroy-on-close
  >
    <Form layout="vertical">
      <FormItem
        :label="$t('admin.tenant.adminPanel.username')"
        :required="!isEdit"
      >
        <Input
          v-model:value="form.username"
          :placeholder="$t('admin.tenant.adminPanel.usernamePlaceholder')"
          :max-length="50"
          :disabled="isEdit"
        />
      </FormItem>
      <FormItem :label="$t('admin.tenant.adminPanel.email')" required>
        <Input
          v-model:value="form.email"
          :placeholder="$t('admin.tenant.adminPanel.emailPlaceholder')"
          type="email"
        />
      </FormItem>
      <FormItem
        v-if="!isEdit"
        :label="$t('admin.tenant.adminPanel.password')"
        required
      >
        <Input.Password
          v-model:value="form.password"
          :placeholder="$t('admin.tenant.adminPanel.passwordPlaceholder')"
        />
      </FormItem>
      <FormItem :label="$t('admin.tenant.adminPanel.nickname')">
        <Input
          v-model:value="form.nickname"
          :placeholder="$t('admin.tenant.adminPanel.nicknamePlaceholder')"
          :max-length="100"
        />
      </FormItem>
      <FormItem
        :label="$t('admin.tenant.adminPanel.aiConversation')"
        :extra="
          canManageAi ? undefined : $t('admin.tenant.adminPanel.aiReadonlyHelp')
        "
      >
        <Switch
          v-model:checked="form.ai_enabled"
          :checked-children="$t('shared.common.enabled')"
          :un-checked-children="$t('shared.common.disabled')"
          :disabled="!canManageAi"
        />
      </FormItem>
    </Form>
    <template #footer>
      <div class="flex justify-end gap-2">
        <Button @click="close">{{ $t('shared.common.cancel') }}</Button>
        <Button type="primary" :loading="loading" @click="handleSubmit">
          {{ $t('shared.common.confirm') }}
        </Button>
      </div>
    </template>
  </Drawer>
</template>
