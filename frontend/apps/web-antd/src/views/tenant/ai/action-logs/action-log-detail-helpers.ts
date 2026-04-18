import type { ActionLogItem } from '#/api/tenant/action-logs';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

import { $t } from '#/locales';
import { toAvatarDisplayUrl } from '#/utils/image';

export type DetailTabKey = 'error' | 'overview' | 'request' | 'response';
export type PayloadEntryKind = 'json' | 'scalar';

export interface PayloadEntry {
  key: string;
  kind: PayloadEntryKind;
  valueText: string;
}

type ActionLogAgentSource = Pick<ActionLogItem, 'agent_id' | 'agent_name'>;
type ActionLogOperatorSource = Pick<
  ActionLogItem,
  | 'created_at'
  | 'operator_avatar'
  | 'operator_display_name'
  | 'operator_id'
  | 'operator_is_active'
  | 'operator_is_leader'
  | 'operator_is_owner'
  | 'operator_name'
  | 'operator_nickname'
  | 'operator_org_node_name'
  | 'operator_role_name'
  | 'operator_type'
>;

function getOperatorTypeText(operatorType: null | string | undefined): string {
  switch (operatorType) {
    case 'admin':
    case 'platform_admin': {
      return $t('tenant.ai.actionLog.operatorTypes.admin');
    }
    case 'tenant_admin': {
      return $t('tenant.ai.actionLog.operatorTypes.tenantAdmin');
    }
    case 'tenant_user': {
      return $t('tenant.ai.actionLog.operatorTypes.tenantUser');
    }
    default: {
      return '';
    }
  }
}

function getOperatorTypeColor(operatorType: null | string | undefined): string {
  switch (operatorType) {
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

function getOperatorDisplayName(
  log: ActionLogOperatorSource | null | undefined,
): string {
  return (
    log?.operator_display_name ||
    log?.operator_nickname ||
    log?.operator_name ||
    (log?.operator_id ? `#${log.operator_id}` : '-')
  );
}

function isStructuredValue(
  value: unknown,
): value is Record<string, unknown> | unknown[] {
  return Array.isArray(value) || (!!value && typeof value === 'object');
}

function tryFormatStringAsJson(value: string): null | string {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const looksLikeJson =
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'));
  if (!looksLikeJson) {
    return null;
  }

  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2);
  } catch {
    return null;
  }
}

export function getAgentDisplayName(log: ActionLogAgentSource): string {
  if (log.agent_name) {
    return log.agent_name;
  }

  if (log.agent_id && log.agent_id > 0) {
    return `#${log.agent_id}`;
  }

  return $t('tenant.ai.actionLog.agentUnavailable');
}

export function getOperatorIdentityModel(
  log: ActionLogOperatorSource | null | undefined,
) {
  const typeText = getOperatorTypeText(log?.operator_type);

  return {
    avatar: log?.operator_avatar,
    badges: typeText
      ? [
          {
            color: getOperatorTypeColor(log?.operator_type),
            key: `operator-type-${log?.operator_id ?? log?.operator_name ?? 'unknown'}`,
            label: typeText,
          },
        ]
      : [],
    displayName: log?.operator_display_name,
    id: log?.operator_id ?? '-',
    isActive: log?.operator_is_active,
    isLeader: log?.operator_is_leader,
    isOwner: log?.operator_is_owner,
    nickname: getOperatorDisplayName(log),
    orgNodeName: log?.operator_org_node_name,
    roleName: log?.operator_role_name,
    userType: log?.operator_type,
    username:
      log?.operator_display_name || log?.operator_nickname
        ? undefined
        : (log?.operator_name ?? undefined),
  };
}

export function buildOperatorMeta(
  log: ActionLogOperatorSource | null | undefined,
): IdentityDetailMeta {
  return {
    createdAt: log?.created_at,
    orgNodeName: log?.operator_org_node_name,
    roleName: log?.operator_role_name,
    scope: 'tenant',
    subjectType: log?.operator_type,
    userType: log?.operator_type,
    username:
      log?.operator_name ||
      log?.operator_display_name ||
      log?.operator_nickname ||
      undefined,
  };
}

export function isIconAvatar(avatar: null | string | undefined): boolean {
  return Boolean(avatar && String(avatar).includes(':'));
}

export function getInitialLetter(value: null | string | undefined): string {
  const text = String(value || '').trim();
  return text ? text.charAt(0).toUpperCase() : '?';
}

export function getAgentAvatarUrl(
  avatar: null | string | undefined,
): null | string {
  if (!avatar || isIconAvatar(avatar)) {
    return null;
  }

  return toAvatarDisplayUrl(avatar);
}

export function stringifyPayload(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }

  if (typeof value === 'string') {
    return tryFormatStringAsJson(value) ?? value;
  }

  if (isStructuredValue(value)) {
    return JSON.stringify(value, null, 2);
  }

  return String(value);
}

export function buildPayloadEntries(
  payload: null | Record<string, unknown>,
): PayloadEntry[] {
  if (!payload) {
    return [];
  }

  return Object.entries(payload).map(([key, value]) => ({
    key,
    kind: isStructuredValue(value) ? 'json' : 'scalar',
    valueText: stringifyPayload(value) || '-',
  }));
}

export function formatDuration(durationMs: null | number | undefined): string {
  return durationMs ? `${durationMs}ms` : '-';
}

export function formatPayloadSize(payloadText: string): string {
  if (!payloadText) {
    return '-';
  }

  const bytes = new TextEncoder().encode(payloadText).length;
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
