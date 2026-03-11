/**
 * Platform tenant domain management API / 平台端租户域名管理 API
 * Backend: /admin/tenants/{tenant_id}/domains/*
 */
import type {
  DomainType,
  SslCertificateInfo,
  SslCertificateInfoRaw,
  SslStatus,
  VerificationInfo,
  VerificationStatus,
} from '#/types/domain';
import type { ApiRequestOptions } from '#/utils/request';

import { transformSslCertInfo } from '#/types/domain';
import { requestClient } from '#/utils/request';

export type {
  DomainType,
  SslCertificateInfo,
  SslStatus,
  VerificationStatus,
} from '#/types/domain';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Domain info (backend raw snake_case) / 域名信息（后端原始格式） */
export interface TenantDomainInfoRaw {
  id: number;
  tenant_id: number;
  domain: string;
  domain_type: DomainType;
  is_verified: boolean;
  is_primary: boolean;
  ssl_status: SslStatus;
  cname_target?: string;
  txt_record?: string;
  verification_token?: null | string;
  verification_info?: null | VerificationInfo;
  verified_at?: null | string;
  ssl_expires_at?: string;
  remark?: string;
  created_at: string;
  updated_at: string;
}

/** Domain info (frontend camelCase) / 域名信息（前端格式） */
export interface TenantDomainInfo {
  id: number;
  tenantId: number;
  domain: string;
  domainType: DomainType;
  isPrimary: boolean;
  verificationStatus: VerificationStatus;
  sslStatus: SslStatus;
  cnameTarget?: string;
  txtRecord?: string;
  verificationToken?: null | string;
  verificationInfo?: null | VerificationInfo;
  verifiedAt?: string;
  sslExpiresAt?: string;
  remark?: string;
  createdAt: string;
  updatedAt: string;
}

/** Create domain request / 创建域名请求 */
export interface TenantDomainCreateRequest {
  /** Domain (e.g. app.example.com) / 域名 */
  domain: string;
  /** Set as primary domain / 是否设为主域名 */
  is_primary?: boolean;
  /** Remark / 备注 */
  remark?: null | string;
}

/** Update domain request / 更新域名请求 */
export interface TenantDomainUpdateRequest {
  /** Set as primary domain / 是否设为主域名 */
  is_primary?: boolean | null;
  /** Remark / 备注 */
  remark?: null | string;
}

/** Domain list response / 域名列表响应 */
export interface TenantDomainListResponse {
  items: TenantDomainInfo[];
  total: number;
}

export type DevHostsStatus =
  | 'managed_present'
  | 'manual_present'
  | 'missing'
  | 'not_required'
  | 'unsupported';

/** Dev Hosts runtime info (backend raw snake_case) / Dev Hosts 运行时信息（后端原始格式） */
export interface DevHostsRuntimeInfoRaw {
  enabled: boolean;
  debug: boolean;
  supported: boolean;
  os_name: string;
  hosts_path?: null | string;
  requires_elevation: boolean;
  can_write_hint: boolean;
}

/** Dev Hosts runtime info (frontend camelCase) / Dev Hosts 运行时信息（前端格式） */
export interface DevHostsRuntimeInfo {
  enabled: boolean;
  debug: boolean;
  supported: boolean;
  osName: string;
  hostsPath?: null | string;
  requiresElevation: boolean;
  canWriteHint: boolean;
}

/** Dev Hosts domain status (backend raw snake_case) / Dev Hosts 域名状态（后端原始格式） */
export interface DevHostDomainStatusRaw {
  domain_id: number;
  domain: string;
  eligible: boolean;
  status: DevHostsStatus;
  managed: boolean;
  matched_ip?: null | string;
  reason?: null | string;
}

/** Dev Hosts domain status (frontend camelCase) / Dev Hosts 域名状态（前端格式） */
export interface DevHostDomainStatus {
  domainId: number;
  domain: string;
  eligible: boolean;
  status: DevHostsStatus;
  managed: boolean;
  matchedIp?: null | string;
  reason?: null | string;
}

/** Dev Hosts overview (backend raw snake_case) / Dev Hosts 总览（后端原始格式） */
export interface DevHostsStatusResponseRaw {
  runtime: DevHostsRuntimeInfoRaw;
  domains: DevHostDomainStatusRaw[];
}

/** Dev Hosts overview (frontend camelCase) / Dev Hosts 总览（前端格式） */
export interface DevHostsStatusResponse {
  runtime: DevHostsRuntimeInfo;
  domains: DevHostDomainStatus[];
}

/** Dev Hosts mutation response (backend raw snake_case) / Dev Hosts 单项操作响应（后端原始格式） */
export interface DevHostMutationResponseRaw {
  runtime: DevHostsRuntimeInfoRaw;
  domain: DevHostDomainStatusRaw;
}

/** Dev Hosts mutation response (frontend camelCase) / Dev Hosts 单项操作响应（前端格式） */
export interface DevHostMutationResponse {
  runtime: DevHostsRuntimeInfo;
  domain: DevHostDomainStatus;
}

/** Dev Hosts batch sync response (backend raw snake_case) / Dev Hosts 批量同步响应（后端原始格式） */
export interface DevHostsSyncAllResponseRaw extends DevHostsStatusResponseRaw {
  skipped: number;
  synced: number;
}

/** Dev Hosts batch sync response (frontend camelCase) / Dev Hosts 批量同步响应（前端格式） */
export interface DevHostsSyncAllResponse extends DevHostsStatusResponse {
  skipped: number;
  synced: number;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Convert backend snake_case to frontend camelCase / 将后端转换为前端格式 */
function transformDomainInfo(raw: TenantDomainInfoRaw): TenantDomainInfo {
  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    domain: raw.domain,
    domainType: raw.domain_type || 'custom',
    isPrimary: raw.is_primary,
    verificationStatus: raw.is_verified ? 'verified' : 'pending',
    sslStatus: raw.ssl_status,
    cnameTarget: raw.cname_target,
    txtRecord: raw.txt_record,
    verificationToken: raw.verification_token,
    verificationInfo: raw.verification_info,
    verifiedAt: raw.verified_at || undefined,
    sslExpiresAt: raw.ssl_expires_at,
    remark: raw.remark,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

/** Convert Dev Hosts runtime info / 转换 Dev Hosts 运行时信息 */
function transformDevHostsRuntimeInfo(
  raw: DevHostsRuntimeInfoRaw,
): DevHostsRuntimeInfo {
  return {
    enabled: raw.enabled,
    debug: raw.debug,
    supported: raw.supported,
    osName: raw.os_name,
    hostsPath: raw.hosts_path,
    requiresElevation: raw.requires_elevation,
    canWriteHint: raw.can_write_hint,
  };
}

/** Convert Dev Hosts domain status / 转换 Dev Hosts 域名状态 */
function transformDevHostDomainStatus(
  raw: DevHostDomainStatusRaw,
): DevHostDomainStatus {
  return {
    domainId: raw.domain_id,
    domain: raw.domain,
    eligible: raw.eligible,
    status: raw.status,
    managed: raw.managed,
    matchedIp: raw.matched_ip,
    reason: raw.reason,
  };
}

/** Convert Dev Hosts overview / 转换 Dev Hosts 总览 */
function transformDevHostsStatusResponse(
  raw: DevHostsStatusResponseRaw,
): DevHostsStatusResponse {
  return {
    runtime: transformDevHostsRuntimeInfo(raw.runtime),
    domains: raw.domains.map((item) => transformDevHostDomainStatus(item)),
  };
}

/** Convert Dev Hosts mutation response / 转换 Dev Hosts 单项操作响应 */
function transformDevHostMutationResponse(
  raw: DevHostMutationResponseRaw,
): DevHostMutationResponse {
  return {
    runtime: transformDevHostsRuntimeInfo(raw.runtime),
    domain: transformDevHostDomainStatus(raw.domain),
  };
}

// ============================================================
// API functions / API 接口
// ============================================================

/**
 * Build tenant domain API prefix / 构建租户域名 API 前缀
 */
function getDomainApiPrefix(tenantId: number): string {
  return `/admin/tenants/${tenantId}/domains`;
}

/**
 * Get tenant domain list / 获取租户域名列表
 * GET /admin/tenants/{tenant_id}/domains
 */
export async function getTenantDomainsApi(
  tenantId: number,
  options?: ApiRequestOptions,
): Promise<TenantDomainListResponse> {
  const response = await requestClient.get<TenantDomainInfoRaw[]>(
    getDomainApiPrefix(tenantId),
    options,
  );

  // Backend may return array or paginated object, handle both / 后端可能返回数组或分页对象
  if (Array.isArray(response)) {
    return {
      items: response.map((item) => transformDomainInfo(item)),
      total: response.length,
    };
  }

  // If backend returns paginated format / 如果后端返回分页格式
  const pageResponse = response as unknown as {
    items: TenantDomainInfoRaw[];
    total: number;
  };
  return {
    items: pageResponse.items.map((item) => transformDomainInfo(item)),
    total: pageResponse.total,
  };
}

/**
 * Add custom domain / 添加自定义域名
 * POST /admin/tenants/{tenant_id}/domains
 */
export async function createTenantDomainApi(
  tenantId: number,
  data: TenantDomainCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantDomainInfo> {
  const raw = await requestClient.post<TenantDomainInfoRaw>(
    getDomainApiPrefix(tenantId),
    data,
    options,
  );
  return transformDomainInfo(raw);
}

/**
 * Get domain detail / 获取域名详情
 * GET /admin/tenants/{tenant_id}/domains/{domain_id}
 */
export async function getTenantDomainApi(
  tenantId: number,
  domainId: number,
  options?: ApiRequestOptions,
): Promise<TenantDomainInfo> {
  const raw = await requestClient.get<TenantDomainInfoRaw>(
    `${getDomainApiPrefix(tenantId)}/${domainId}`,
    options,
  );
  return transformDomainInfo(raw);
}

/**
 * Update domain / 更新域名
 * PUT /admin/tenants/{tenant_id}/domains/{domain_id}
 */
export async function updateTenantDomainApi(
  tenantId: number,
  domainId: number,
  data: TenantDomainUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantDomainInfo> {
  const raw = await requestClient.put<TenantDomainInfoRaw>(
    `${getDomainApiPrefix(tenantId)}/${domainId}`,
    data,
    options,
  );
  return transformDomainInfo(raw);
}

/**
 * Delete domain / 删除域名
 * DELETE /admin/tenants/{tenant_id}/domains/{domain_id}
 */
export async function deleteTenantDomainApi(
  tenantId: number,
  domainId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `${getDomainApiPrefix(tenantId)}/${domainId}`,
    options,
  );
}

/**
 * Verify domain / 验证域名
 * POST /admin/tenants/{tenant_id}/domains/{domain_id}/verify
 */
export async function verifyTenantDomainApi(
  tenantId: number,
  domainId: number,
  options?: ApiRequestOptions,
): Promise<TenantDomainInfo> {
  const raw = await requestClient.post<TenantDomainInfoRaw>(
    `${getDomainApiPrefix(tenantId)}/${domainId}/verify`,
    {},
    options,
  );
  return transformDomainInfo(raw);
}

/**
 * Set primary domain / 设置主域名
 * PUT /admin/tenants/{tenant_id}/domains/{domain_id}/primary
 */
export async function setPrimaryDomainApi(
  tenantId: number,
  domainId: number,
  options?: ApiRequestOptions,
): Promise<TenantDomainInfo> {
  const raw = await requestClient.put<TenantDomainInfoRaw>(
    `${getDomainApiPrefix(tenantId)}/${domainId}/primary`,
    {},
    options,
  );
  return transformDomainInfo(raw);
}

/**
 * Get Dev Hosts status overview / 获取 Dev Hosts 状态总览
 * GET /admin/tenants/{tenant_id}/domains/dev-hosts/status
 */
export async function getTenantDevHostsStatusApi(
  tenantId: number,
  options?: ApiRequestOptions,
): Promise<DevHostsStatusResponse> {
  const raw = await requestClient.get<DevHostsStatusResponseRaw>(
    `${getDomainApiPrefix(tenantId)}/dev-hosts/status`,
    options,
  );
  return transformDevHostsStatusResponse(raw);
}

/**
 * Sync a single Dev Hosts entry / 同步单个 Dev Hosts 条目
 * POST /admin/tenants/{tenant_id}/domains/{domain_id}/dev-hosts/sync
 */
export async function syncTenantDevHostApi(
  tenantId: number,
  domainId: number,
  options?: ApiRequestOptions,
): Promise<DevHostMutationResponse> {
  const raw = await requestClient.post<DevHostMutationResponseRaw>(
    `${getDomainApiPrefix(tenantId)}/${domainId}/dev-hosts/sync`,
    {},
    options,
  );
  return transformDevHostMutationResponse(raw);
}

/**
 * Remove a managed Dev Hosts entry / 移除托管 Dev Hosts 条目
 * DELETE /admin/tenants/{tenant_id}/domains/{domain_id}/dev-hosts
 */
export async function removeTenantDevHostApi(
  tenantId: number,
  domainId: number,
  options?: ApiRequestOptions,
): Promise<DevHostMutationResponse> {
  const raw = await requestClient.delete<DevHostMutationResponseRaw>(
    `${getDomainApiPrefix(tenantId)}/${domainId}/dev-hosts`,
    options,
  );
  return transformDevHostMutationResponse(raw);
}

/**
 * Batch sync Dev Hosts entries / 批量同步 Dev Hosts 条目
 * POST /admin/tenants/{tenant_id}/domains/dev-hosts/sync-all
 */
export async function syncAllTenantDevHostsApi(
  tenantId: number,
  options?: ApiRequestOptions,
): Promise<DevHostsSyncAllResponse> {
  const raw = await requestClient.post<DevHostsSyncAllResponseRaw>(
    `${getDomainApiPrefix(tenantId)}/dev-hosts/sync-all`,
    {},
    options,
  );
  return {
    ...transformDevHostsStatusResponse(raw),
    skipped: raw.skipped,
    synced: raw.synced,
  };
}

// ============================================================
// SSL 证书管理 API (types imported from '#/types/domain')
// ============================================================

/**
 * Get domain SSL certificate detail / 获取域名 SSL 证书详情
 * GET /admin/tenants/{tenant_id}/domains/{domain_id}/ssl
 */
export async function getSslDetailApi(
  tenantId: number,
  domainId: number,
  options?: ApiRequestOptions,
): Promise<null | SslCertificateInfo> {
  const raw = await requestClient.get<null | SslCertificateInfoRaw>(
    `${getDomainApiPrefix(tenantId)}/${domainId}/ssl`,
    options,
  );
  return raw ? transformSslCertInfo(raw) : null;
}

/**
 * Manually trigger SSL provisioning / 手动触发 SSL 签发
 * POST /admin/tenants/{tenant_id}/domains/{domain_id}/ssl/provision
 */
export async function provisionSslApi(
  tenantId: number,
  domainId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(
    `${getDomainApiPrefix(tenantId)}/${domainId}/ssl/provision`,
    {},
    options,
  );
}

/**
 * Manually renew SSL certificate / 手动续期 SSL 证书
 * POST /admin/tenants/{tenant_id}/domains/{domain_id}/ssl/renew
 */
export async function renewSslApi(
  tenantId: number,
  domainId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(
    `${getDomainApiPrefix(tenantId)}/${domainId}/ssl/renew`,
    {},
    options,
  );
}

/**
 * Upload custom SSL certificate / 上传自定义 SSL 证书
 * POST /admin/tenants/{tenant_id}/domains/{domain_id}/ssl/upload
 */
export async function uploadSslCertApi(
  tenantId: number,
  domainId: number,
  data: {
    certificate: string;
    certificate_chain?: string;
    private_key: string;
  },
  options?: ApiRequestOptions,
): Promise<SslCertificateInfo> {
  const raw = await requestClient.post<SslCertificateInfoRaw>(
    `${getDomainApiPrefix(tenantId)}/${domainId}/ssl/upload`,
    data,
    options,
  );
  return transformSslCertInfo(raw);
}

/**
 * Force replace SSL certificate (Admin only) / 强制替换 SSL 证书（Admin 独有）
 * POST /admin/tenants/{tenant_id}/domains/{domain_id}/ssl/replace
 */
export async function replaceSslApi(
  tenantId: number,
  domainId: number,
  data: {
    certificate?: string;
    certificate_chain?: string;
    mode: 'custom' | 'platform';
    private_key?: string;
  },
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(
    `${getDomainApiPrefix(tenantId)}/${domainId}/ssl/replace`,
    data,
    options,
  );
}

/**
 * Delete SSL certificate / 删除 SSL 证书
 * DELETE /admin/tenants/{tenant_id}/domains/{domain_id}/ssl
 */
export async function deleteSslCertApi(
  tenantId: number,
  domainId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `${getDomainApiPrefix(tenantId)}/${domainId}/ssl`,
    options,
  );
}

/**
 * Set SSL auto-renew toggle / 设置 SSL 自动续期开关
 * PUT /admin/tenants/{tenant_id}/domains/{domain_id}/ssl/auto-renew
 */
export async function updateSslAutoRenewApi(
  tenantId: number,
  domainId: number,
  autoRenew: boolean,
  options?: ApiRequestOptions,
): Promise<SslCertificateInfo> {
  const raw = await requestClient.put<SslCertificateInfoRaw>(
    `${getDomainApiPrefix(tenantId)}/${domainId}/ssl/auto-renew`,
    { auto_renew: autoRenew },
    options,
  );
  return transformSslCertInfo(raw);
}

/**
 * Batch provision SSL for all tenant domains (Admin only) / 批量签发租户所有域名 SSL
 * POST /admin/tenants/{tenant_id}/domains/ssl/batch-provision
 */
export async function batchProvisionSslApi(
  tenantId: number,
  options?: ApiRequestOptions,
): Promise<{ skipped: number; triggered: number }> {
  return await requestClient.post<{ skipped: number; triggered: number }>(
    `/admin/tenants/${tenantId}/domains/ssl/batch-provision`,
    {},
    options,
  );
}
