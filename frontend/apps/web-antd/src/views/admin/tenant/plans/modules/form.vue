<script lang="ts" setup>
/**
 * 套餐新建/编辑表单抽屉
 */
import type { adminApi } from '#/api';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getTenantPlanDetailApi } from '#/api/admin/plan';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

type TenantPlanInfo = adminApi.TenantPlanInfo;

const emits = defineEmits<{ success: [] }>();

// 表单
const [Form, formApi] = useVbenForm({
  schema: useFormSchema(false),
  showDefaultActions: false,
});

// CRUD 抽屉
const { Drawer, isEdit } = useCrudDrawer<TenantPlanInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  transform: (values) => {
    // 解构嵌套对象
    const quota = values.quota || {};
    const features = values.features || {};

    // 修正配额对象（确保数值类型正确）
    const finalQuota: Record<string, any> = {};
    if (quota.storage_limit_gb !== undefined) finalQuota.storage_limit_gb = quota.storage_limit_gb;
    if (quota.max_users !== undefined) finalQuota.max_users = quota.max_users;
    if (quota.max_admins !== undefined) finalQuota.max_admins = quota.max_admins;
    if (quota.max_custom_domains !== undefined) finalQuota.max_custom_domains = quota.max_custom_domains;
    if (quota.allow_custom_domain !== undefined) finalQuota.allow_custom_domain = quota.allow_custom_domain;
    if (quota.api_calls_per_month !== undefined) finalQuota.api_calls_per_month = quota.api_calls_per_month;
    if (quota.max_file_size_mb !== undefined) finalQuota.max_file_size_mb = quota.max_file_size_mb;

    // 修正特性对象
    const finalFeatures: Record<string, any> = {};
    if (features.ai_enabled !== undefined) finalFeatures.ai_enabled = features.ai_enabled;
    if (features.advanced_analytics !== undefined) finalFeatures.advanced_analytics = features.advanced_analytics;
    if (features.white_label !== undefined) finalFeatures.white_label = features.white_label;
    if (features.priority_support !== undefined) finalFeatures.priority_support = features.priority_support;

    return {
      code: values.code,
      name: values.name,
      description: values.description || null,
      price: values.price || null,
      billing_cycle: values.billing_cycle || 'monthly',
      sort_order: values.sort_order || 0,
      is_active: values.is_active ?? true,
      quota: Object.keys(finalQuota).length > 0 ? finalQuota : null,
      features: Object.keys(finalFeatures).length > 0 ? finalFeatures : null,
    };
  },
  toFormValues: (data) => {
    return {
      code: data.code,
      name: data.name,
      description: data.description,
      price: data.price,
      billing_cycle: data.billingCycle,
      sort_order: data.sortOrder,
      is_active: data.isActive,
      // 配额字段（嵌套结构）
      quota: {
        storage_limit_gb: data.quota?.storageLimitGb,
        max_users: data.quota?.maxUsers,
        max_admins: data.quota?.maxAdmins,
        max_custom_domains: data.quota?.maxCustomDomains,
        allow_custom_domain: data.quota?.allowCustomDomain ?? false,
        api_calls_per_month: data.quota?.apiCallsPerMonth,
        max_file_size_mb: data.quota?.maxFileSizeMb,
      },
      // 特性字段（嵌套结构）
      features: {
        ai_enabled: data.features?.aiEnabled ?? false,
        advanced_analytics: data.features?.advancedAnalytics ?? false,
        white_label: data.features?.whiteLabel ?? false,
        priority_support: data.features?.prioritySupport ?? false,
      },
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getTenantPlanDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value ? $t('admin.tenant.plan.edit') : $t('admin.tenant.plan.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
