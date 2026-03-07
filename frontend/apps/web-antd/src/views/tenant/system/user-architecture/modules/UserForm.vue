<script lang="ts" setup>
import type { TenantUserInfo } from '#/api/tenant/tenant-users';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getTenantUserDetailApi } from '#/api/tenant/tenant-users';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getUserFormDefaults, useUserFormSchema } from '../data';

defineOptions({ name: 'UserArchitectureUserForm' });

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useUserFormSchema(false),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<TenantUserInfo>({
  formApi,
  schema: useUserFormSchema,
  defaults: getUserFormDefaults,
  fields: [
    'username',
    'email',
    'password',
    'phone',
    'nickname',
    'role_id',
    'is_active',
  ],
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getTenantUserDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value
    ? $t('tenant.system.user.edit')
    : $t('tenant.system.user.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
