import type {
  ConfigGroupListItemMeta,
  ConfigGroupMeta,
  ConfigSubmitPayload,
} from '#/types/config';
import type { StorageDriverInfo } from '#/types/storage';
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

/** 生成 Fernet 加密密钥 */
export async function generateFernetKeyApi(
  options?: ApiRequestOptions,
): Promise<{ key: string }> {
  return await requestClient.post<{ key: string }>(
    '/admin/configs/generate-fernet-key',
    {},
    options,
  );
}

/** 测试存储连接 */
export async function testStorageConnectionApi(
  data: {
    driver: string;
    root_path?: string;
    base_url?: string;
    config?: Record<string, unknown>;
  },
  options?: ApiRequestOptions,
): Promise<{ success: boolean; errors?: string[] }> {
  return await requestClient.post<{ success: boolean; errors?: string[] }>(
    '/admin/configs/storage/test-connection',
    data,
    options,
  );
}

/** 获取可用存储驱动列表（含插件启用状态） */
export async function getStorageDriversApi(
  options?: ApiRequestOptions,
): Promise<StorageDriverInfo[]> {
  return await requestClient.get('/admin/configs/storage/drivers', options);
}

/** 获取租户存储配置 */
export async function getTenantStorageConfigApi(
  tenantId: number,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return await requestClient.get(
    `/admin/tenants/${tenantId}/storage-config`,
    options,
  );
}

/** 设置租户存储配置 */
export async function updateTenantStorageConfigApi(
  tenantId: number,
  data: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.put(
    `/admin/tenants/${tenantId}/storage-config`,
    data,
    options,
  );
}

/** 测试租户存储连接 */
export async function testTenantStorageConnectionApi(
  tenantId: number,
  data: {
    driver: string;
    root_path?: string;
    base_url?: string;
    config?: Record<string, unknown>;
  },
  options?: ApiRequestOptions,
): Promise<{ success: boolean; errors?: string[] }> {
  return await requestClient.post<{ success: boolean; errors?: string[] }>(
    `/admin/tenants/${tenantId}/storage-config/test`,
    data,
    options,
  );
}
