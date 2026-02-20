/**
 * 租户端域名管理 API
 * 对接后端 /tenant/domains/* 接口
 */
import type { DomainType, SslStatus, VerificationStatus } from '#/types/domain';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

export type { DomainType, SslStatus, VerificationStatus } from '#/types/domain';

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
  verification_info?: null | {
    dns_name?: string;
    dns_type?: string;
    dns_value?: string;
    host?: string;
    type?: string;
    value?: string;
  };
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
  isVerified: boolean;
  verificationStatus: VerificationStatus;
  sslStatus: SslStatus;
  cnameTarget?: string;
  txtRecord?: string;
  verificationToken?: null | string;
  verificationInfo?: null | Record<string, any>;
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
  /** 备注 */
  remark?: string;
}

/** 更新域名请求 */
export interface TenantDomainUpdateRequest {
  /** 备注 */
  remark?: string;
}

/** 域名列表响应 */
export interface TenantDomainListResponse {
  items: TenantDomainInfo[];
  total: number;
}

/** DNS 验证信息 */
export interface DnsVerificationInfo {
  /** CNAME 目标 */
  cname_target?: string;
  /** TXT 记录 */
  txt_record?: string;
  /** 验证 token */
  verification_token?: string;
}

// ============================================================
// 转换函数
// ============================================================

/** 将后端 snake_case 转换为前端 camelCase */
function transformDomainInfo(raw: TenantDomainInfoRaw): TenantDomainInfo {
  const domainType = raw.domain_type || 'custom';

  return {
    id: raw.id,
    tenantId: raw.tenant_id,
    domain: raw.domain,
    domainType,
    isPrimary: raw.is_primary,
    isVerified: raw.is_verified,
    verificationStatus: raw.is_verified ? 'verified' : 'pending',
    sslStatus: raw.ssl_status || 'none',
    cnameTarget: raw.cname_target,
    txtRecord: raw.txt_record,
    verificationToken: raw.verification_token,
    verificationInfo: raw.verification_info
      ? {
          host: raw.verification_info.dns_name || raw.verification_info.host,
          type: raw.verification_info.dns_type || raw.verification_info.type,
          value: raw.verification_info.dns_value || raw.verification_info.value,
        }
      : null,
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
 * 获取租户域名列表
 * GET /tenant/domains
 */
export async function getTenantDomainsApi(
  options?: ApiRequestOptions,
): Promise<TenantDomainListResponse> {
  const response = await requestClient.get<TenantDomainInfoRaw[]>(
    '/tenant/domains',
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
 * POST /tenant/domains
 */
export async function createTenantDomainApi(
  data: TenantDomainCreateRequest,
  options?: ApiRequestOptions,
): Promise<TenantDomainInfo> {
  const raw = await requestClient.post<TenantDomainInfoRaw>(
    '/tenant/domains',
    data,
    options,
  );
  return transformDomainInfo(raw);
}

/**
 * 获取域名详情
 * GET /tenant/domains/{domain_id}
 */
export async function getTenantDomainApi(
  domainId: number,
  options?: ApiRequestOptions,
): Promise<TenantDomainInfo> {
  const raw = await requestClient.get<TenantDomainInfoRaw>(
    `/tenant/domains/${domainId}`,
    options,
  );
  return transformDomainInfo(raw);
}

/**
 * 更新域名
 * PUT /tenant/domains/{domain_id}
 */
export async function updateTenantDomainApi(
  domainId: number,
  data: TenantDomainUpdateRequest,
  options?: ApiRequestOptions,
): Promise<TenantDomainInfo> {
  const raw = await requestClient.put<TenantDomainInfoRaw>(
    `/tenant/domains/${domainId}`,
    data,
    options,
  );
  return transformDomainInfo(raw);
}

/**
 * 删除域名
 * DELETE /tenant/domains/{domain_id}
 */
export async function deleteTenantDomainApi(
  domainId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`/tenant/domains/${domainId}`, options);
}

/**
 * 验证域名
 * POST /tenant/domains/{domain_id}/verify
 */
export async function verifyTenantDomainApi(
  domainId: number,
  options?: ApiRequestOptions,
): Promise<TenantDomainInfo> {
  const raw = await requestClient.post<TenantDomainInfoRaw>(
    `/tenant/domains/${domainId}/verify`,
    {},
    options,
  );
  return transformDomainInfo(raw);
}

/**
 * 设置主域名
 * PUT /tenant/domains/{domain_id}/primary
 */
export async function setPrimaryDomainApi(
  domainId: number,
  options?: ApiRequestOptions,
): Promise<TenantDomainInfo> {
  const raw = await requestClient.put<TenantDomainInfoRaw>(
    `/tenant/domains/${domainId}/primary`,
    {},
    options,
  );
  return transformDomainInfo(raw);
}

// TODO: getDomainDnsInfoApi 待后端实现对应端点后启用
// /**
//  * 获取域名 DNS 验证信息
//  * GET /tenant/domains/{domain_id}/dns-info
//  */
// export async function getDomainDnsInfoApi(
//   domainId: number,
//   options?: ApiRequestOptions,
// ): Promise<DnsVerificationInfo> {
//   return await requestClient.get<DnsVerificationInfo>(
//     `/tenant/domains/${domainId}/dns-info`,
//     options,
//   );
// }

// ============================================================
// SSL 证书管理 API
// ============================================================

/** SSL 证书详情响应 */
export interface SslCertificateInfo {
  id: number;
  domainId: number;
  tenantId: number;
  certType: 'custom' | 'platform';
  status: 'active' | 'expired' | 'failed' | 'pending' | 'revoked';
  issuer: null | string;
  serialNumber: null | string;
  issuedAt: null | string;
  expiresAt: null | string;
  autoRenew: boolean;
  hasCertificate: boolean;
  hasPrivateKey: boolean;
  hasChain: boolean;
  lastRenewalAttempt: null | string;
  renewalError: null | string;
  createdAt: string;
  updatedAt: string;
}

/** SSL 证书详情原始响应 */
interface SslCertificateInfoRaw {
  id: number;
  domain_id: number;
  tenant_id: number;
  cert_type: 'custom' | 'platform';
  status: 'active' | 'expired' | 'failed' | 'pending' | 'revoked';
  issuer: null | string;
  serial_number: null | string;
  issued_at: null | string;
  expires_at: null | string;
  auto_renew: boolean;
  has_certificate: boolean;
  has_private_key: boolean;
  has_chain: boolean;
  last_renewal_attempt: null | string;
  renewal_error: null | string;
  created_at: string;
  updated_at: string;
}

function transformSslCertInfo(raw: SslCertificateInfoRaw): SslCertificateInfo {
  return {
    id: raw.id,
    domainId: raw.domain_id,
    tenantId: raw.tenant_id,
    certType: raw.cert_type,
    status: raw.status,
    issuer: raw.issuer,
    serialNumber: raw.serial_number,
    issuedAt: raw.issued_at,
    expiresAt: raw.expires_at,
    autoRenew: raw.auto_renew,
    hasCertificate: raw.has_certificate,
    hasPrivateKey: raw.has_private_key,
    hasChain: raw.has_chain,
    lastRenewalAttempt: raw.last_renewal_attempt,
    renewalError: raw.renewal_error,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

/**
 * 获取域名 SSL 证书详情
 * GET /tenant/domains/{domain_id}/ssl
 */
export async function getTenantSslDetailApi(
  domainId: number,
  options?: ApiRequestOptions,
): Promise<SslCertificateInfo | null> {
  const raw = await requestClient.get<SslCertificateInfoRaw | null>(
    `/tenant/domains/${domainId}/ssl`,
    options,
  );
  return raw ? transformSslCertInfo(raw) : null;
}

/**
 * 手动触发 SSL 签发
 * POST /tenant/domains/{domain_id}/ssl/provision
 */
export async function provisionTenantSslApi(
  domainId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(
    `/tenant/domains/${domainId}/ssl/provision`,
    {},
    options,
  );
}

/**
 * 手动续期 SSL 证书
 * POST /tenant/domains/{domain_id}/ssl/renew
 */
export async function renewTenantSslApi(
  domainId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.post(
    `/tenant/domains/${domainId}/ssl/renew`,
    {},
    options,
  );
}

/**
 * 上传自定义 SSL 证书
 * POST /tenant/domains/{domain_id}/ssl/upload
 */
export async function uploadTenantSslCertApi(
  domainId: number,
  data: { certificate: string; certificate_chain?: string; private_key: string },
  options?: ApiRequestOptions,
): Promise<SslCertificateInfo> {
  const raw = await requestClient.post<SslCertificateInfoRaw>(
    `/tenant/domains/${domainId}/ssl/upload`,
    data,
    options,
  );
  return transformSslCertInfo(raw);
}

/**
 * 删除 SSL 证书
 * DELETE /tenant/domains/{domain_id}/ssl
 */
export async function deleteTenantSslCertApi(
  domainId: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `/tenant/domains/${domainId}/ssl`,
    options,
  );
}

/**
 * 设置 SSL 自动续期开关
 * PUT /tenant/domains/{domain_id}/ssl/auto-renew
 */
export async function updateTenantSslAutoRenewApi(
  domainId: number,
  autoRenew: boolean,
  options?: ApiRequestOptions,
): Promise<SslCertificateInfo> {
  const raw = await requestClient.put<SslCertificateInfoRaw>(
    `/tenant/domains/${domainId}/ssl/auto-renew`,
    { auto_renew: autoRenew },
    options,
  );
  return transformSslCertInfo(raw);
}
