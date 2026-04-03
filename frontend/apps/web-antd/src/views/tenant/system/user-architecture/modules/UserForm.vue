<script lang="ts" setup>
import type { TenantUserInfo } from '#/api/tenant/tenant-users';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getTenantOrganizationTreeApi } from '#/api/tenant/organization';
import { getTenantUserRoleListApi } from '#/api/tenant/tenant-user-roles';
import { getTenantUserDetailApi } from '#/api/tenant/tenant-users';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import {
  getUserFormDefaults,
  toOrganizationTreeSelectOptions,
  useUserFormSchema,
} from '../data';

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
    'org_node_id',
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
      const [roleResponse, orgTree] = await Promise.all([
        getTenantUserRoleListApi({
          'page[size]': 100,
          'filter[is_active][eq]': true,
        }),
        getTenantOrganizationTreeApi(),
      ]);

      const roleOptions = roleResponse.items.map((role) => ({
        label: role.name,
        value: role.id,
      }));
      const orgOptions = toOrganizationTreeSelectOptions(orgTree);

      const updatedSchema = useUserFormSchema(isEdit.value).map((item) => {
        if (item.fieldName === 'role_id' && item.componentProps) {
          return {
            ...item,
            componentProps: {
              ...item.componentProps,
              options: roleOptions,
            },
          };
        }

        if (item.fieldName === 'org_node_id' && item.componentProps) {
          return {
            ...item,
            componentProps: {
              ...item.componentProps,
              treeData: orgOptions,
            },
          };
        }

        return item;
      });

      api.setState({ schema: updatedSchema });
    } catch {
      // Error handled by request client / 错误由请求拦截器处理
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
