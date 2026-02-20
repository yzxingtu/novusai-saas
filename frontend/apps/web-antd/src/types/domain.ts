/**
 * 域名管理 - 共享类型定义
 * 统一 admin/tenant 两端的域名相关类型
 */

/** 域名类型 */
export type DomainType = 'custom' | 'default';

/** 验证状态 */
export type VerificationStatus = 'failed' | 'pending' | 'verified';

/** SSL 状态 */
export type SslStatus =
  | 'active'
  | 'expired'
  | 'failed'
  | 'none'
  | 'pending'
  | 'provisioning';

/** SSL 类型 */
export type SslType = 'custom' | 'platform';
