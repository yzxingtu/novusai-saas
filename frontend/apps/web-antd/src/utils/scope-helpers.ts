/**
 * Unified resource scope helpers (ResourceScopeEnum — 5 values only)
 * 统一资源作用域工具（仅 5 个枚举值）
 *
 * global_shared | admin_only | all_tenants | admin_and_selected_tenants | selected_tenants
 * 与 RBAC 权限端别（admin/tenant/user/both）、插件菜单挂载端别无关。
 */

import { $t } from '#/locales';

export interface ScopeConfig {
  color: string;
  icon: string;
  textKey: string;
}

/** Scope configuration table / 作用域配置表 */
export const SCOPE_CONFIG: Record<string, ScopeConfig> = {
  global_shared: {
    color: 'purple',
    icon: 'lucide:globe',
    textKey: 'common.scope.globalShared',
  },
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
  admin_and_selected_tenants: {
    color: 'orange',
    icon: 'lucide:user-check',
    textKey: 'common.scope.adminAndSelectedTenants',
  },
  selected_tenants: {
    color: 'cyan',
    icon: 'lucide:user-plus',
    textKey: 'common.scope.selectedTenants',
  },
};

export function getScopeColor(scope: string | undefined): string {
  if (!scope) return 'default';
  return SCOPE_CONFIG[scope]?.color ?? 'default';
}

export function getScopeText(scope: string | undefined): string {
  if (!scope) return '';
  const config = SCOPE_CONFIG[scope];
  return config ? $t(config.textKey) : scope;
}

export function getScopeIcon(scope: string | undefined): string {
  if (!scope) return 'lucide:help-circle';
  return SCOPE_CONFIG[scope]?.icon ?? 'lucide:help-circle';
}

export interface ScopeOption {
  label: string;
  value: string;
}

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

export function getAdminScopeOptions(): ScopeOption[] {
  return getScopeOptions([
    'global_shared',
    'admin_only',
    'all_tenants',
    'admin_and_selected_tenants',
    'selected_tenants',
  ]);
}

/** Tenant creates resources that are tenant-owned; scope usually all_tenants */
export function getTenantScopeOptions(): ScopeOption[] {
  return getScopeOptions(['all_tenants']);
}
