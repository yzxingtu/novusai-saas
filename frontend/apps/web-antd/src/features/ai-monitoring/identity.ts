import type {
  MonitoringActorInfo,
  MonitoringCallLogInfo,
  MonitoringUsageBreakdownItem,
} from './api';

import type {
  IdentityDisplayBadge,
  IdentityDisplayModel,
} from '#/components/business/identity-display';

import { createIdentityDisplayModel } from '#/components/business/identity-display';
import { $t } from '#/locales';

function getActorTypeColor(type: null | string | undefined): string {
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
      return $t('common.admin');
    }
    case 'tenant_admin': {
      return $t('common.tenant_admin');
    }
    case 'tenant_user': {
      return $t('common.user');
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
      color: getActorTypeColor(type),
      key,
      label,
    },
  ];
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
    id: actor.id ?? actor.username ?? 'unknown-actor',
    isActive: actor.is_active,
    isLeader: actor.is_leader,
    isOwner: actor.is_owner,
    nickname: actor.nickname || actor.display_name,
    orgNodeName: actor.org_node_name,
    roleName: actor.role_name,
    username: actor.display_name || actor.nickname ? undefined : actor.username,
  });
}

type MonitoringCallerIdentitySource = Pick<
  MonitoringCallLogInfo,
  | 'caller_avatar'
  | 'caller_display_name'
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
    roleName: source.caller_role_name,
    username:
      source.caller_display_name || source.caller_nickname
        ? undefined
        : source.caller_username,
  });
}

export function createMonitoringUsageActorIdentityModel(
  item: MonitoringUsageBreakdownItem,
): IdentityDisplayModel | null {
  return createMonitoringActorIdentityModel(item.actor);
}
