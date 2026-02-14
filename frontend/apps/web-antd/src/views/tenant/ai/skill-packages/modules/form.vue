<script lang="ts" setup>
defineOptions({ name: 'TenantSkillPackageForm' });
/**
 * 租户端技能包新建/编辑表单抽屉
 */
import type { TenantSkillPackageInfo } from '#/api/tenant/skill-packages';

import { computed } from 'vue';

import {
  inputField,
  numberField,
  switchField,
  textareaField,
} from '#/adapter/form';
import { useVbenForm } from '#/adapter/form';
import { getSkillPackageDetailApi } from '#/api/tenant/skill-packages';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

const emits = defineEmits<{ success: [] }>();

function useFormSchema() {
  return [
    inputField('name', $t('tenant.ai.skillPackage.name'), {
      required: true,
      placeholder: $t('tenant.ai.skillPackage.placeholder.inputName'),
    }),
    textareaField('description', $t('tenant.ai.skillPackage.description'), {
      placeholder: $t('tenant.ai.skillPackage.placeholder.inputDescription'),
    }),
    switchField('is_active', $t('tenant.ai.skillPackage.isActive'), {
      defaultValue: true,
    }),
    numberField('sort_order', $t('tenant.ai.skillPackage.sortOrder'), {
      min: 0,
      defaultValue: 0,
    }),
  ];
}

function getFormDefaults(): Record<string, unknown> {
  return {
    is_active: true,
    sort_order: 0,
  };
}

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<TenantSkillPackageInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  apiPath: '/tenant/ai/skill-packages',
  transform: (values) => {
    return {
      name: values.name,
      description: values.description || null,
      is_active: values.is_active ?? true,
      sort_order: values.sort_order ?? 0,
    };
  },
  toFormValues: (data: TenantSkillPackageInfo) => ({
    name: data.name,
    description: data.description,
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
    ? $t('tenant.common.edit')
    : $t('tenant.ai.skillPackage.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[500px]">
    <Form />
  </Drawer>
</template>
