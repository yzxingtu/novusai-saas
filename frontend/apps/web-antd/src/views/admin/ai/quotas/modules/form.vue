<script lang="ts" setup>
defineOptions({ name: 'AIQuotaForm' });
/**
 * AI 配额新建/编辑表单抽屉
 */
import type { AIQuotaInfo } from '#/api/admin/ai';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getAIQuotaDetailApi } from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<AIQuotaInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  transform: (values) => {
    return {
      tenant_id: values.tenant_id,
      model_id: values.model_id || null,
      period: values.period,
      limit: values.limit,
      quota_type: values.quota_type,
      warning_threshold: values.warning_threshold ?? null,
      description: values.description || null,
      is_active: values.is_active ?? true,
    };
  },
  toFormValues: (data) => {
    return {
      tenant_id: data.tenant_id,
      model_id: data.model_id,
      period: data.period,
      limit: data.limit,
      quota_type: data.quota_type,
      warning_threshold: data.warning_threshold,
      description: data.description,
      is_active: data.is_active,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAIQuotaDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value
    ? $t('admin.common.edit')
    : $t('admin.ai.quota.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
