<script lang="ts" setup>
import type { TenantUserInfo } from '#/api/tenant/tenant-users';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getTenantUserRoleListApi } from '#/api/tenant/tenant-user-roles';
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
  async afterOpen(api) {
    if (!api) return;
    try {
      const res = await getTenantUserRoleListApi({
        'page[size]': 100,
        'filter[is_active][eq]': true,
      });
      const roleOptions = res.items.map((r) => ({
        label: r.name,
        value: r.id,
      }));
      const currentSchema = useUserFormSchema(isEdit.value);
      const updatedSchema = currentSchema.map((item) => {
        if (item.fieldName === 'role_id' && item.componentProps) {
          return {
            ...item,
            componentProps: {
              ...item.componentProps,
              options: roleOptions,
            },
          };
        }
        return item;
      });
      api.setState({ schema: updatedSchema });
    } catch {
      // error handled by request client
    }
  },
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
