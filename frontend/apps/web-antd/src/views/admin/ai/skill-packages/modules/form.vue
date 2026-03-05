<script lang="ts" setup>
/**
 * 管理端技能包新建/编辑表单抽屉
 */
import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';

import { computed } from 'vue';

import {
  inputField,
  numberField,
  switchField,
  textareaField,
  useVbenForm,
} from '#/adapter/form';
import { getSkillPackageDetailApi } from '#/api/admin/skill-packages';
import {
  extractScopePayload,
  useScopeFields,
} from '#/components/business/scope-select';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

defineOptions({ name: 'AdminSkillPackageForm' });

const emits = defineEmits<{ success: [] }>();

function useFormSchema() {
  return [
    {
      component: 'Alert',
      fieldName: '_create_guide',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'info',
        showIcon: true,
        banner: true,
        message: $t('admin.ai.skillPackage.createGuide'),
      },
      dependencies: {
        triggerFields: ['_mode'],
        if: (values: Record<string, unknown>) => values._mode !== 'edit',
      },
    },
    inputField('name', $t('admin.ai.skillPackage.name'), {
      required: true,
      placeholder: $t('admin.ai.skillPackage.placeholder.inputName'),
    }),
    ...useScopeFields({
      scopeHelp: $t('admin.ai.skillPackage.help.scope'),
      scopeDisabled: (values: Record<string, unknown>) =>
        values._mode === 'edit',
    }),
    textareaField('description', $t('admin.ai.skillPackage.description'), {
      placeholder: $t('admin.ai.skillPackage.placeholder.inputDescription'),
    }),
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
    scope: 'admin_only',
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
  transform: (values) => ({
    name: values.name,
    description: values.description || null,
    is_active: values.is_active ?? true,
    sort_order: values.sort_order ?? 0,
    ...extractScopePayload(values),
  }),
  toFormValues: (data: AdminSkillPackageInfo) => ({
    name: data.name,
    description: data.description,
    is_active: data.is_active,
    sort_order: data.sort_order,
    scope: data.scope,
    tenant_id: data.tenant_id ?? null,
    tenant_ids: data.assigned_tenant_ids ?? [],
  }),
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getSkillPackageDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value ? $t('admin.common.edit') : $t('admin.ai.skillPackage.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[500px]">
    <Form />
  </Drawer>
</template>
