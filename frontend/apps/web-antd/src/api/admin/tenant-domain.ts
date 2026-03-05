/**
 * 平台端租户域名管理 API
 * 对接后端 /admin/tenants/{tenant_id}/domains/* 接口
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
// 类型定义
// ============================================================

/** 域名信息（后端原始格式 snake_case） */
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

/** 域名信息（前端格式 camelCase） */
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

/** 创建域名请求 */
export interface TenantDomainCreateRequest {
  /** 域名（如 app.example.com） */
  domain: string;
  /** 是否设为主域名 */
  is_primary?: boolean;
  /** 备注 */
  remark?: null | string;
}

/** 更新域名请求 */
export interface TenantDomainUpdateRequest {
  /** 是否设为主域名 */
  is_primary?: boolean | null;
  /** 备注 */
  remark?: null | string;
}

/** 域名列表响应 */
export interface TenantDomainListResponse {
  items: TenantDomainInfo[];
  total: number;
}

// ============================================================
// 转换函数
// ============================================================

/** 将后端 snake_case 转换为前端 camelCase */
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

// ============================================================
// API 接口
// ============================================================

/**
 * 构建租户域名 API 前缀
 */
function getDomainApiPrefix(tenantId: number): string {
  return `/admin/tenants/${tenantId}/domains`;
}

/**
 * 获取租户域名列表
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

  // 后端可能返回数组或分页对象，兼容处理
  if (Array.isArray(response)) {
    return {
      items: response.map((item) => transformDomainInfo(item)),
      total: response.length,
    };
  }

  // 如果后端返回分页格式
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
 * 添加自定义域名
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
 * 获取域名详情
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
 * 更新域名
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
 * 删除域名
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
 * 验证域名
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
 * 设置主域名
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

// ============================================================
// SSL 证书管理 API (types imported from '#/types/domain')
// ============================================================

/**
 * 获取域名 SSL 证书详情
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
 * 手动触发 SSL 签发
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
 * 手动续期 SSL 证书
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
 * 上传自定义 SSL 证书
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
 * 强制替换 SSL 证书（Admin 独有）
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
 * 删除 SSL 证书
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
 * 设置 SSL 自动续期开关
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
 * 批量签发租户所有域名 SSL（Admin 独有）
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
