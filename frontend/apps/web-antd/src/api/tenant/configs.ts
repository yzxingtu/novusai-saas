import type {
  ConfigGroupListItemMeta,
  ConfigGroupMeta,
  ConfigSubmitPayload,
} from '#/types/config';
import type { StorageDriverInfo, TenantStorageStatus } from '#/types/storage';
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

/** 更新租户配置分组配置，后端期望 { configs: { key: value } } 格式 */
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

/** 测试租户存储连接（Mode 3） */
export async function testTenantStorageConnectionApi(
  data: {
    driver: string;
    root_path?: string;
    base_url?: string;
    config?: Record<string, unknown>;
  },
  options?: ApiRequestOptions,
): Promise<{ success: boolean; errors?: string[] }> {
  return await requestClient.post<{ success: boolean; errors?: string[] }>(
    '/tenant/configs/storage/test-connection',
    data,
    options,
  );
}

/** 获取租户允许的存储驱动列表 */
export async function getTenantStorageDriversApi(
  options?: ApiRequestOptions,
): Promise<StorageDriverInfo[]> {
  return await requestClient.get('/tenant/configs/storage/drivers', options);
}

/** 获取租户存储状态 */
export async function getTenantStorageStatusApi(
  options?: ApiRequestOptions,
): Promise<TenantStorageStatus> {
  return await requestClient.get('/tenant/configs/storage/status', options);
}

/** 保存租户存储配置（Mode 3） */
export async function saveTenantStorageConfigApi(
  data: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put('/tenant/configs/storage', data, options);
}

