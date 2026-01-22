import type {
  ConfigGroupListItemMeta,
  ConfigGroupMeta,
  ConfigSubmitPayload,
} from '#/types/config';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

/** 获取租户配置分组列表 */
export async function getTenantConfigGroupsApi(
  options?: ApiRequestOptions,
): Promise<ConfigGroupListItemMeta[]> {
  return await requestClient.get<ConfigGroupListItemMeta[]>(
    '/tenant/configs/groups',
    options,
  );
}

/** 获取租户配置分组详情（含配置项） */
export async function getTenantConfigGroupDetailApi(
  groupCode: string,
  options?: ApiRequestOptions,
): Promise<ConfigGroupMeta> {
  return await requestClient.get<ConfigGroupMeta>(
    `/tenant/configs/groups/${groupCode}`,
    options,
  );
}

/** 更新租户配置分组配置 */
export async function updateTenantConfigGroupApi(
  groupCode: string,
  configs: ConfigSubmitPayload,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `/tenant/configs/groups/${groupCode}`,
    configs,
    options,
  );
}
