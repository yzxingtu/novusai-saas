<script lang="ts" setup>
/** Rate limit form (Admin) / 速率限制表单（管理端） */
import type { AIRateLimitInfo } from '#/api/admin/ai-quotas';

import { useVbenForm } from '#/adapter/form';
import { useCrudDrawer } from '#/composables';

import { getRateLimitFormDefaults, getRateLimitFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: getRateLimitFormSchema(),
  showDefaultActions: false,
});

const { Drawer, openNew, openEdit } = useCrudDrawer<AIRateLimitInfo>({
  formApi,
  apiPath: '/admin/ai/quotas/rate-limits',
  schema: () => getRateLimitFormSchema(),
  defaults: getRateLimitFormDefaults,
  transform: (values) => ({
    tenant_id: values.tenant_id,
    model_id: values.model_id,
    rpm_limit: values.rpm_limit || null,
    tpm_limit: values.tpm_limit || null,
    description: values.description || null,
    is_active: values.is_active ?? true,
  }),
  toFormValues: (data: AIRateLimitInfo) => ({
    tenant_id: data.tenant_id,
    model_id: data.model_id,
    rpm_limit: data.rpm_limit,
    tpm_limit: data.tpm_limit,
    description: data.description,
    is_active: data.is_active,
  }),
  onSuccess: () => {
    emits('success');
  },
});

function openNewWithContext(extraData?: Record<string, unknown>) {
  openNew(extraData);
}

function openEditWithContext(
  row: AIRateLimitInfo,
  extraData?: Record<string, unknown>,
) {
  openEdit(row, extraData);
}

defineExpose({
  openNew: openNewWithContext,
  openEdit: openEditWithContext,
});
</script>

<template>
  <Drawer class="w-[480px]">
    <Form />
  </Drawer>
</template>
