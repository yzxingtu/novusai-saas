/**
 * 租户端域名管理 API
 * 对接后端 /tenant/domains/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义
// ============================================================

/** 域名类型 */
export type DomainType = 'custom' | 'default';

/** SSL 状态 */
export type SslStatus = 'active' | 'failed' | 'none' | 'pending';

/** 验证状态 */
export type VerificationStatus = 'failed' | 'pending' | 'verified';

/** 域名信息（后端原始格式 snake_case） */
export interface TenantDomainInfoRaw {
  id: number;
  tenant_id: number;
  domain: string;
  domain_type?: DomainType; // 后端可能不返回此字段，前端需要推断
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

/**
 * 判断是否为默认域名
 * 默认域名格式：{subdomain}.{app_platform_domain}
 * 例如：t5od3oj3p.app.novusai.com
 */
function isDefaultDomain(domain: string, raw: TenantDomainInfoRaw): boolean {
  // 如果后端返回了 domain_type，直接使用
  if ('domain_type' in raw && raw.domain_type) {
    return raw.domain_type === 'default';
  }

  // 否则根据规则推断：默认域名通常包含 app.novusai.com 或类似的平台域名
  // 这里可以根据实际平台域名调整判断逻辑
  const platformDomains = [
    'app.novusai.com',
    'novusai.com',
    // 可以添加更多平台域名
  ];

  return platformDomains.some((pd) => domain.endsWith(pd));
}

/** 将后端 snake_case 转换为前端 camelCase */
function transformDomainInfo(raw: TenantDomainInfoRaw): TenantDomainInfo {
  // 处理缺失的 domain_type 字段
  const domainType = isDefaultDomain(raw.domain, raw) ? 'default' : 'custom';

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

/**
 * 获取域名 DNS 验证信息
 * GET /tenant/domains/{domain_id}/dns-info
 */
export async function getDomainDnsInfoApi(
  domainId: number,
  options?: ApiRequestOptions,
): Promise<DnsVerificationInfo> {
  return await requestClient.get<DnsVerificationInfo>(
    `/tenant/domains/${domainId}/dns-info`,
    options,
  );
}
