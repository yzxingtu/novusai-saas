<script lang="ts" setup>
/**
 * 创建租户子管理员表单（Drawer）
 *
 * 从租户列表的管理员展开面板中调用。
 */
import type { TenantAdminItem } from '#/api/admin/tenant';

import { ref } from 'vue';

import { Button, Drawer, Form, FormItem, Input, message } from 'ant-design-vue';

import { createTenantAdminApi, updateTenantAdminApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

defineOptions({ name: 'TenantAdminForm' });

const emit = defineEmits<{ success: [] }>();

const visible = ref(false);
const loading = ref(false);
const tenantId = ref(0);
const tenantName = ref('');

const editingAdmin = ref<null | TenantAdminItem>(null);
const isEdit = ref(false);

const form = ref({
  username: '',
  email: '',
  password: '',
  nickname: '',
});

/** 打开表单（创建或编辑） */
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
    };
  } else {
    isEdit.value = false;
    editingAdmin.value = null;
    form.value = { username: '', email: '', password: '', nickname: '' };
  }
  visible.value = true;
}

/** 关闭表单 */
function close() {
  visible.value = false;
}

/** 提交 */
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
      });
      message.success($t('common.saveSuccess'));
    } else {
      await createTenantAdminApi(tenantId.value, {
        username: form.value.username,
        email: form.value.email,
        password: form.value.password,
        nickname: form.value.nickname || undefined,
      });
      message.success($t('tenant_admin.created'));
    }
    visible.value = false;
    emit('success');
  } catch {
    message.error($t('common.requestFailed'));
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
