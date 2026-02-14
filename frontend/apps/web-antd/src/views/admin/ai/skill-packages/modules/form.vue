<script lang="ts" setup>
defineOptions({ name: 'AdminSkillPackageForm' });
/**
 * 管理端技能包新建/编辑表单抽屉
 */
import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';

import { computed } from 'vue';

import {
  inputField,
  numberField,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { useVbenForm } from '#/adapter/form';
import { getSkillPackageDetailApi } from '#/api/admin/skill-packages';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

const isTenantScope = (v: Record<string, unknown>) => v.scope === 'tenant';

const emits = defineEmits<{ success: [] }>();

function getScopeOptions() {
  return [
    { label: $t('admin.ai.skillPackage.scope_options.admin'), value: 'admin' },
    { label: $t('admin.ai.skillPackage.scope_options.tenant'), value: 'tenant' },
    { label: $t('admin.ai.skillPackage.scope_options.global'), value: 'global' },
  ];
}

function useFormSchema() {
  return [
    inputField('name', $t('admin.ai.skillPackage.name'), {
      required: true,
      placeholder: $t('admin.ai.skillPackage.placeholder.inputName'),
    }),
    {
      ...select('scope', $t('admin.ai.skillPackage.scope'), {
        options: getScopeOptions(),
        required: true,
        placeholder: $t('admin.ai.skillPackage.placeholder.selectScope'),
      }),
      help: $t('admin.ai.skillPackage.help.scope'),
    },
    textareaField('description', $t('admin.ai.skillPackage.description'), {
      placeholder: $t('admin.ai.skillPackage.placeholder.inputDescription'),
    }),
    {
      ...select('tenant_id', $t('admin.ai.skillPackage.tenantId'), {
        api: getTenantSelectApi,
        params: { is_active: 'true' },
        required: true,
        placeholder: $t('admin.ai.skillPackage.placeholder.selectTenant'),
      }),
      dependencies: {
        triggerFields: ['scope'],
        if: isTenantScope,
      },
    },
    switchField('is_active', $t('admin.ai.skillPackage.isActive'), {
      defaultValue: true,
    }),
    numberField('sort_order', $t('admin.ai.skillPackage.sortOrder'), {
      min: 0,
      defaultValue: 0,
    }),
  ];
}

function getFormDefaults(): Record<string, unknown> {
  return {
    scope: 'admin',
    is_active: true,
    sort_order: 0,
  };
}

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<AdminSkillPackageInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  apiPath: '/admin/ai/skill-packages',
  transform: (values) => {
    const result: Record<string, unknown> = {
      name: values.name,
      scope: values.scope,
      description: values.description || null,
      is_active: values.is_active ?? true,
      sort_order: values.sort_order ?? 0,
    };
    if (values.scope === 'tenant') {
      result.tenant_id = values.tenant_id;
    }
    return result;
  },
  toFormValues: (data: AdminSkillPackageInfo) => ({
    name: data.name,
    scope: data.scope,
    description: data.description,
    tenant_id: data.tenant_id,
    is_active: data.is_active,
    sort_order: data.sort_order,
  }),
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getSkillPackageDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value
    ? $t('admin.common.edit')
    : $t('admin.ai.skillPackage.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[500px]">
    <Form />
  </Drawer>
</template>
