/**
 * Tenant domain management - type definitions
 * 租户域名管理 - 类型定义
 */
import type {
  DomainType,
  SslStatus,
  SslType,
  VerificationStatus,
} from '#/types/domain';

export type {
  DomainType,
  SslStatus,
  SslType,
  VerificationStatus,
} from '#/types/domain';

/** Domain info / 域名信息 */
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
  verificationInfo?: null | {
    host?: string;
    type?: string;
    value?: string;
  };
  verifiedAt?: string;
  sslExpiresAt?: string;
  remark?: string;
  createdAt: string;
  updatedAt: string;
  // SSL extension (reserved) / SSL 扩展 (预留)
  sslInfo?: SslInfo;
}

/** SSL info (reserved) / SSL 信息 (预留) */
export interface SslInfo {
  status: SslStatus;
  type: SslType;
  issuer?: string;
  validFrom?: string;
  validTo?: string;
  autoRenew: boolean;
  nextRenewAt?: string;
  domainMatch?: boolean;
}

/** SSL detail response (reserved, includes cert content for copying) / SSL 详情响应 (预留，包含证书内容用于复制) */
export interface SslDetailResponse {
  status: SslStatus;
  type: SslType;
  // Certificate content (copyable in platform-issued mode) / 证书内容 (平台签发模式可复制)
  certificate?: string;
  privateKey?: string;
  certificateChain?: string;
  // Certificate info / 证书信息
  issuer?: string;
  validFrom?: string;
  validTo?: string;
  // Auto-renew (platform-issued only) / 自动续期 (仅平台签发)
  autoRenew: boolean;
  nextRenewAt?: string;
  // Domain match (custom cert only) / 域名匹配 (仅自定义证书)
  domainMatch?: boolean;
}

/** Domain modal open data / 域名弹窗打开数据 */
export interface DomainModalData {
  tenantId: number;
  tenantName: string;
  tenantCode: string;
}

/** Domain detail drawer data / 域名详情抽屉数据 */
export interface DomainDetailData {
  domainId: number;
  tenantId: number;
}

/** DNS guide modal data / DNS 引导弹窗数据 */
export interface DnsGuideData {
  domain: string;
  tenantId: number;
  domainId: number;
  verificationInfo?: TenantDomainInfo['verificationInfo'];
  verificationToken?: null | string;
  cnameTarget?: string;
}
