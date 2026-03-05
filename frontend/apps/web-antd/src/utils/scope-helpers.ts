/**
 * 统一作用域工具函数
 *
 * 全平台共用，替代各模块分散的 getScopeColor/getScopeText/getScopeOptions。
 * 5 种作用域：admin_only / all_tenants / admin_and_all / admin_and_assigned / assigned_tenants
 */

import { $t } from '#/locales';

export interface ScopeConfig {
  color: string;
  icon: string;
  textKey: string;
}

/** 作用域配置表 */
export const SCOPE_CONFIG: Record<string, ScopeConfig> = {
  admin_only: {
    color: 'blue',
    icon: 'lucide:shield',
    textKey: 'common.scope.adminOnly',
  },
  all_tenants: {
    color: 'green',
    icon: 'lucide:users',
    textKey: 'common.scope.allTenants',
  },
  admin_and_all: {
    color: 'purple',
    icon: 'lucide:globe',
    textKey: 'common.scope.adminAndAll',
  },
  admin_and_assigned: {
    color: 'orange',
    icon: 'lucide:user-check',
    textKey: 'common.scope.adminAndAssigned',
  },
  assigned_tenants: {
    color: 'cyan',
    icon: 'lucide:user-plus',
    textKey: 'common.scope.assignedTenants',
  },
};

/** 获取 scope 颜色（Tag 使用） */
export function getScopeColor(scope: string | undefined): string {
  if (!scope) return 'default';
  return SCOPE_CONFIG[scope]?.color ?? 'default';
}

/** 获取 scope 文本（已翻译） */
export function getScopeText(scope: string | undefined): string {
  if (!scope) return '';
  const config = SCOPE_CONFIG[scope];
  return config ? $t(config.textKey) : scope;
}

/** 获取 scope 图标 */
export function getScopeIcon(scope: string | undefined): string {
  if (!scope) return 'lucide:help-circle';
  return SCOPE_CONFIG[scope]?.icon ?? 'lucide:help-circle';
}

export interface ScopeOption {
  label: string;
  value: string;
}

/**
 * 获取 scope 下拉选项
 *
 * @param allowedScopes 可选，限制返回的 scope 列表。不传则返回全部 5 种。
 */
export function getScopeOptions(allowedScopes?: string[]): ScopeOption[] {
  const scopes = allowedScopes ?? Object.keys(SCOPE_CONFIG);
  return scopes
    .filter((s) => s in SCOPE_CONFIG)
    .map((s) => {
      const config = SCOPE_CONFIG[s];
      if (!config) return null;
      return {
        label: $t(config.textKey),
        value: s,
      };
    })
    .filter((item): item is ScopeOption => item !== null);
}

/** 获取管理端可选的 scope 列表（排除 assigned_tenants，因为管理端不需要） */
export function getAdminScopeOptions(): ScopeOption[] {
  return getScopeOptions([
    'admin_only',
    'all_tenants',
    'admin_and_all',
    'admin_and_assigned',
    'assigned_tenants',
  ]);
}

/** 获取租户端可见的 scope 列表（租户端只能创建 all_tenants） */
export function getTenantScopeOptions(): ScopeOption[] {
  return getScopeOptions(['all_tenants']);
}
