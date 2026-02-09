/**
 * 租户端 API Key 管理 - 表单配置
 */
import type { VbenFormSchema } from '#/adapter/form';

import { inputField, select } from '#/adapter/form';
import { getTenantProviderSelectOptions } from '#/api/tenant/ai';
import { $t } from '#/locales';

/**
 * 创建 API Key 表单 Schema
 */
export function useCreateFormSchema(): VbenFormSchema[] {
  return [
    inputField('name', $t('tenant.ai.apiKey.name'), {
      required: true,
      placeholder: $t('tenant.ai.apiKey.placeholder.inputName'),
    }),
    select('provider_id', $t('tenant.ai.apiKey.providerId'), {
      api: getTenantProviderSelectOptions,
      required: true,
      placeholder: $t('tenant.ai.apiKey.placeholder.selectProvider'),
    }),
    inputField('api_key', $t('tenant.ai.apiKey.apiKey'), {
      required: true,
      placeholder: $t('tenant.ai.apiKey.placeholder.inputApiKey'),
    }),
  ];
}
