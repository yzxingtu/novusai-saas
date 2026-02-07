import type {
  ConfigGroupListItemMeta,
  ConfigGroupMeta,
  ConfigSubmitPayload,
} from '#/types/config';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

/** 获取平台配置分组列表 */
export async function getAdminConfigGroupsApi(
  options?: ApiRequestOptions,
): Promise<ConfigGroupListItemMeta[]> {
  return await requestClient.get<ConfigGroupListItemMeta[]>(
    '/admin/configs/groups',
    options,
  );
}

/** 获取平台配置分组详情（含配置项） */
export async function getAdminConfigGroupDetailApi(
  groupCode: string,
  options?: ApiRequestOptions,
): Promise<ConfigGroupMeta> {
  return await requestClient.get<ConfigGroupMeta>(
    `/admin/configs/groups/${groupCode}`,
    options,
  );
}

/** 更新平台配置分组配置，后端期望 { configs: { key: value } } 格式 */
export async function updateAdminConfigGroupApi(
  groupCode: string,
  configs: ConfigSubmitPayload,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `/admin/configs/groups/${groupCode}`,
    { configs },
    options,
  );
}
