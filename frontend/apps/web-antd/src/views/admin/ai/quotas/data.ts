/**
 * AI 配额管理 - 表单 Schema 和诊断辅助函数
 */
import type { VbenFormSchema } from '#/adapter/form';

import {
  dividerField,
  inputField,
  numberField,
  select,
  switchField,
} from '#/adapter/form';
import { getAIModelSelectApi } from '#/api/admin/ai-models';
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
 * 获取运行时状态文案
 */
export function getRuntimeStatusText(status: string | undefined): string {
  switch (status) {
    case 'exceeded': {
      return $t('admin.ai.quota.runtimeStatus.exceeded');
    }
    case 'healthy': {
      return $t('admin.ai.quota.runtimeStatus.healthy');
    }
    case 'inactive': {
      return $t('admin.ai.quota.runtimeStatus.inactive');
    }
    case 'warning': {
      return $t('admin.ai.quota.runtimeStatus.warning');
    }
    default: {
      return status || '-';
    }
  }
}

/**
 * 获取运行时状态颜色
 */
export function getRuntimeStatusColor(status: string | undefined): string {
  switch (status) {
    case 'exceeded': {
      return 'error';
    }
    case 'healthy': {
      return 'success';
    }
    case 'warning': {
      return 'warning';
    }
    default: {
      return 'default';
    }
  }
}

/**
 * 获取配额范围文案
 */
export function getScopeTypeText(scopeType: string | undefined): string {
  switch (scopeType) {
    case 'global': {
      return $t('admin.ai.quota.scopeType.global');
    }
    case 'model': {
      return $t('admin.ai.quota.scopeType.model');
    }
    default: {
      return scopeType || '-';
    }
  }
}

/**
 * 获取状态过滤选项
 */
export function getActiveStateOptions() {
  return [
    { label: $t('admin.common.enabled'), value: 'true' },
    { label: $t('admin.common.disabled'), value: 'false' },
  ];
}

/**
 * 获取来源文案
 */
export function getSourceText(source: string | undefined): string {
  switch (source) {
    case 'model': {
      return $t('admin.ai.rateLimit.source.model');
    }
    case 'none': {
      return $t('admin.ai.rateLimit.source.none');
    }
    case 'tenant': {
      return $t('admin.ai.rateLimit.source.tenant');
    }
    default: {
      return source || '-';
    }
  }
}

/**
 * 获取来源颜色
 */
export function getSourceColor(source: string | undefined): string {
  switch (source) {
    case 'model': {
      return 'geekblue';
    }
    case 'tenant': {
      return 'blue';
    }
    default: {
      return 'default';
    }
  }
}

/**
 * 格式化百分比
 */
export function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return '0%';
  return `${value.toFixed(value >= 10 ? 0 : 1)}%`;
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
      api: getAIModelSelectApi,
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

function mergeAiFormSchemas(...groups: VbenFormSchema[][]): VbenFormSchema[] {
  const fieldMap = new Map<string, VbenFormSchema>();

  for (const group of groups) {
    for (const schema of group) {
      const fieldName = schema.fieldName as string | undefined;
      if (!fieldName) continue;
      if (!fieldMap.has(fieldName)) {
        fieldMap.set(fieldName, schema);
      }
    }
  }

  return [...fieldMap.values()];
}

// ============================================================
// Rate limit Schema / 速率限制 Schema
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
      api: getAIModelSelectApi,
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

export function useQuotaPageAiFormSchema(): VbenFormSchema[] {
  return mergeAiFormSchemas(useFormSchema(), getRateLimitFormSchema());
}
