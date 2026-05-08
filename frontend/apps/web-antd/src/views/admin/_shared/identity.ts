import type {
  IdentityDisplayBadge,
  IdentityDisplayModel,
} from '#/components/business/identity-display';

import { $t } from '#/locales';

interface CreateAdminIdentityModelOptions extends Omit<
  IdentityDisplayModel,
  'badges' | 'secondaryText'
> {
  badges?: IdentityDisplayBadge[];
  includeTypeBadge?: boolean;
  secondaryText?: null | string;
  useTypeAsSecondary?: boolean;
  useUsernameAsSecondary?: boolean;
}

function firstNonEmpty(...values: Array<null | string | undefined>): string {
  for (const value of values) {
    if (typeof value !== 'string') {
      continue;
    }
    const trimmed = value.trim();
    if (trimmed) {
      return trimmed;
    }
  }
  return '';
}

function normalizeIdentityType(userType?: null | string): string {
  return firstNonEmpty(userType).toLowerCase();
}

function humanizeIdentityType(userType: string): string {
  return userType
    .split('_')
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

export function getAdminIdentityTypeLabel(userType?: null | string): string {
  const normalized = normalizeIdentityType(userType);

  switch (normalized) {
    case 'admin':
    case 'platform_admin':
    case 'system_admin': {
      return $t('shared.identity.userTypes.admin');
    }
    case 'tenant_admin': {
      return $t('shared.identity.userTypes.tenantAdmin');
    }
    case 'tenant_user': {
      return $t('shared.identity.userTypes.tenantUser');
    }
    default: {
      return normalized ? humanizeIdentityType(normalized) : '';
    }
  }
}

export function getAdminIdentityTypeColor(userType?: null | string): string {
  switch (normalizeIdentityType(userType)) {
    case 'admin':
    case 'platform_admin':
    case 'system_admin': {
      return 'cyan';
    }
    case 'tenant_admin': {
      return 'blue';
    }
    case 'tenant_user': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}

export function createAdminIdentityTypeBadge(
  userType?: null | string,
  keyPrefix: string = 'identity-type',
): IdentityDisplayBadge | null {
  const normalized = normalizeIdentityType(userType);
  const label = getAdminIdentityTypeLabel(normalized);

  if (!label) {
    return null;
  }

  return {
    color: getAdminIdentityTypeColor(normalized),
    key: `${keyPrefix}-${normalized || 'unknown'}`,
    label,
  };
}

export function createAdminIdentityModel(
  options: CreateAdminIdentityModelOptions,
): IdentityDisplayModel {
  const primaryName = firstNonEmpty(options.nickname, options.displayName);
  const username = firstNonEmpty(options.username);
  const badges = [...(options.badges ?? [])];
  let secondaryText = firstNonEmpty(options.secondaryText);
  if (
    !secondaryText &&
    (options.useUsernameAsSecondary ?? false) &&
    primaryName &&
    username &&
    primaryName !== username
  ) {
    secondaryText = username;
  }
  if (!secondaryText && (options.useTypeAsSecondary ?? false)) {
    secondaryText = getAdminIdentityTypeLabel(options.userType);
  }

  if (options.includeTypeBadge) {
    const badge = createAdminIdentityTypeBadge(options.userType);
    if (badge) {
      badges.push(badge);
    }
  }

  return {
    avatar: options.avatar,
    badges,
    displayName: options.displayName,
    id: options.id,
    isActive: options.isActive,
    isLeader: options.isLeader,
    isOwner: options.isOwner,
    nickname: options.nickname,
    orgNodeName: options.orgNodeName,
    roleName: options.roleName,
    secondaryText,
    userType: options.userType,
    username: options.username,
  };
}
