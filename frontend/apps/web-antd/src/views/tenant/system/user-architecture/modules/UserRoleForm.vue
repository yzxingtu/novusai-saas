<script lang="ts" setup>
import type { TenantUserRoleInfo } from '#/api/tenant/tenant-user-roles';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getTenantUserRoleDetailApi } from '#/api/tenant/tenant-user-roles';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getRoleFormDefaults, useRoleFormSchema } from '../data';

defineOptions({ name: 'UserArchitectureRoleForm' });

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useRoleFormSchema(false),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<TenantUserRoleInfo>({
  formApi,
  schema: useRoleFormSchema,
  defaults: getRoleFormDefaults,
  fields: ['name', 'code', 'description', 'sort_order', 'is_active'],
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getTenantUserRoleDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value
    ? $t('tenant.system.userRole.edit')
    : $t('tenant.system.userRole.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
