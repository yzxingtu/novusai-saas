/**
 * Domain management - shared type definitions
 * Unified domain-related types for both admin/tenant endpoints
 * 域名管理 - 共享类型定义
 * 统一 admin/tenant 两端的域名相关类型
 */

/** Domain type / 域名类型 */
export type DomainType = 'custom' | 'default';

/** Verification status / 验证状态 */
export type VerificationStatus = 'failed' | 'pending' | 'verified';

/** SSL status / SSL 状态 */
export type SslStatus =
  | 'active'
  | 'expired'
  | 'failed'
  | 'none'
  | 'pending'
  | 'provisioning';

/** SSL type / SSL 类型 */
export type SslType = 'custom' | 'platform';

/** SSL certificate status (certificate record level) / SSL 证书状态（证书记录级别） */
export type SslCertStatus =
  | 'active'
  | 'expired'
  | 'failed'
  | 'pending'
  | 'revoked';

/** DNS verification info (backend returns dns_name/dns_type/dns_value, frontend unifies to host/type/value) / DNS 验证信息（后端返回 dns_name/dns_type/dns_value，前端统一为 host/type/value） */
export interface VerificationInfo {
  dns_name?: string;
  dns_type?: string;
  dns_value?: string;
  host?: string;
  type?: string;
  value?: string;
}

/** SSL certificate details (frontend camelCase format) / SSL 证书详情（前端 camelCase 格式） */
export interface SslCertificateInfo {
  id: number;
  domainId: number;
  tenantId: number;
  certType: SslType;
  status: SslCertStatus;
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

/** SSL certificate details (backend snake_case raw format) / SSL 证书详情（后端 snake_case 原始格式） */
export interface SslCertificateInfoRaw {
  id: number;
  domain_id: number;
  tenant_id: number;
  cert_type: SslType;
  status: SslCertStatus;
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

/** SSL certificate snake→camelCase transform / SSL 证书 snake→camelCase 转换 */
export function transformSslCertInfo(
  raw: SslCertificateInfoRaw,
): SslCertificateInfo {
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
