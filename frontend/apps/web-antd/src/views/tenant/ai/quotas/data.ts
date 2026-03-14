/**
 * 企业端配额管理 - 表单 Schema 和辅助函数
 */
import type { VbenFormSchema } from '#/adapter/form';

import {
  dividerField,
  inputField,
  numberField,
  select,
  switchField,
} from '#/adapter/form';
import { getTenantAIModelsApi } from '#/api/tenant/ai';
import { $t } from '#/locales';

/**
 * 获取模型下拉选项
 */
export async function getModelSelectOptions() {
  try {
    const models = await getTenantAIModelsApi();
    return models.map((m) => ({
      label: `${m.name} (${m.provider_name || '-'})`,
      value: m.id,
    }));
  } catch {
    return [];
  }
}

/**
 * 获取周期下拉选项
 */
export function getPeriodOptions() {
  return [
    { label: $t('tenant.ai.quota.period_options.daily'), value: 'daily' },
    { label: $t('tenant.ai.quota.period_options.monthly'), value: 'monthly' },
  ];
}

/**
 * 获取配额类型下拉选项
 */
export function getQuotaTypeOptions() {
  return [
    { label: $t('tenant.ai.quota.type_options.soft'), value: 'soft' },
    { label: $t('tenant.ai.quota.type_options.hard'), value: 'hard' },
  ];
}

/**
 * 获取周期文本
 */
export function getPeriodText(period: string | undefined): string {
  if (!period) return '-';
  switch (period) {
    case 'daily': {
      return $t('tenant.ai.quota.period_options.daily');
    }
    case 'monthly': {
      return $t('tenant.ai.quota.period_options.monthly');
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
      return $t('tenant.ai.quota.type_options.hard');
    }
    case 'soft': {
      return $t('tenant.ai.quota.type_options.soft');
    }
    default: {
      return type;
    }
  }
}

// ============ 配额表单 ============

/**
 * 配额表单 Schema
 */
export function useQuotaFormSchema(): VbenFormSchema[] {
  return [
    dividerField('basic_divider', $t('tenant.ai.quota.section.basic')),
    select('model_id', $t('tenant.ai.quota.modelId'), {
      api: getModelSelectOptions,
      placeholder: $t('tenant.ai.quota.placeholder.selectModel'),
    }),

    dividerField('config_divider', $t('tenant.ai.quota.section.config')),
    select('period', $t('tenant.ai.quota.period'), {
      options: getPeriodOptions(),
      required: true,
      placeholder: $t('tenant.ai.quota.placeholder.selectPeriod'),
    }),
    numberField('limit', $t('tenant.ai.quota.limit'), {
      required: true,
      min: 1,
      placeholder: $t('tenant.ai.quota.placeholder.inputLimit'),
    }),
    select('quota_type', $t('tenant.ai.quota.quotaType'), {
      options: getQuotaTypeOptions(),
      required: true,
      placeholder: $t('tenant.ai.quota.placeholder.selectType'),
    }),
    numberField('warning_threshold', $t('tenant.ai.quota.warningThreshold'), {
      min: 0,
      max: 100,
      placeholder: $t('tenant.ai.quota.placeholder.inputThreshold'),
    }),
    inputField('description', $t('tenant.ai.quota.description'), {
      placeholder: $t('tenant.ai.quota.placeholder.inputDescription'),
    }),
    switchField('is_active', $t('tenant.ai.quota.isActive'), {
      defaultValue: true,
    }),
  ];
}

/**
 * 配额表单默认值
 */
export function getQuotaFormDefaults(): Record<string, unknown> {
  return {
    period: 'monthly',
    quota_type: 'soft',
    warning_threshold: 80,
    is_active: true,
  };
}

// ============ 速率限制表单 ============

/**
 * 速率限制表单 Schema
 */
export function useRateLimitFormSchema(): VbenFormSchema[] {
  return [
    select('model_id', $t('tenant.ai.rateLimit.modelId'), {
      api: getModelSelectOptions,
      required: true,
      placeholder: $t('tenant.ai.rateLimit.placeholder.selectModel'),
    }),
    numberField('rpm_limit', $t('tenant.ai.rateLimit.rpmLimit'), {
      min: 0,
      placeholder: $t('tenant.ai.rateLimit.placeholder.inputRpm'),
    }),
    numberField('tpm_limit', $t('tenant.ai.rateLimit.tpmLimit'), {
      min: 0,
      placeholder: $t('tenant.ai.rateLimit.placeholder.inputTpm'),
    }),
    inputField('description', $t('tenant.ai.rateLimit.description'), {
      placeholder: $t('tenant.ai.rateLimit.placeholder.inputDescription'),
    }),
    switchField('is_active', $t('tenant.ai.rateLimit.isActive'), {
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

export { formatTokens } from '#/utils/format';
