import type {
  DomainType,
  SslStatus,
  VerificationStatus,
} from './modules/domains-types';

import { $t } from '#/locales';

/**
 * 获取验证状态配置 (Tag 颜色与文本)
 */
export function getVerificationStatusConfig(status: VerificationStatus) {
  switch (status) {
    case 'failed': {
      return {
        color: 'error',
        text: $t('tenant.system.domain.verification.failed'),
      };
    }
    case 'verified': {
      return {
        color: 'success',
        text: $t('tenant.system.domain.verification.verified'),
      };
    }
    default: {
      return {
        color: 'warning',
        text: $t('tenant.system.domain.verification.pending'),
      };
    }
  }
}

/**
 * 获取 SSL 状态配置 (Badge 状态与文本)
 */
export function getSslStatusConfig(status: SslStatus) {
  switch (status) {
    case 'active': {
      return {
        status: 'success' as const,
        text: $t('tenant.system.domain.ssl.active'),
      };
    }
    case 'expired': {
      return {
        status: 'error' as const,
        text: $t('tenant.system.domain.ssl.expired'),
      };
    }
    case 'failed': {
      return { status: 'error' as const, text: 'Failed' };
    }
    case 'pending': {
      return {
        status: 'processing' as const,
        text: $t('tenant.system.domain.ssl.pending'),
      };
    }
    default: {
      return {
        status: 'default' as const,
        text: $t('tenant.system.domain.ssl.none'),
      };
    }
  }
}

/**
 * 获取域名类型配置 (Tag 颜色与文本)
 */
export function getDomainTypeConfig(type: DomainType) {
  if (type === 'default') {
    return {
      color: 'default', // 或 secondary/muted
      text: $t('tenant.system.domain.type.default'),
    };
  }
  return {
    color: 'blue',
    text: $t('tenant.system.domain.type.custom'),
  };
}
