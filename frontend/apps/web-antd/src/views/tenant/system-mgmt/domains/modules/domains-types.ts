/**
 * 租户端域名管理 - 类型定义
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

/** 域名详情抽屉数据 */
export interface DomainDetailData {
  domainId: number;
}

/** DNS 引导弹窗数据 */
export interface DnsGuideData {
  domain: string;
  domainId: number;
  verificationInfo?: TenantDomainInfo['verificationInfo'];
  verificationToken?: null | string;
  cnameTarget?: string;
}
