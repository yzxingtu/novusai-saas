import type {
  ConfigGroupListItemMeta,
  ConfigGroupMeta,
  ConfigSubmitPayload,
} from '#/types/config';
import type { StorageDriverInfo, TenantStorageStatus } from '#/types/storage';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

/** Get tenant config group list / 获取租户配置分组列表 */
export async function getTenantConfigGroupsApi(
  options?: ApiRequestOptions,
): Promise<ConfigGroupListItemMeta[]> {
  return await requestClient.get<ConfigGroupListItemMeta[]>(
    '/tenant/configs/groups',
    options,
  );
}

/** Get tenant config group detail (with config items) / 获取租户配置分组详情 */
export async function getTenantConfigGroupDetailApi(
  groupCode: string,
  options?: ApiRequestOptions,
): Promise<ConfigGroupMeta> {
  return await requestClient.get<ConfigGroupMeta>(
    `/tenant/configs/groups/${groupCode}`,
    options,
  );
}

/** Update tenant config group, backend expects { configs: { key: value } } / 更新租户配置分组 */
export async function updateTenantConfigGroupApi(
  groupCode: string,
  configs: ConfigSubmitPayload,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `/tenant/configs/groups/${groupCode}`,
    { configs },
    options,
  );
}

/** Test tenant storage connection (Mode 3) / 测试租户存储连接 */
export async function testTenantStorageConnectionApi(
  data: {
    base_url?: string;
    config?: Record<string, unknown>;
    driver: string;
    root_path?: string;
  },
  options?: ApiRequestOptions,
): Promise<{ errors?: string[]; success: boolean }> {
  return await requestClient.post<{ errors?: string[]; success: boolean }>(
    '/tenant/configs/storage/test-connection',
    data,
    options,
  );
}

/** Get tenant allowed storage drivers / 获取租户允许的存储驱动列表 */
export async function getTenantStorageDriversApi(
  options?: ApiRequestOptions,
): Promise<StorageDriverInfo[]> {
  return await requestClient.get('/tenant/configs/storage/drivers', options);
}

/** Get tenant storage status / 获取租户存储状态 */
export async function getTenantStorageStatusApi(
  options?: ApiRequestOptions,
): Promise<TenantStorageStatus> {
  return await requestClient.get('/tenant/configs/storage/status', options);
}

/** Save tenant storage config (Mode 3) / 保存租户存储配置 */
export async function saveTenantStorageConfigApi(
  data: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put('/tenant/configs/storage', data, options);
}
