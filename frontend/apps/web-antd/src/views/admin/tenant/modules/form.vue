<script lang="ts" setup>
/**
 * 租户新建/编辑表单抽屉
 */
import type { adminApi } from '#/api';

import { computed, onMounted } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getTenantPlanSelectApi } from '#/api/admin/plan';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { useFormSchema } from '../data';

type TenantInfo = adminApi.TenantInfo;

const emits = defineEmits<{ success: [] }>();

// 表单
const [Form, formApi] = useVbenForm({
  schema: useFormSchema(false),
  showDefaultActions: false,
});

// 加载套餐选项
onMounted(async () => {
  try {
    const plans = await getTenantPlanSelectApi({ is_active: 'true' });
    const options = plans.map((p) => ({
      label: p.name,
      value: p.id,
    }));
    // 更新表单 schema 中的套餐选项
    formApi.updateSchema([
      {
        fieldName: 'plan_id',
        componentProps: {
          options,
        },
      },
    ]);
  } catch (error) {
    console.error('Failed to load plan options:', error);
  }
});

// CRUD 抽屉
const { Drawer, isEdit } = useCrudDrawer<TenantInfo>({
  formApi,
  schema: useFormSchema,
  transform: (values) => ({
    name: values.name,
    contact_name: values.contact_name || null,
    contact_phone: values.contact_phone || null,
    contact_email: values.contact_email || null,
    plan_id: values.plan_id || null,
    expires_at: values.expires_at || null,
    remark: values.remark || null,
  }),
  toFormValues: (data) => ({
    code: data.code,
    name: data.name,
    contact_name: data.contactName,
    contact_phone: data.contactPhone,
    contact_email: data.contactEmail,
    plan_id: data.planId,
    expires_at: data.expiresAt,
    remark: data.remark,
  }),
  onSuccess: () => emits('success'),
});

const title = computed(() =>
  isEdit.value ? $t('admin.tenant.edit') : $t('admin.tenant.create'),
);
</script>

<template>
  <Drawer :title="title">
    <Form />
  </Drawer>
</template>
