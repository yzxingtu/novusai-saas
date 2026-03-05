<script lang="ts" setup>
/**
 * AI 供应商新建/编辑表单抽屉
 */
import type { AIProviderInfo } from '#/api/admin/ai';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getAIProviderDetailApi } from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

defineOptions({ name: 'AIProviderForm' });

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<AIProviderInfo>({
  formApi,
  schema: (edit) => useFormSchema(edit),
  defaults: getFormDefaults,
  transform: (values, edit) => {
    const result: Record<string, unknown> = {
      name: values.name,
      type: values.type,
      base_url: values.base_url || null,
      description: values.description || null,
      icon: values.icon || null,
      sort_order: values.sort_order ?? 0,
      is_active: values.is_active ?? true,
    };
    if (!edit) {
      result.code = values.code;
    }
    return result;
  },
  toFormValues: (data) => {
    return {
      name: data.name,
      code: data.code,
      type: data.type,
      base_url: data.base_url,
      description: data.description,
      icon: data.icon,
      sort_order: data.sort_order,
      is_active: data.is_active,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAIProviderDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value ? $t('admin.common.edit') : $t('admin.ai.provider.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
