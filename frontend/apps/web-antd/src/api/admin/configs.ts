/**
 * Platform config management API / 平台配置管理 API
 * Backend: /admin/configs/*
 */
import type {
  ConfigGroupListItemMeta,
  ConfigGroupMeta,
  ConfigSubmitPayload,
} from '#/types/config';
import type { StorageDriverInfo } from '#/types/storage';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

/** Get platform config group list / 获取平台配置分组列表 */
export async function getAdminConfigGroupsApi(
  options?: ApiRequestOptions,
): Promise<ConfigGroupListItemMeta[]> {
  return await requestClient.get<ConfigGroupListItemMeta[]>(
    '/admin/configs/groups',
    options,
  );
}

/** Get platform config group detail (with config items) / 获取平台配置分组详情 */
export async function getAdminConfigGroupDetailApi(
  groupCode: string,
  options?: ApiRequestOptions,
): Promise<ConfigGroupMeta> {
  return await requestClient.get<ConfigGroupMeta>(
    `/admin/configs/groups/${groupCode}`,
    options,
  );
}

/** Update platform config group, backend expects { configs: { key: value } } format / 更新平台配置分组配置 */
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

/** Generate Fernet encryption key / 生成 Fernet 加密密钥 */
export async function generateFernetKeyApi(
  options?: ApiRequestOptions,
): Promise<{ key: string }> {
  return await requestClient.post<{ key: string }>(
    '/admin/configs/generate-fernet-key',
    {},
    options,
  );
}

/** Test storage connection / 测试存储连接 */
export async function testStorageConnectionApi(
  data: {
    base_url?: string;
    config?: Record<string, unknown>;
    driver: string;
    root_path?: string;
  },
  options?: ApiRequestOptions,
): Promise<{ errors?: string[]; success: boolean }> {
  return await requestClient.post<{ errors?: string[]; success: boolean }>(
    '/admin/configs/storage/test-connection',
    data,
    options,
  );
}

/** Get available storage drivers (with plugin enable status) / 获取可用存储驱动列表 */
export async function getStorageDriversApi(
  options?: ApiRequestOptions,
): Promise<StorageDriverInfo[]> {
  return await requestClient.get('/admin/configs/storage/drivers', options);
}

/** Get tenant storage config / 获取租户存储配置 */
export async function getTenantStorageConfigApi(
  tenantId: number,
  options?: ApiRequestOptions,
): Promise<Record<string, unknown>> {
  return await requestClient.get(
    `/admin/tenants/${tenantId}/storage-config`,
    options,
  );
}

/** Set tenant storage config / 设置租户存储配置 */
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

/** Test tenant storage connection / 测试租户存储连接 */
export async function testTenantStorageConnectionApi(
  tenantId: number,
  data: {
    base_url?: string;
    config?: Record<string, unknown>;
    driver: string;
    root_path?: string;
  },
  options?: ApiRequestOptions,
): Promise<{ errors?: string[]; success: boolean }> {
  return await requestClient.post<{ errors?: string[]; success: boolean }>(
    `/admin/tenants/${tenantId}/storage-config/test`,
    data,
    options,
  );
}
