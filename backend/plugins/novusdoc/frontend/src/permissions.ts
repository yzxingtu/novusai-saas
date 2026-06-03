import type { NovusPluginSharedAPI } from './types';

type AccessMode = 'all' | 'any';
type PermissionAction = 'create' | 'delete' | 'export' | 'update' | 'view';
type PermissionSet = Record<PermissionAction, string>;

const ADMIN_PERMISSION_CODES: PermissionSet = {
  view: 'plugin.novusdoc.novusdoc_admin:view',
  create: 'plugin.novusdoc.novusdoc_admin:create',
  update: 'plugin.novusdoc.novusdoc_admin:update',
  delete: 'plugin.novusdoc.novusdoc_admin:delete',
  export: 'plugin.novusdoc.novusdoc_admin:export',
};

const TENANT_PERMISSION_CODES: PermissionSet = {
  view: 'plugin.novusdoc.novusdoc_portal:view',
  create: 'plugin.novusdoc.novusdoc_portal:create',
  update: 'plugin.novusdoc.novusdoc_portal:update',
  delete: 'plugin.novusdoc.novusdoc_portal:delete',
  export: 'plugin.novusdoc.novusdoc_portal:export',
};

type SharedAccessApi = Pick<
  NovusPluginSharedAPI,
  'getAccessCodes' | 'hasAccessByCodes'
>;

function normalizeCodes(codes: string | string[] | undefined): string[] {
  if (Array.isArray(codes)) {
    return codes.filter(Boolean);
  }
  if (codes) {
    return [codes];
  }
  return [];
}

function getSharedAccessApi(): SharedAccessApi | undefined {
  return (window as unknown as { NovusPluginShared?: SharedAccessApi })
    .NovusPluginShared;
}

export function getNovusdocPermissionCodes(
  scope: 'admin' | 'tenant',
): PermissionSet {
  return scope === 'admin'
    ? ADMIN_PERMISSION_CODES
    : TENANT_PERMISSION_CODES;
}

export function resolveRouteAccessCodes(
  routeMeta: Record<string, unknown> | undefined,
  fallbackCodes: string[] = [],
): string[] {
  const raw = routeMeta?.accessCodes;
  if (Array.isArray(raw)) {
    return raw.filter(
      (code): code is string => typeof code === 'string' && !!code,
    );
  }
  if (typeof raw === 'string' && raw) {
    return [raw];
  }
  return fallbackCodes;
}

export function hasNovusdocAccess(
  codes: string | string[] | undefined,
  options: {
    mode?: AccessMode;
    shared?: SharedAccessApi;
  } = {},
): boolean {
  const requestedCodes = normalizeCodes(codes);
  if (requestedCodes.length === 0) {
    return true;
  }

  const shared = options.shared ?? getSharedAccessApi();
  if (typeof shared?.hasAccessByCodes === 'function') {
    return shared.hasAccessByCodes(requestedCodes, { mode: options.mode });
  }

  if (typeof shared?.getAccessCodes !== 'function') {
    return false;
  }

  const accessCodes = shared.getAccessCodes() ?? [];
  if (accessCodes.includes('*')) {
    return true;
  }

  if (options.mode === 'all') {
    return requestedCodes.every((code) => accessCodes.includes(code));
  }

  return requestedCodes.some((code) => accessCodes.includes(code));
}
