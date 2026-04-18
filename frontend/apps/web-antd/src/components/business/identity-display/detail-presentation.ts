import type { IdentityDetail } from './identity-detail';

import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  getIdentityApprovalStatusLabel,
  getIdentityDetailTypeLabel,
  getIdentityStatusLabel,
  normalizeIdentitySubjectType,
} from './identity-detail';
import {
  resolveIdentityDisplayTitle,
  resolveIdentityOrgNodeLabel,
  resolveIdentityRoleLabel,
  shouldUseIdentityRoleLine,
} from './types';

export interface IdentityPresentationRow {
  key: string;
  label: string;
  value: string;
}

export interface IdentityStatusChip {
  color: string;
  key: string;
  label: string;
}

export type IdentitySummaryMode =
  | 'detail-account'
  | 'detail-overview'
  | 'embedded'
  | 'quick';

function normalizeText(value?: null | string): string {
  return typeof value === 'string' ? value.trim() : '';
}

function resolveValue(value?: null | string): string {
  return normalizeText(value) || $t('shared.identity.field.empty');
}

function resolveIdentityTypeColor(userType?: null | string): string {
  switch (normalizeIdentitySubjectType(userType)) {
    case 'admin': {
      return 'gold';
    }
    case 'tenant_admin': {
      return 'processing';
    }
    case 'tenant_user': {
      return 'success';
    }
    default: {
      return 'default';
    }
  }
}

function createRow(
  key: string,
  label: string,
  value?: null | string,
): IdentityPresentationRow {
  return {
    key,
    label,
    value: resolveValue(value),
  };
}

function pushOptionalRow(
  rows: IdentityPresentationRow[],
  key: string,
  label: string,
  value?: null | string,
): void {
  if (!normalizeText(value)) {
    return;
  }
  rows.push({
    key,
    label,
    value: normalizeText(value),
  });
}

function formatYesNo(value?: boolean): string {
  return value ? $t('shared.common.yes') : $t('shared.common.no');
}

export function formatIdentityDateTime(value?: null | string): string {
  return formatDate(value, {
    fallback: $t('shared.identity.field.empty'),
    format: 'YYYY-MM-DD HH:mm:ss',
  });
}

export function formatIdentityRecentActivity(value?: null | string): string {
  const relative = formatRelativeTime(value, '');
  if (relative) {
    return relative;
  }
  return formatIdentityDateTime(value);
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

export function shouldShowSecondaryOrganization(
  detail: Pick<IdentityDetail, 'orgNodeName' | 'roleName' | 'userType'>,
): boolean {
  if (!usesRoleAsPrimaryIdentityContext(detail)) {
    return false;
  }
  return Boolean(normalizeText(detail.orgNodeName));
}

export function shouldShowRoleRow(
  detail: Pick<IdentityDetail, 'orgNodeName' | 'roleName' | 'userType'>,
): boolean {
  if (usesRoleAsPrimaryIdentityContext(detail)) {
    return false;
  }

  const roleName = normalizeText(detail.roleName);
  if (!roleName) {
    return false;
  }

  const orgNodeName = normalizeText(detail.orgNodeName);
  return roleName !== orgNodeName;
}

function buildQuickRows(detail: IdentityDetail): IdentityPresentationRow[] {
  const rows = [
    createRow(
      'username',
      $t('shared.identity.field.username'),
      detail.username,
    ),
  ];

  pushOptionalRow(
    rows,
    'tenant',
    $t('shared.identity.field.tenant'),
    detail.tenantName,
  );

  rows.push({
    key: 'primary-context',
    label: resolveIdentityPrimaryContextLabel(detail),
    value: resolveIdentityPrimaryContextValue(detail),
  });

  if (normalizeText(detail.email)) {
    rows.push(
      createRow('email', $t('shared.identity.field.email'), detail.email),
    );
  } else if (normalizeText(detail.phone)) {
    rows.push(
      createRow('phone', $t('shared.identity.field.phone'), detail.phone),
    );
  }

  pushOptionalRow(
    rows,
    'last-login',
    $t('shared.identity.field.lastLoginAt'),
    normalizeText(detail.lastLoginAt)
      ? formatIdentityRecentActivity(detail.lastLoginAt)
      : undefined,
  );

  return rows;
}

function buildDetailOverviewRows(
  detail: IdentityDetail,
): IdentityPresentationRow[] {
  const rows = [
    createRow(
      'username',
      $t('shared.identity.field.username'),
      detail.username,
    ),
  ];

  pushOptionalRow(
    rows,
    'tenant',
    $t('shared.identity.field.tenant'),
    detail.tenantName,
  );

  rows.push({
    key: 'primary-context',
    label: resolveIdentityPrimaryContextLabel(detail),
    value: resolveIdentityPrimaryContextValue(detail),
  });

  if (shouldShowSecondaryOrganization(detail)) {
    rows.push(
      createRow(
        'organization',
        $t('shared.identity.field.organization'),
        detail.orgNodeName,
      ),
    );
  }

  if (shouldShowRoleRow(detail)) {
    rows.push(
      createRow('role', $t('shared.identity.field.role'), detail.roleName),
    );
  }

  return rows;
}

function buildDetailAccountRows(
  detail: IdentityDetail,
): IdentityPresentationRow[] {
  return [
    {
      key: 'status',
      label: $t('shared.identity.field.status'),
      value: getIdentityStatusLabel(detail.isActive),
    },
    {
      key: 'approval-status',
      label: $t('shared.identity.field.approvalStatus'),
      value: detail.approvalStatus
        ? getIdentityApprovalStatusLabel(detail.approvalStatus)
        : $t('shared.identity.field.empty'),
    },
    {
      key: 'owner',
      label: $t('shared.identity.field.owner'),
      value: formatYesNo(detail.isOwner),
    },
    {
      key: 'leader',
      label: $t('shared.identity.field.leader'),
      value: formatYesNo(detail.isLeader),
    },
    {
      key: 'super-admin',
      label: $t('shared.identity.field.superAdmin'),
      value: formatYesNo(detail.isSuper),
    },
    createRow('email', $t('shared.identity.field.email'), detail.email),
    createRow('phone', $t('shared.identity.field.phone'), detail.phone),
  ];
}

export function buildIdentitySummaryRows(
  detail: IdentityDetail,
  mode: IdentitySummaryMode,
): IdentityPresentationRow[] {
  switch (mode) {
    case 'detail-account': {
      return buildDetailAccountRows(detail);
    }
    case 'detail-overview': {
      return buildDetailOverviewRows(detail);
    }
    case 'embedded':
    case 'quick': {
      return buildQuickRows(detail);
    }
    default: {
      return [];
    }
  }
}

export function buildIdentityStatusChips(
  detail: Pick<
    IdentityDetail,
    'isActive' | 'isLeader' | 'isOwner' | 'userType' | 'userTypeLabel'
  >,
): IdentityStatusChip[] {
  const chips: IdentityStatusChip[] = [];
  const seen = new Set<string>();

  function pushChip(chip: IdentityStatusChip) {
    if (!chip.label.trim() || seen.has(chip.key)) {
      return;
    }
    seen.add(chip.key);
    chips.push(chip);
  }

  if (normalizeText(detail.userType) || normalizeText(detail.userTypeLabel)) {
    pushChip({
      color: resolveIdentityTypeColor(detail.userType),
      key: 'identity-type',
      label:
        normalizeText(detail.userTypeLabel) ||
        getIdentityDetailTypeLabel(detail.userType),
    });
  }

  if (detail.isLeader) {
    pushChip({
      color: 'warning',
      key: 'leader',
      label: $t('shared.identity.field.leader'),
    });
  }

  if (detail.isOwner) {
    pushChip({
      color: 'gold',
      key: 'owner',
      label: $t('shared.identity.field.owner'),
    });
  }

  if (detail.isActive === false) {
    pushChip({
      color: 'default',
      key: 'disabled',
      label: $t('shared.common.statusDisabled'),
    });
  }

  return chips;
}

export function buildIdentityActivityRows(
  detail: Pick<
    IdentityDetail,
    'createdAt' | 'lastLoginAt' | 'lastLoginIp' | 'updatedAt'
  >,
): IdentityPresentationRow[] {
  return [
    {
      key: 'created-at',
      label: $t('shared.identity.field.createdAt'),
      value: formatIdentityDateTime(detail.createdAt),
    },
    {
      key: 'updated-at',
      label: $t('shared.identity.field.updatedAt'),
      value: formatIdentityDateTime(detail.updatedAt),
    },
    {
      key: 'last-login-at',
      label: $t('shared.identity.field.lastLoginAt'),
      value: formatIdentityDateTime(detail.lastLoginAt),
    },
    {
      key: 'last-login-ip',
      label: $t('shared.identity.field.lastLoginIp'),
      value: resolveValue(detail.lastLoginIp),
    },
  ];
}

export function buildIdentityAuxiliaryItems(
  detail: Pick<
    IdentityDetail,
    'displayName' | 'email' | 'tenantName' | 'username'
  >,
): string[] {
  const resolvedTitle = normalizeText(
    resolveIdentityDisplayTitle({
      displayName: detail.displayName,
      id: '-',
      username: detail.username,
    }),
  );
  const values = [
    normalizeText(detail.username),
    normalizeText(detail.email),
    normalizeText(detail.tenantName),
  ];

  return values.filter(
    (value, index, list) =>
      Boolean(value) &&
      value !== resolvedTitle &&
      list.indexOf(value) === index,
  );
}

export const shouldShowIdentityOrganization = shouldShowSecondaryOrganization;
export const shouldShowIdentityRole = shouldShowRoleRow;
