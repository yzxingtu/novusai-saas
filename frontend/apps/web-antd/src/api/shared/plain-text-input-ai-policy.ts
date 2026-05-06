import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

export interface PlainTextInputAiPolicy {
  account_ai_enabled?: boolean;
  ai_unavailable_reason?: null | string;
  enabled: boolean;
  personal_enabled?: boolean;
  platform_admin_enabled?: boolean;
  platform_allow_tenant_enable?: boolean;
  platform_tenant_default_enabled?: boolean;
  scope?: 'admin' | 'tenant' | string;
  surface?: string;
  tenant_enabled?: boolean;
}

export async function getPlainTextInputAiPolicyApi(
  apiPrefix: string,
  options?: ApiRequestOptions,
): Promise<PlainTextInputAiPolicy> {
  return await requestClient.get<PlainTextInputAiPolicy>(
    `${apiPrefix}/ai/plain-text-input/policy`,
    options,
  );
}
