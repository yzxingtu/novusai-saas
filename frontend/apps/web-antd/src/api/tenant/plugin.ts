/**
 * 租户端插件 API
 */
import { requestClient } from '#/utils/request';

import type { PluginSlotData, PluginSlotsResponse } from '#/api/admin/plugin';

const BASE_URL = '/tenant/plugins';

export function getTenantPluginSlotsApi() {
  return requestClient.get<PluginSlotsResponse>(`${BASE_URL}/slots`);
}

export type { PluginSlotData, PluginSlotsResponse };
