<script lang="ts" setup>
/**
 * 企业配额新建/编辑表单抽屉
 */
import type { TenantQuotaInfo } from '#/api/tenant/ai';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getTenantQuotaDetailApi } from '#/api/tenant/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getQuotaFormDefaults, useQuotaFormSchema } from '../data';

defineOptions({ name: 'TenantQuotaForm' });

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useQuotaFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit, openNew, openEdit } = useCrudDrawer<TenantQuotaInfo>({
  formApi,
  schema: useQuotaFormSchema,
  defaults: getQuotaFormDefaults,
  apiPath: '/tenant/ai/quotas',
  transform: (values) => {
    return {
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
  detailApi: async (id) => {
    const detail = await getTenantQuotaDetailApi(id as number);
    return detail.quota;
  },
});

defineExpose({ openNew, openEdit });

const title = computed(() =>
  isEdit.value ? $t('common.edit') : $t('tenant.ai.quota.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
