/**
 * AI 配额管理 - 表单 Schema 和辅助函数（卡片布局）
 */
import type { VbenFormSchema } from '#/adapter/form';

import {
  dividerField,
  inputField,
  numberField,
  select,
  switchField,
} from '#/adapter/form';
import { getAIModelListApi } from '#/api/admin/ai';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

/**
 * 获取周期下拉选项
 */
export function getPeriodOptions() {
  return [
    { label: $t('admin.ai.quota.period_options.daily'), value: 'daily' },
    { label: $t('admin.ai.quota.period_options.monthly'), value: 'monthly' },
  ];
}

/**
 * 获取配额类型下拉选项
 */
export function getQuotaTypeOptions() {
  return [
    { label: $t('admin.ai.quota.type_options.soft'), value: 'soft' },
    { label: $t('admin.ai.quota.type_options.hard'), value: 'hard' },
  ];
}

/**
 * 获取周期文本
 */
export function getPeriodText(period: string | undefined): string {
  if (!period) return '-';
  switch (period) {
    case 'daily': {
      return $t('admin.ai.quota.period_options.daily');
    }
    case 'monthly': {
      return $t('admin.ai.quota.period_options.monthly');
    }
    default: {
      return period;
    }
  }
}

/**
 * 获取配额类型文本
 */
export function getQuotaTypeText(type: string | undefined): string {
  if (!type) return '-';
  switch (type) {
    case 'hard': {
      return $t('admin.ai.quota.type_options.hard');
    }
    case 'soft': {
      return $t('admin.ai.quota.type_options.soft');
    }
    default: {
      return type;
    }
  }
}

/**
 * 获取模型下拉选项
 */
async function getModelSelectOptions() {
  const response = await getAIModelListApi({
    'page[size]': 200,
    sort: 'name',
    'filter[is_active]': true,
  });
  return response.items.map((item) => ({
    label: `${item.name} (${item.provider_name || '-'})`,
    value: item.id,
  }));
}

/**
 * 表单 Schema
 */
export function useFormSchema(): VbenFormSchema[] {
  return [
    dividerField('basic_divider', $t('admin.ai.quota.section.basic')),
    select('tenant_id', $t('admin.ai.quota.tenantId'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      required: true,
      placeholder: $t('admin.ai.quota.placeholder.selectTenant'),
    }),
    select('model_id', $t('admin.ai.quota.modelId'), {
      api: getModelSelectOptions,
      placeholder: $t('admin.ai.quota.placeholder.selectModel'),
    }),

    dividerField('config_divider', $t('admin.ai.quota.section.config')),
    select('period', $t('admin.ai.quota.period'), {
      options: getPeriodOptions(),
      required: true,
      placeholder: $t('admin.ai.quota.placeholder.selectPeriod'),
    }),
    numberField('limit', $t('admin.ai.quota.limit'), {
      required: true,
      min: 1,
      placeholder: $t('admin.ai.quota.placeholder.inputLimit'),
    }),
    select('quota_type', $t('admin.ai.quota.quotaType'), {
      options: getQuotaTypeOptions(),
      required: true,
      placeholder: $t('admin.ai.quota.placeholder.selectType'),
    }),
    numberField('warning_threshold', $t('admin.ai.quota.warningThreshold'), {
      min: 0,
      max: 100,
      placeholder: $t('admin.ai.quota.placeholder.inputThreshold'),
    }),
    inputField('description', $t('admin.ai.quota.description'), {
      placeholder: $t('admin.ai.quota.placeholder.inputDescription'),
    }),
    switchField('is_active', $t('admin.ai.quota.isActive'), {
      defaultValue: true,
    }),
  ];
}

/**
 * 表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    period: 'monthly',
    quota_type: 'soft',
    warning_threshold: 80,
    is_active: true,
  };
}

// ============================================================
// 速率限制 Schema
// ============================================================

/**
 * 速率限制表单 Schema
 */
export function getRateLimitFormSchema(): VbenFormSchema[] {
  return [
    select('tenant_id', $t('admin.ai.rateLimit.tenantId'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      required: true,
      placeholder: $t('admin.ai.rateLimit.placeholder.selectTenant'),
    }),
    select('model_id', $t('admin.ai.rateLimit.modelId'), {
      api: getModelSelectOptions,
      required: true,
      placeholder: $t('admin.ai.rateLimit.placeholder.selectModel'),
    }),
    numberField('rpm_limit', $t('admin.ai.rateLimit.rpmLimit'), {
      min: 0,
      placeholder: $t('admin.ai.rateLimit.placeholder.inputRpm'),
    }),
    numberField('tpm_limit', $t('admin.ai.rateLimit.tpmLimit'), {
      min: 0,
      placeholder: $t('admin.ai.rateLimit.placeholder.inputTpm'),
    }),
    inputField('description', $t('admin.ai.rateLimit.description'), {
      placeholder: $t('admin.ai.rateLimit.placeholder.inputDescription'),
    }),
    switchField('is_active', $t('admin.ai.rateLimit.isActive'), {
      defaultValue: true,
    }),
  ];
}

/**
 * 速率限制表单默认值
 */
export function getRateLimitFormDefaults(): Record<string, unknown> {
  return {
    is_active: true,
  };
}
