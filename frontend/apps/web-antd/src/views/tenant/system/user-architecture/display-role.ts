/**
 * 企业用户角色展示名（内置角色按 i18n，与接口返回语言解耦）
 * Display labels for tenant user roles; built-in roles use i18n instead of DB text.
 */
import type { TenantUserRoleInfo } from '#/api/tenant/tenant-user-roles';

export type TranslateFn = (key: string, ...args: unknown[]) => string;

/** 内置角色 code → i18n 前缀（tenant.system.userArchitecture.builtInRoles.<code>） */
const BUILT_IN_ROLE_CODES = new Set(['default_user']);

export function isBuiltInTenantUserRoleCode(code: string): boolean {
  return BUILT_IN_ROLE_CODES.has(code);
}

export function displayTenantUserRoleName(
  role: Pick<TenantUserRoleInfo, 'code' | 'name'>,
  t: TranslateFn,
): string {
  if (role.code === 'default_user') {
    return t('tenant.system.userArchitecture.builtInRoles.default_user.name');
  }
  return role.name;
}

/** 返回可展示的描述；内置角色始终用文案，忽略库中旧英文描述 */
export function displayTenantUserRoleDescription(
  role: Pick<TenantUserRoleInfo, 'code' | 'description'>,
  t: TranslateFn,
): string {
  if (role.code === 'default_user') {
    return t('tenant.system.userArchitecture.builtInRoles.default_user.description');
  }
  return (role.description ?? '').trim();
}
