import type { TenantPermissionRoleInfo } from '#/api/tenant/role';
import type { TenantUserInfo } from '#/api/tenant/tenant-users';
import type { IdentitySelectOption } from '#/components/business/identity-display';

import { normalizeIdentitySelectOption } from '#/components/business/identity-display';
import { $t } from '#/locales';

export interface PermissionRoleTreeNode {
  disabled?: boolean;
  key: number;
  title: string;
  value: number;
}

export type TenantAccessRoleMode = 'all' | 'specific';

export const PUB_ALL = 'all_users';
export const PUB_ROLES = 'tenant_user_roles';
export const PUB_USERS = 'specific_users';

export function getAccessTypeOptions() {
  return [
    {
      label: $t('tenant.ai.agent.publication.accessAllUsers'),
      value: PUB_ALL,
    },
    {
      label: $t('tenant.ai.agent.publication.accessByUserRoles'),
      value: PUB_ROLES,
    },
    {
      label: $t('tenant.ai.agent.publication.accessSpecificUsers'),
      value: PUB_USERS,
    },
  ];
}

export function normalizeIdList(raw: unknown): number[] {
  if (raw === null || raw === undefined || !Array.isArray(raw)) {
    return [];
  }

  return raw
    .map((value) =>
      typeof value === 'string' ? Number.parseInt(value, 10) : Number(value),
    )
    .filter((value) => Number.isFinite(value) && value > 0);
}

export function deriveTenantAdminRoleMode(
  ids: null | number[] | undefined,
): TenantAccessRoleMode {
  if (ids === null || ids === undefined || ids.length === 0) {
    return 'all';
  }

  return 'specific';
}

export function roleInfoToTreeData(
  roles: TenantPermissionRoleInfo[],
): PermissionRoleTreeNode[] {
  return roles.map((role) => ({
    disabled: !role.isActive,
    key: role.id,
    title: role.name,
    value: role.id,
  }));
}

export function tenantUserToIdentityOption(
  user: TenantUserInfo,
): IdentitySelectOption {
  const roleName = Object.prototype.hasOwnProperty.call(user, 'displayRoleName')
    ? (user.displayRoleName ?? null)
    : (user.roleName ?? null);

  return normalizeIdentitySelectOption({
    label: user.nickname || user.displayName || user.username || `#${user.id}`,
    value: user.id,
    extra: {
      avatar: user.avatar || null,
      displayName: user.displayName || null,
      isActive: user.isActive,
      isLeader: user.isLeader,
      isOwner: user.isOwner,
      nickname: user.nickname || null,
      orgNodeId: user.orgNodeId ?? null,
      orgNodeName: user.orgNodeName || null,
      roleName,
      secondaryText: user.username,
      userType: user.userType || null,
      username: user.username,
    },
  });
}

export function mergeTenantUserOptions(
  current: Map<number, IdentitySelectOption>,
  options: IdentitySelectOption[],
): Map<number, IdentitySelectOption> {
  if (options.length === 0) {
    return current;
  }

  const nextCache = new Map(current);
  for (const option of options) {
    const normalized = normalizeIdentitySelectOption(option);
    const normalizedValue = Number(normalized.value);
    if (!Number.isFinite(normalizedValue) || normalizedValue <= 0) {
      continue;
    }
    nextCache.set(normalizedValue, normalized);
  }

  return nextCache;
}

export function mapTenantUserRoleOptions(
  roles: Array<{ id: number; name: string }>,
) {
  return roles.map((role) => ({
    label: role.name,
    value: role.id,
  }));
}
