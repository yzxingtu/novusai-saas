import type { IdentityDisplayModel, IdentityValue } from './types';

import type { TenantAdminIdentityDetail as AdminTenantAdminIdentityDetail } from '#/api/admin/tenant';
import type { AdminIdentityDetail } from '#/api/admin/users';
import type { TenantAdminIdentityDetail } from '#/api/tenant/admins';
import type { TenantUserInfo } from '#/api/tenant/tenant-users';

import { getTenantAdminDetailApi as getAdminTenantAdminDetailApi } from '#/api/admin/tenant';
import { getAdminTenantUserIdentityDetailApi } from '#/api/admin/tenant-users';
import { getAdminIdentityDetailApi } from '#/api/admin/users';
import { getTenantAdminIdentityDetailApi } from '#/api/tenant/admins';
import { getTenantUserDetailApi } from '#/api/tenant/tenant-users';
import { $t } from '#/locales';

import {
  createIdentityDisplayModel,
  resolveIdentityDisplayTitle,
} from './types';

export type IdentityDetailScope = 'admin' | 'tenant';

export type IdentitySubjectType =
  | 'admin'
  | 'platform_admin'
  | 'system_admin'
  | 'tenant_admin'
  | 'tenant_user'
  | 'unknown';

export interface IdentityDetail extends Omit<IdentityDisplayModel, 'id'> {
  approvalStatus?: null | string;
  createdAt?: null | string;
  detailScope?: IdentityDetailScope;
  displayName?: null | string;
  email?: null | string;
  id: IdentityValue;
  isSuper?: boolean;
  lastLoginAt?: null | string;
  lastLoginIp?: null | string;
  phone?: null | string;
  tenantId?: null | number;
  tenantName?: null | string;
  updatedAt?: null | string;
  userType?: null | string;
}

export interface IdentityDetailRequest {
  disableFetch?: boolean;
  fallback?: null | Partial<IdentityDetail>;
  id: IdentityValue;
  scope?: IdentityDetailScope;
  subjectType?: null | string;
  tenantId?: null | number;
  tenantName?: null | string;
}

type IdentityDetailFetcher = (
  request: IdentityDetailRequest,
) => Promise<null | Partial<IdentityDetail>>;

const identityDetailFetchers = new Map<string, IdentityDetailFetcher>();

function registryKey(
  scope: IdentityDetailScope,
  subjectType: IdentitySubjectType,
): string {
  return `${scope}:${subjectType}`;
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

function toOptionalString(value?: null | string): string | undefined {
  const normalized = firstNonEmpty(value);
  return normalized || undefined;
}

function resolveRawDetailRoleName(
  detail:
    | {
        display_role_name?: null | string;
        role_name?: null | string;
      }
    | {
        displayRoleName?: null | string;
        roleName?: null | string;
      },
): string | undefined {
  if (Object.prototype.hasOwnProperty.call(detail, 'display_role_name')) {
    return toOptionalString(
      (detail as { display_role_name?: null | string }).display_role_name,
    );
  }
  if (Object.prototype.hasOwnProperty.call(detail, 'displayRoleName')) {
    return toOptionalString(
      (detail as { displayRoleName?: null | string }).displayRoleName,
    );
  }
  if (Object.prototype.hasOwnProperty.call(detail, 'role_name')) {
    return toOptionalString(
      (detail as { role_name?: null | string }).role_name,
    );
  }
  return Object.prototype.hasOwnProperty.call(detail, 'roleName')
    ? toOptionalString((detail as { roleName?: null | string }).roleName)
    : undefined;
}

export function normalizeIdentitySubjectType(
  subjectType?: null | string,
): IdentitySubjectType {
  const normalized = firstNonEmpty(subjectType).toLowerCase();
  switch (normalized) {
    case 'admin':
    case 'platform_admin':
    case 'system_admin': {
      return 'admin';
    }
    case 'tenant_admin': {
      return 'tenant_admin';
    }
    case 'tenant_user': {
      return 'tenant_user';
    }
    default: {
      return normalized ? 'unknown' : 'unknown';
    }
  }
}

export function toIdentityDetailFallback(
  detail?: IdentityDisplayModel | null | Partial<IdentityDetail>,
): Partial<IdentityDetail> | undefined {
  if (!detail) {
    return undefined;
  }

  const source = detail as IdentityDisplayModel & Partial<IdentityDetail>;
  return {
    ...source,
    approvalStatus: toOptionalString(source.approvalStatus),
    badges: source.badges ? [...source.badges] : undefined,
    createdAt: toOptionalString(source.createdAt),
    detailScope: source.detailScope,
    displayName: toOptionalString(source.displayName),
    email: toOptionalString(source.email),
    lastLoginAt: toOptionalString(source.lastLoginAt),
    lastLoginIp: toOptionalString(source.lastLoginIp),
    nickname: toOptionalString(source.nickname),
    orgNodeName: toOptionalString(source.orgNodeName),
    phone: toOptionalString(source.phone),
    realName: toOptionalString(source.realName),
    roleName: toOptionalString(source.roleName),
    secondaryText: toOptionalString(source.secondaryText),
    tenantName: toOptionalString(source.tenantName),
    updatedAt: toOptionalString(source.updatedAt),
    userType: toOptionalString(source.userType),
    userTypeLabel: toOptionalString(source.userTypeLabel),
    username: toOptionalString(source.username),
  };
}

export function mergeIdentityDetailFallbacks(
  ...sources: Array<
    IdentityDisplayModel | null | Partial<IdentityDetail> | undefined
  >
): Partial<IdentityDetail> | undefined {
  const merged: Partial<IdentityDetail> = {};
  let hasValue = false;

  for (const source of sources) {
    const normalized = toIdentityDetailFallback(source);
    if (!normalized) {
      continue;
    }

    for (const [key, value] of Object.entries(normalized)) {
      if (value === undefined) {
        continue;
      }
      hasValue = true;
      Object.assign(merged, {
        [key]: value,
      });
    }
  }

  return hasValue ? merged : undefined;
}

function normalizeIdentityDetail(
  request: IdentityDetailRequest,
  detail?: null | Partial<IdentityDetail>,
): IdentityDetail {
  const merged = {
    ...request.fallback,
    ...detail,
  };
  const displayModel = createIdentityDisplayModel({
    avatar: merged.avatar,
    badges: merged.badges,
    displayName: merged.displayName,
    id: merged.id ?? request.id,
    isActive: merged.isActive,
    isLeader: merged.isLeader,
    isOwner: merged.isOwner,
    nickname: merged.nickname,
    orgNodeId: merged.orgNodeId,
    orgNodeName: merged.orgNodeName,
    realName: merged.realName,
    roleName: merged.roleName,
    secondaryText:
      merged.secondaryText ?? firstNonEmpty(merged.username, merged.email),
    userType: merged.userType,
    userTypeLabel: merged.userTypeLabel,
    username: merged.username,
  });

  const userType =
    firstNonEmpty(merged.userType, request.subjectType) ||
    normalizeIdentitySubjectType(request.subjectType);

  return {
    ...displayModel,
    approvalStatus: merged.approvalStatus,
    createdAt: merged.createdAt,
    detailScope: request.scope,
    displayName:
      displayModel.displayName || resolveIdentityDisplayTitle(displayModel),
    email: merged.email,
    id: merged.id ?? request.id,
    isSuper: merged.isSuper,
    lastLoginAt: merged.lastLoginAt,
    lastLoginIp: merged.lastLoginIp,
    phone: merged.phone,
    tenantId: merged.tenantId ?? request.tenantId,
    tenantName: merged.tenantName ?? request.tenantName,
    updatedAt: merged.updatedAt,
    userType,
  };
}

export function createIdentityDetailPreview(
  request: IdentityDetailRequest,
): IdentityDetail {
  return normalizeIdentityDetail(request);
}

export function registerIdentityDetailFetcher(
  scope: IdentityDetailScope,
  subjectType: IdentitySubjectType,
  fetcher: IdentityDetailFetcher,
): () => void {
  const key = registryKey(scope, subjectType);
  identityDetailFetchers.set(key, fetcher);
  return () => {
    identityDetailFetchers.delete(key);
  };
}

function getIdentityDetailFetcher(
  request: IdentityDetailRequest,
): IdentityDetailFetcher | null {
  if (!request.scope) {
    return null;
  }
  const subjectType = normalizeIdentitySubjectType(request.subjectType);
  return (
    identityDetailFetchers.get(registryKey(request.scope, subjectType)) ?? null
  );
}

function canRequestIdentityDetail(id: IdentityValue): id is number {
  return typeof id === 'number' && Number.isFinite(id);
}

export async function loadIdentityDetail(
  request: IdentityDetailRequest,
): Promise<IdentityDetail> {
  const fallbackDetail = normalizeIdentityDetail(request);
  if (request.disableFetch || !canRequestIdentityDetail(request.id)) {
    return fallbackDetail;
  }

  const fetcher = getIdentityDetailFetcher(request);
  if (!fetcher) {
    return fallbackDetail;
  }

  const loadedDetail = await fetcher(request);
  return normalizeIdentityDetail(request, loadedDetail);
}

export function getIdentityDetailTypeLabel(userType?: null | string): string {
  switch (normalizeIdentitySubjectType(userType)) {
    case 'admin': {
      return $t('shared.identity.userTypes.admin');
    }
    case 'tenant_admin': {
      return $t('shared.identity.userTypes.tenantAdmin');
    }
    case 'tenant_user': {
      return $t('shared.identity.userTypes.tenantUser');
    }
    default: {
      return $t('shared.identity.userTypes.unknown');
    }
  }
}

export function getIdentityApprovalStatusLabel(
  approvalStatus?: null | string,
): string {
  switch (firstNonEmpty(approvalStatus).toLowerCase()) {
    case 'approved': {
      return $t('shared.identity.approval.approved');
    }
    case 'pending': {
      return $t('shared.identity.approval.pending');
    }
    case 'rejected': {
      return $t('shared.identity.approval.rejected');
    }
    default: {
      return $t('shared.identity.field.empty');
    }
  }
}

export function getIdentityStatusLabel(isActive?: boolean): string {
  return isActive === false
    ? $t('shared.common.statusDisabled')
    : $t('shared.common.statusEnabled');
}

function mapAdminIdentityDetail(
  detail: AdminIdentityDetail,
): Partial<IdentityDetail> {
  return {
    avatar: detail.avatar,
    createdAt: detail.created_at,
    displayName: detail.display_name ?? undefined,
    email: detail.email,
    id: detail.id,
    isActive: detail.is_active,
    isLeader: detail.is_leader,
    isOwner: detail.is_owner,
    isSuper: detail.is_super,
    lastLoginAt: detail.last_login_at,
    lastLoginIp: detail.last_login_ip,
    nickname: detail.nickname,
    orgNodeId: detail.org_node_id,
    orgNodeName: detail.org_node_name,
    phone: detail.phone,
    roleName: resolveRawDetailRoleName(detail),
    updatedAt: detail.updated_at,
    userType: detail.user_type ?? undefined,
    username: detail.username ?? undefined,
  };
}

function mapTenantAdminIdentityDetail(
  detail: AdminTenantAdminIdentityDetail | TenantAdminIdentityDetail,
): Partial<IdentityDetail> {
  return {
    avatar: detail.avatar,
    createdAt: detail.created_at,
    displayName: detail.display_name ?? undefined,
    email: detail.email,
    id: detail.id,
    isActive: detail.is_active,
    isLeader: detail.is_leader,
    isOwner: detail.is_owner,
    lastLoginAt: detail.last_login_at,
    lastLoginIp: detail.last_login_ip,
    nickname: detail.nickname,
    orgNodeId: detail.org_node_id,
    orgNodeName: detail.org_node_name,
    phone: detail.phone,
    roleName: resolveRawDetailRoleName(detail),
    tenantId: detail.tenant_id,
    updatedAt: detail.updated_at,
    userType: detail.user_type ?? undefined,
    username: detail.username ?? undefined,
  };
}

function mapTenantUserIdentityDetail(
  detail: TenantUserInfo,
): Partial<IdentityDetail> {
  return {
    approvalStatus: detail.approvalStatus,
    avatar: detail.avatar,
    createdAt: detail.createdAt,
    displayName: detail.displayName ?? undefined,
    email: detail.email,
    id: detail.id,
    isActive: detail.isActive,
    isLeader: detail.isLeader,
    isOwner: detail.isOwner,
    lastLoginAt: detail.lastLoginAt,
    lastLoginIp: detail.lastLoginIp,
    nickname: detail.nickname,
    orgNodeId: detail.orgNodeId,
    orgNodeName: detail.orgNodeName,
    phone: detail.phone,
    roleName: resolveRawDetailRoleName(detail),
    tenantId: detail.tenantId,
    updatedAt: detail.updatedAt,
    userType: detail.userType ?? undefined,
    username: detail.username ?? undefined,
  };
}

let builtInFetchersRegistered = false;

function registerBuiltInIdentityDetailFetchers() {
  if (builtInFetchersRegistered) {
    return;
  }
  builtInFetchersRegistered = true;

  registerIdentityDetailFetcher('admin', 'admin', async (request) =>
    mapAdminIdentityDetail(await getAdminIdentityDetailApi(Number(request.id))),
  );

  registerIdentityDetailFetcher('admin', 'tenant_admin', async (request) => {
    if (typeof request.tenantId !== 'number') {
      return null;
    }
    return mapTenantAdminIdentityDetail(
      await getAdminTenantAdminDetailApi(request.tenantId, Number(request.id)),
    );
  });

  registerIdentityDetailFetcher('admin', 'tenant_user', async (request) => {
    if (typeof request.tenantId !== 'number') {
      return null;
    }
    return mapTenantUserIdentityDetail(
      await getAdminTenantUserIdentityDetailApi(
        request.tenantId,
        Number(request.id),
      ),
    );
  });

  registerIdentityDetailFetcher('tenant', 'tenant_admin', async (request) =>
    mapTenantAdminIdentityDetail(
      await getTenantAdminIdentityDetailApi(Number(request.id)),
    ),
  );

  registerIdentityDetailFetcher('tenant', 'tenant_user', async (request) =>
    mapTenantUserIdentityDetail(
      await getTenantUserDetailApi(Number(request.id)),
    ),
  );
}

registerBuiltInIdentityDetailFetchers();
