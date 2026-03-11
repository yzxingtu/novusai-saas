<script lang="ts" setup>
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
  useVbenForm,
} from '#/adapter/form';
import { getSkillPackageDetailApi } from '#/api/admin/skill-packages';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getAudienceOptions } from '../data';

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
    textareaField('description', $t('admin.ai.skillPackage.description'), {
      placeholder: $t('admin.ai.skillPackage.placeholder.inputDescription'),
    }),
    {
      ...select('target_audience', $t('admin.ai.skillPackage.targetAudience'), {
        options: getAudienceOptions(),
        required: true,
      }),
      dependencies: {
        triggerFields: ['is_system'],
        disabled: (values: Record<string, unknown>) => !!values.is_system,
      },
    },
    switchField('is_recommended', $t('admin.ai.skillPackage.isRecommended'), {
      defaultValue: false,
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
    target_audience: values.target_audience ?? 'all',
    is_recommended: values.is_recommended ?? false,
    is_active: values.is_active ?? true,
    sort_order: values.sort_order ?? 0,
  }),
  toFormValues: (data: AdminSkillPackageInfo) => ({
    name: data.name,
    description: data.description,
    target_audience: data.target_audience ?? 'all',
    is_recommended: data.is_recommended ?? false,
    is_active: data.is_active,
    sort_order: data.sort_order,
    is_system: data.is_system,
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
