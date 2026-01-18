<script lang="ts" setup>
/**
 * 套餐新建/编辑表单抽屉
 */
import type { adminApi } from '#/api';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
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
    // 构建配额对象
    const quota: Record<string, any> = {};
    if (values['quota.storage_limit_gb'] !== undefined) {
      quota.storage_limit_gb = values['quota.storage_limit_gb'];
    }
    if (values['quota.max_users'] !== undefined) {
      quota.max_users = values['quota.max_users'];
    }
    if (values['quota.max_admins'] !== undefined) {
      quota.max_admins = values['quota.max_admins'];
    }
    if (values['quota.max_custom_domains'] !== undefined) {
      quota.max_custom_domains = values['quota.max_custom_domains'];
    }
    if (values['quota.allow_custom_domain'] !== undefined) {
      quota.allow_custom_domain = values['quota.allow_custom_domain'];
    }
    if (values['quota.api_calls_per_month'] !== undefined) {
      quota.api_calls_per_month = values['quota.api_calls_per_month'];
    }
    if (values['quota.max_file_size_mb'] !== undefined) {
      quota.max_file_size_mb = values['quota.max_file_size_mb'];
    }

    // 构建特性对象
    const features: Record<string, any> = {};
    if (values['features.ai_enabled'] !== undefined) {
      features.ai_enabled = values['features.ai_enabled'];
    }
    if (values['features.advanced_analytics'] !== undefined) {
      features.advanced_analytics = values['features.advanced_analytics'];
    }
    if (values['features.white_label'] !== undefined) {
      features.white_label = values['features.white_label'];
    }
    if (values['features.priority_support'] !== undefined) {
      features.priority_support = values['features.priority_support'];
    }

    return {
      code: values.code,
      name: values.name,
      description: values.description || null,
      price: values.price || null,
      billing_cycle: values.billing_cycle || 'monthly',
      sort_order: values.sort_order || 0,
      is_active: values.is_active ?? true,
      quota: Object.keys(quota).length > 0 ? quota : null,
      features: Object.keys(features).length > 0 ? features : null,
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
      // 配额字段
      'quota.storage_limit_gb': data.quota?.storageLimitGb,
      'quota.max_users': data.quota?.maxUsers,
      'quota.max_admins': data.quota?.maxAdmins,
      'quota.max_custom_domains': data.quota?.maxCustomDomains,
      'quota.allow_custom_domain': data.quota?.allowCustomDomain ?? false,
      'quota.api_calls_per_month': data.quota?.apiCallsPerMonth,
      'quota.max_file_size_mb': data.quota?.maxFileSizeMb,
      // 特性字段
      'features.ai_enabled': data.features?.aiEnabled ?? false,
      'features.advanced_analytics': data.features?.advancedAnalytics ?? false,
      'features.white_label': data.features?.whiteLabel ?? false,
      'features.priority_support': data.features?.prioritySupport ?? false,
    };
  },
  onSuccess: () => {
    emits('success');
  },
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
