import type { IdentityDetail } from './identity-detail';

import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  resolveIdentityOrgNodeLabel,
  resolveIdentityRoleLabel,
  shouldUseIdentityRoleLine,
} from './types';

function normalizeText(value?: null | string): string {
  return typeof value === 'string' ? value.trim() : '';
}

export function formatIdentityDateTime(value?: null | string): string {
  return formatDate(value, {
    fallback: $t('shared.identity.field.empty'),
    format: 'YYYY-MM-DD HH:mm:ss',
  });
}

export function shouldShowIdentityRole(
  detail: Pick<IdentityDetail, 'orgNodeName' | 'roleName'>,
): boolean {
  const roleName = normalizeText(detail.roleName);
  if (!roleName) {
    return false;
  }

  const orgNodeName = normalizeText(detail.orgNodeName);
  return roleName !== orgNodeName;
}

export function usesRoleAsPrimaryIdentityContext(
  detail: Pick<IdentityDetail, 'roleName' | 'userType'>,
): boolean {
  return shouldUseIdentityRoleLine(detail);
}

export function resolveIdentityPrimaryContextLabel(
  detail: Pick<IdentityDetail, 'roleName' | 'userType'>,
): string {
  return usesRoleAsPrimaryIdentityContext(detail)
    ? $t('shared.identity.field.role')
    : $t('shared.identity.field.organization');
}

export function resolveIdentityPrimaryContextValue(
  detail: Pick<IdentityDetail, 'orgNodeName' | 'roleName' | 'userType'>,
): string {
  return usesRoleAsPrimaryIdentityContext(detail)
    ? resolveIdentityRoleLabel(detail.roleName)
    : resolveIdentityOrgNodeLabel(detail.orgNodeName);
}

export function shouldShowIdentityOrganization(
  detail: Pick<IdentityDetail, 'orgNodeName' | 'roleName' | 'userType'>,
): boolean {
  if (!usesRoleAsPrimaryIdentityContext(detail)) {
    return false;
  }
  return Boolean(normalizeText(detail.orgNodeName));
}
