import type {
  IdentityDetailRequest,
  IdentityDetailScope,
} from '#/components/business/identity-display';
import type { IdentityDisplayModel } from '#/components/business/identity-display';

import {
  closeIdentityDetailDialog,
  mergeIdentityDetailFallbacks,
  openIdentityDetailDialog,
  useIdentityDetailDialog,
} from '#/components/business/identity-display';

export interface IdentityDetailMeta {
  approvalStatus?: null | string;
  createdAt?: null | string;
  email?: null | string;
  lastLoginAt?: null | string;
  lastLoginIp?: null | string;
  orgNodeName?: null | string;
  phone?: null | string;
  roleName?: null | string;
  scope?: IdentityDetailScope;
  subjectType?: null | string;
  tenantId?: null | number;
  tenantName?: null | string;
  updatedAt?: null | string;
  userType?: null | string;
  username?: null | string;
}

export interface IdentityDetailPayload {
  context?: string;
  meta?: IdentityDetailMeta;
  model: IdentityDisplayModel;
}

function inferScopeFromLocation(): IdentityDetailScope | undefined {
  if (typeof window === 'undefined') {
    return undefined;
  }
  if (window.location.pathname.startsWith('/tenant')) {
    return 'tenant';
  }
  if (window.location.pathname.startsWith('/admin')) {
    return 'admin';
  }
  return undefined;
}

export function createIdentityDetailRequest(
  payload: IdentityDetailPayload,
): IdentityDetailRequest {
  const meta = payload.meta;
  return {
    fallback: mergeIdentityDetailFallbacks(payload.model, {
      approvalStatus: meta?.approvalStatus,
      createdAt: meta?.createdAt,
      email: meta?.email,
      lastLoginAt: meta?.lastLoginAt,
      lastLoginIp: meta?.lastLoginIp,
      orgNodeName: meta?.orgNodeName ?? payload.model.orgNodeName ?? undefined,
      phone: meta?.phone,
      roleName: meta?.roleName ?? payload.model.roleName ?? undefined,
      tenantId: meta?.tenantId,
      tenantName: meta?.tenantName,
      updatedAt: meta?.updatedAt,
      userType:
        meta?.subjectType ?? meta?.userType ?? payload.model.userType ?? undefined,
      username: meta?.username ?? payload.model.username ?? undefined,
    }),
    id: payload.model.id,
    scope: meta?.scope || inferScopeFromLocation(),
    subjectType:
      meta?.subjectType ?? meta?.userType ?? payload.model.userType ?? undefined,
    tenantId: meta?.tenantId,
    tenantName: meta?.tenantName,
  };
}

export function openIdentityDetailDrawer(payload: IdentityDetailPayload) {
  return openIdentityDetailDialog(createIdentityDetailRequest(payload));
}

export function useIdentityDetailDrawer() {
  return useIdentityDetailDialog();
}

export { closeIdentityDetailDialog };
