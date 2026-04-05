import { $t } from '#/locales';

export interface IdentityDisplayBadge {
  readonly color?: string;
  readonly icon?: string;
  readonly key: string;
  readonly label: string;
}

export type IdentityValue = number | string;

export interface IdentityDisplayModel {
  avatar?: null | string;
  badges?: readonly IdentityDisplayBadge[];
  displayName?: null | string;
  id: IdentityValue;
  isActive?: boolean;
  isLeader?: boolean;
  isOwner?: boolean;
  nickname?: null | string;
  orgNodeId?: IdentityValue | null;
  orgNodeName?: null | string;
  realName?: null | string;
  roleName?: null | string;
  secondaryText?: null | string;
  userTypeLabel?: null | string;
  userType?: null | string;
  username?: null | string;
}

export interface ResolvedIdentityDisplayModel extends IdentityDisplayModel {
  badges: readonly IdentityDisplayBadge[];
  displayName: string;
  nickname: string;
  realName: string;
  orgNodeName: string;
  roleName: string;
  secondaryText: string;
  userTypeLabel: string;
  userType: string;
  username: string;
}

export interface IdentityDisplaySource extends IdentityDisplayModel {
  id: IdentityValue;
}

export interface IdentitySelectOptionExtra {
  avatar?: null | string;
  displayName?: null | string;
  nickname?: null | string;
  orgNodeId?: IdentityValue | null;
  orgNodeName?: null | string;
  realName?: null | string;
  roleName?: null | string;
  secondaryText?: null | string;
  userType?: null | string;
  userTypeLabel?: null | string;
  username?: null | string;
  isActive?: boolean;
  isLeader?: boolean;
  isOwner?: boolean;
}

export interface IdentitySelectOption {
  disabled?: boolean;
  extra?: IdentitySelectOptionExtra | null;
  label: string;
  value: IdentityValue;
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

function resolveIdentityId(id: number | string): string {
  const normalized = String(id ?? '').trim();
  return normalized || '-';
}

export function resolveIdentityDisplayTitle(
  model: IdentityDisplayModel,
): string {
  const primary = firstNonEmpty(
    model.nickname,
    model.displayName,
    model.realName,
    model.username,
  );
  if (primary) {
    return primary;
  }
  return `#${resolveIdentityId(model.id)}`;
}

export function resolveIdentityAvatarText(model: IdentityDisplayModel): string {
  const source =
    firstNonEmpty(
      model.nickname,
      model.displayName,
      model.realName,
      model.username,
    ) || resolveIdentityId(model.id);
  const normalized = source.replace(/^#/, '');
  return normalized.charAt(0).toUpperCase() || '?';
}

export function resolveIdentityOrgNodeLabel(
  orgNodeName?: null | string,
  fallbackLabel: string = $t('shared.identity.unassignedArchitecture'),
): string {
  return firstNonEmpty(orgNodeName) || fallbackLabel;
}

export function resolveIdentityRoleLabel(
  roleName?: null | string,
  fallbackLabel: string = $t('shared.identity.unassignedRole'),
): string {
  return firstNonEmpty(roleName) || fallbackLabel;
}

function normalizeIdentityUserType(userType?: null | string): string {
  return firstNonEmpty(userType).toLowerCase();
}

export function shouldUseIdentityRoleLine(
  model: Partial<IdentityDisplayModel>,
): boolean {
  return normalizeIdentityUserType(model.userType) === 'tenant_user';
}

export function resolveIdentityContextIcon(
  model: Partial<IdentityDisplayModel>,
): string {
  return shouldUseIdentityRoleLine(model)
    ? 'lucide:shield'
    : 'lucide:building-2';
}

export function resolveIdentityContextLabel(
  model: Partial<IdentityDisplayModel>,
): string {
  if (shouldUseIdentityRoleLine(model)) {
    return resolveIdentityRoleLabel(model.roleName);
  }
  return resolveIdentityOrgNodeLabel(model.orgNodeName);
}

export function resolveIdentityDisplayModel(
  model: IdentityDisplayModel,
): ResolvedIdentityDisplayModel {
  return {
    ...model,
    badges: (model.badges ?? []).filter((badge) => badge.label.trim()),
    displayName: firstNonEmpty(model.displayName),
    nickname: firstNonEmpty(model.nickname),
    orgNodeName: firstNonEmpty(model.orgNodeName),
    realName: firstNonEmpty(model.realName),
    roleName: firstNonEmpty(model.roleName),
    secondaryText: firstNonEmpty(model.secondaryText),
    userTypeLabel: firstNonEmpty(model.userTypeLabel),
    userType: firstNonEmpty(model.userType),
    username: firstNonEmpty(model.username),
    isActive: model.isActive ?? true,
    isLeader: Boolean(model.isLeader),
    isOwner: Boolean(model.isOwner),
  };
}

export function resolveIdentitySecondaryText(
  model: Partial<IdentityDisplayModel>,
): string {
  const explicit = firstNonEmpty(model.secondaryText);
  if (explicit) {
    return explicit;
  }

  const resolvedTitle = resolveIdentityDisplayTitle({
    id: model.id ?? '-',
    ...model,
  });
  const username = firstNonEmpty(model.username);
  if (username && username !== resolvedTitle) {
    return username;
  }
  const realName = firstNonEmpty(model.realName);
  if (realName && realName !== resolvedTitle) {
    return realName;
  }
  return '';
}

export function createIdentityDisplayModel(
  model: IdentityDisplaySource,
): IdentityDisplayModel {
  return {
    ...model,
    displayName: resolveIdentityDisplayTitle(model),
    secondaryText: resolveIdentitySecondaryText(model),
  };
}

export function identityModelFromOption(
  option?: IdentitySelectOption | null,
): IdentityDisplayModel {
  if (!option) {
    return createIdentityDisplayModel({
      displayName: '-',
      id: '-',
    });
  }

  return createIdentityDisplayModel({
    ...option.extra,
    displayName: option.extra?.displayName || option.label,
    id: option.value,
  });
}

export function normalizeIdentitySelectOption(
  option: IdentitySelectOption,
): IdentitySelectOption {
  const identity = identityModelFromOption(option);

  return {
    ...option,
    label: option.label || identity.displayName || `#${String(option.value)}`,
    extra: {
      ...option.extra,
      avatar: identity.avatar,
      displayName: identity.displayName,
      nickname: identity.nickname,
      orgNodeId: identity.orgNodeId,
      orgNodeName: identity.orgNodeName,
      realName: identity.realName,
      roleName: identity.roleName,
      secondaryText: identity.secondaryText,
      userType: identity.userType,
      userTypeLabel: identity.userTypeLabel,
      username: identity.username,
      isActive: identity.isActive,
      isLeader: identity.isLeader,
      isOwner: identity.isOwner,
    },
  };
}
