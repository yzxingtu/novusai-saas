import type {
  MonitoringActorInfo,
  MonitoringCallLogInfo,
  MonitoringScope,
  MonitoringUsageBreakdownItem,
} from './api';

import type {
  IdentityDisplayBadge,
  IdentityDisplayModel,
} from '#/components/business/identity-display';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

import {
  createIdentityDisplayModel,
  getIdentityDetailTypeLabel,
} from '#/components/business/identity-display';

type MonitoringActorRoleSource = Pick<
  MonitoringActorInfo,
  'display_role_name' | 'role_name'
>;

type MonitoringCallerIdentitySource = Pick<
  MonitoringCallLogInfo,
  | 'caller_avatar'
  | 'caller_display_name'
  | 'caller_display_role_name'
  | 'caller_id'
  | 'caller_is_active'
  | 'caller_is_leader'
  | 'caller_is_owner'
  | 'caller_name'
  | 'caller_nickname'
  | 'caller_org_node_name'
  | 'caller_role_name'
  | 'caller_type'
  | 'caller_username'
>;

interface MonitoringDetailMetaOptions {
  createdAt?: null | string;
  scope: MonitoringScope;
  tenantId?: null | number;
  tenantName?: null | string;
}

function normalizeText(value: null | string | undefined): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }
  const normalized = value.trim();
  return normalized || undefined;
}

function resolveActorTypeColor(type: null | string | undefined): string {
  switch (type) {
    case 'admin':
    case 'platform_admin': {
      return 'gold';
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

export function getActorTypeLabel(type: null | string | undefined): string {
  switch (type) {
    case 'admin':
    case 'platform_admin': {
      return getIdentityDetailTypeLabel('platform_admin');
    }
    case 'tenant_admin': {
      return getIdentityDetailTypeLabel('tenant_admin');
    }
    case 'tenant_user': {
      return getIdentityDetailTypeLabel('tenant_user');
    }
    default: {
      return '';
    }
  }
}

function buildActorTypeBadge(
  type: null | string | undefined,
  key: string,
): IdentityDisplayBadge[] {
  const label = getActorTypeLabel(type);
  if (!label) {
    return [];
  }

  return [
    {
      color: resolveActorTypeColor(type),
      key,
      label,
    },
  ];
}

function resolveMonitoringDisplayRoleName(
  source:
    | MonitoringActorRoleSource
    | Pick<
        MonitoringCallLogInfo,
        'caller_display_role_name' | 'caller_role_name'
      >,
): string | undefined {
  if (Object.prototype.hasOwnProperty.call(source, 'display_role_name')) {
    return normalizeText(
      (source as MonitoringActorRoleSource).display_role_name,
    );
  }
  if (
    Object.prototype.hasOwnProperty.call(source, 'caller_display_role_name')
  ) {
    return normalizeText(
      (
        source as Pick<
          MonitoringCallLogInfo,
          'caller_display_role_name' | 'caller_role_name'
        >
      ).caller_display_role_name,
    );
  }
  if (Object.prototype.hasOwnProperty.call(source, 'role_name')) {
    return normalizeText((source as MonitoringActorRoleSource).role_name);
  }
  return normalizeText(
    (
      source as Pick<
        MonitoringCallLogInfo,
        'caller_display_role_name' | 'caller_role_name'
      >
    ).caller_role_name,
  );
}

function resolveCallerUsername(
  source: MonitoringCallerIdentitySource,
): string | undefined {
  if (
    normalizeText(source.caller_display_name) ||
    normalizeText(source.caller_nickname)
  ) {
    return normalizeText(source.caller_username);
  }
  return (
    normalizeText(source.caller_username) || normalizeText(source.caller_name)
  );
}

export function createMonitoringActorIdentityModel(
  actor?: MonitoringActorInfo | null,
): IdentityDisplayModel | null {
  if (!actor) {
    return null;
  }

  return createIdentityDisplayModel({
    avatar: actor.avatar,
    badges: buildActorTypeBadge(
      actor.type,
      `actor-type-${actor.id ?? actor.username ?? 'unknown'}`,
    ),
    displayName: actor.display_name,
    id: actor.id ?? actor.username ?? actor.display_name ?? 'unknown-actor',
    isActive: actor.is_active,
    isLeader: actor.is_leader,
    isOwner: actor.is_owner,
    nickname: actor.nickname || actor.display_name,
    orgNodeName: actor.org_node_name,
    roleName: resolveMonitoringDisplayRoleName(actor),
    userType: actor.type,
    username:
      normalizeText(actor.display_name) || normalizeText(actor.nickname)
        ? undefined
        : normalizeText(actor.username),
  });
}

export function createMonitoringActorDetailMeta(
  actor: MonitoringActorInfo | null | undefined,
  options: MonitoringDetailMetaOptions,
): IdentityDetailMeta {
  return {
    createdAt: options.createdAt ?? undefined,
    orgNodeName: actor?.org_node_name,
    roleName: actor ? resolveMonitoringDisplayRoleName(actor) : undefined,
    scope: options.scope,
    subjectType: actor?.type,
    tenantId: actor?.tenant_id ?? options.tenantId ?? undefined,
    tenantName: actor?.tenant_name ?? options.tenantName ?? undefined,
    userType: actor?.type,
    username:
      normalizeText(actor?.username) ||
      normalizeText(actor?.display_name) ||
      normalizeText(actor?.nickname),
  };
}

export function createMonitoringCallerIdentityModel(
  source: MonitoringCallerIdentitySource,
): IdentityDisplayModel {
  return createIdentityDisplayModel({
    avatar: source.caller_avatar,
    badges: buildActorTypeBadge(
      source.caller_type,
      `caller-type-${source.caller_id ?? source.caller_username ?? source.caller_name ?? 'unknown'}`,
    ),
    displayName: source.caller_display_name,
    id:
      source.caller_id ??
      source.caller_username ??
      source.caller_name ??
      'unknown-caller',
    isActive: source.caller_is_active,
    isLeader: source.caller_is_leader,
    isOwner: source.caller_is_owner,
    nickname: source.caller_nickname || source.caller_name,
    orgNodeName: source.caller_org_node_name,
    roleName: resolveMonitoringDisplayRoleName(source),
    userType: source.caller_type,
    username: resolveCallerUsername(source),
  });
}

export function createMonitoringCallerDetailMeta(
  source: MonitoringCallerIdentitySource,
  options: MonitoringDetailMetaOptions,
): IdentityDetailMeta {
  return {
    createdAt: options.createdAt ?? undefined,
    orgNodeName: source.caller_org_node_name,
    roleName: resolveMonitoringDisplayRoleName(source),
    scope: options.scope,
    subjectType: source.caller_type,
    tenantId: options.tenantId ?? undefined,
    tenantName: options.tenantName ?? undefined,
    userType: source.caller_type,
    username:
      normalizeText(source.caller_username) ||
      normalizeText(source.caller_display_name) ||
      normalizeText(source.caller_nickname) ||
      normalizeText(source.caller_name) ||
      (source.caller_id ? `#${source.caller_id}` : undefined),
  };
}

export function createMonitoringUsageActorIdentityModel(
  item: MonitoringUsageBreakdownItem,
): IdentityDisplayModel | null {
  const actorModel = createMonitoringActorIdentityModel(item.actor);
  if (actorModel) {
    return actorModel;
  }

  const fallbackLabel = normalizeText(item.label) || normalizeText(item.key);
  if (!fallbackLabel) {
    return null;
  }

  return createIdentityDisplayModel({
    displayName: fallbackLabel,
    id: item.key,
    nickname: fallbackLabel,
  });
}

export function createMonitoringUsageActorDetailMeta(
  item: MonitoringUsageBreakdownItem,
  options: MonitoringDetailMetaOptions,
): IdentityDetailMeta {
  return createMonitoringActorDetailMeta(item.actor, {
    ...options,
    tenantId: item.actor?.tenant_id ?? options.tenantId,
    tenantName: item.actor?.tenant_name ?? options.tenantName,
  });
}
