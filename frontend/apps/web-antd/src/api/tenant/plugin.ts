import type { PluginSlotData, PluginSlotsResponse } from '#/api/admin/plugin';

/**
 * Tenant plugin API / 企业端插件 API
 */
import { requestClient } from '#/utils/request';

const BASE_URL = '/tenant/plugins';

export function getTenantPluginSlotsApi() {
  return requestClient.get<PluginSlotsResponse>(`${BASE_URL}/slots`);
}

export type { PluginSlotData, PluginSlotsResponse };
