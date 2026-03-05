<script lang="ts" setup>
/**
 * 租户速率限制新建/编辑表单抽屉
 */
import type { TenantRateLimitInfo } from '#/api/tenant/ai';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getRateLimitFormDefaults, useRateLimitFormSchema } from '../data';

defineOptions({ name: 'TenantRateLimitForm' });

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useRateLimitFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit, openNew, openEdit } =
  useCrudDrawer<TenantRateLimitInfo>({
    formApi,
    schema: useRateLimitFormSchema,
    defaults: getRateLimitFormDefaults,
    apiPath: '/tenant/ai/quotas/rate-limits',
    transform: (values) => {
      return {
        model_id: values.model_id,
        rpm_limit: values.rpm_limit ?? null,
        tpm_limit: values.tpm_limit ?? null,
        description: values.description || null,
        is_active: values.is_active ?? true,
      };
    },
    toFormValues: (data) => {
      return {
        model_id: data.model_id,
        rpm_limit: data.rpm_limit,
        tpm_limit: data.tpm_limit,
        description: data.description,
        is_active: data.is_active,
      };
    },
    onSuccess: () => {
      emits('success');
    },
  });

defineExpose({ openNew, openEdit });

const title = computed(() =>
  isEdit.value ? $t('common.edit') : $t('tenant.ai.rateLimit.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
