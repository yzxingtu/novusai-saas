/**
 * 租户域名管理 - 类型定义
 */

/** 域名类型 */
export type DomainType = 'custom' | 'default';

/** 验证状态 */
export type VerificationStatus = 'failed' | 'pending' | 'verified';

/** SSL 状态 */
export type SslStatus = 'active' | 'expired' | 'failed' | 'none' | 'pending';

/** SSL 类型 */
export type SslType = 'custom' | 'platform';

/** 域名信息 */
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
  verificationToken?: string | null;
  verificationInfo?: {
    host?: string;
    type?: string;
    value?: string;
  } | null;
  verifiedAt?: string;
  sslExpiresAt?: string;
  remark?: string;
  createdAt: string;
  updatedAt: string;
  // SSL 扩展 (预留)
  sslInfo?: SslInfo;
}

/** SSL 信息 (预留) */
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

/** SSL 详情响应 (预留，包含证书内容用于复制) */
export interface SslDetailResponse {
  status: SslStatus;
  type: SslType;
  // 证书内容 (平台签发模式可复制)
  certificate?: string;
  privateKey?: string;
  certificateChain?: string;
  // 证书信息
  issuer?: string;
  validFrom?: string;
  validTo?: string;
  // 自动续期 (仅平台签发)
  autoRenew: boolean;
  nextRenewAt?: string;
  // 域名匹配 (仅自定义证书)
  domainMatch?: boolean;
}

/** 域名弹窗打开数据 */
export interface DomainModalData {
  tenantId: number;
  tenantName: string;
  tenantCode: string;
}

/** 域名详情抽屉数据 */
export interface DomainDetailData {
  domainId: number;
  tenantId: number;
}

/** DNS 引导弹窗数据 */
export interface DnsGuideData {
  domain: string;
  tenantId: number;
  domainId: number;
  verificationInfo?: TenantDomainInfo['verificationInfo'];
  verificationToken?: string | null;
  cnameTarget?: string;
}
