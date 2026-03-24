import type { TenantPluginSharedApi } from '../types/tenant';

type AccessCodeInput = readonly string[] | string | undefined;
type AccessMode = 'all' | 'any';

export const WORKFLOW_ACCESS_CODES = {
  ADMIN_ORCHESTRATION_VIEW:
    'plugin.workflow-orchestration.orchestration_admin:view',
  ADMIN_PLATFORM_TEMPLATE_CREATE:
    'plugin.workflow-orchestration.platform_template:create',
  ADMIN_PLATFORM_TEMPLATE_LIST:
    'plugin.workflow-orchestration.platform_template:list',
  ADMIN_RELEASE_OPS_LIST: 'plugin.workflow-orchestration.release_ops:list',
  ADMIN_RUNTIME_OPS_LIST: 'plugin.workflow-orchestration.runtime_ops:list',
  ARTIFACT_CENTER_EXPORT:
    'plugin.workflow-orchestration.artifact_center:export',
  ARTIFACT_CENTER_FEEDBACK:
    'plugin.workflow-orchestration.artifact_center:feedback',
  ARTIFACT_CENTER_LIST: 'plugin.workflow-orchestration.artifact_center:list',
  ARTIFACT_CENTER_VIEW: 'plugin.workflow-orchestration.artifact_center:view',
  WORKFLOW_BUILDER_COPY:
    'plugin.workflow-orchestration.workflow_builder:copy',
  WORKFLOW_BUILDER_CREATE:
    'plugin.workflow-orchestration.workflow_builder:create',
  WORKFLOW_BUILDER_EDIT:
    'plugin.workflow-orchestration.workflow_builder:edit',
  WORKFLOW_BUILDER_PUBLISH:
    'plugin.workflow-orchestration.workflow_builder:publish',
  WORKFLOW_CENTER_LIST: 'plugin.workflow-orchestration.workflow_center:list',
  WORKFLOW_CENTER_VIEW: 'plugin.workflow-orchestration.workflow_center:view',
  WORKFLOW_RUN_EXECUTE: 'plugin.workflow-orchestration.workflow_run:execute',
  WORKFLOW_RUN_LIST: 'plugin.workflow-orchestration.workflow_run:list',
  WORKFLOW_RUN_PAUSE: 'plugin.workflow-orchestration.workflow_run:pause',
  WORKFLOW_RUN_RESUME: 'plugin.workflow-orchestration.workflow_run:resume',
  WORKFLOW_RUN_RETRY: 'plugin.workflow-orchestration.workflow_run:retry',
  WORKFLOW_RUN_TERMINATE:
    'plugin.workflow-orchestration.workflow_run:terminate',
  WORKFLOW_RUN_VIEW: 'plugin.workflow-orchestration.workflow_run:view',
} as const;

export const ADMIN_HOME_PAGE_ACCESS_CODES = [
  WORKFLOW_ACCESS_CODES.ADMIN_ORCHESTRATION_VIEW,
  WORKFLOW_ACCESS_CODES.ADMIN_PLATFORM_TEMPLATE_LIST,
  WORKFLOW_ACCESS_CODES.ADMIN_RELEASE_OPS_LIST,
  WORKFLOW_ACCESS_CODES.ADMIN_RUNTIME_OPS_LIST,
] as const;

export const TENANT_HOME_PAGE_ACCESS_CODES = [
  WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_VIEW,
  WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_LIST,
  WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_LIST,
  WORKFLOW_ACCESS_CODES.ARTIFACT_CENTER_LIST,
] as const;

export const TENANT_WORKFLOW_CREATE_PAGE_ACCESS_CODES = [
  WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_CREATE,
  WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_COPY,
] as const;

export const TENANT_WORKFLOW_LIST_PAGE_ACCESS_CODES = [
  WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_LIST,
] as const;

export const TENANT_WORKFLOW_DETAIL_PAGE_ACCESS_CODES = [
  WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_VIEW,
] as const;

export const TENANT_RUN_LIST_PAGE_ACCESS_CODES = [
  WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_LIST,
] as const;

export const TENANT_RUN_DETAIL_PAGE_ACCESS_CODES = [
  WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_VIEW,
] as const;

export const TENANT_ARTIFACT_DETAIL_PAGE_ACCESS_CODES = [
  WORKFLOW_ACCESS_CODES.ARTIFACT_CENTER_VIEW,
] as const;

export const TENANT_BUILDER_CAPABILITY_ACCESS_CODES = [
  WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_CREATE,
  WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_COPY,
  WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_EDIT,
  WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_PUBLISH,
] as const;

export const TENANT_RUN_ACTION_ACCESS_CODES = {
  pause: WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_PAUSE,
  resume: WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_RESUME,
  retry: WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_RETRY,
  terminate: WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_TERMINATE,
} as const;

function readShared(): TenantPluginSharedApi | undefined {
  return (window as unknown as Record<string, unknown>)
    .NovusPluginShared as TenantPluginSharedApi | undefined;
}

function normalizeAccessCodes(codes: AccessCodeInput): string[] {
  const normalized = Array.isArray(codes) ? codes : codes ? [codes] : [];
  return Array.from(
    new Set(
      normalized
        .map((code) => code.trim())
        .filter((code) => code.length > 0),
    ),
  );
}

export function getPluginAccessCodes(): string[] {
  try {
    return normalizeAccessCodes(readShared()?.getAccessCodes?.());
  } catch {
    return [];
  }
}

export function hasPluginAccess(
  codes: AccessCodeInput,
  options?: { mode?: AccessMode },
): boolean {
  const normalized = normalizeAccessCodes(codes);
  const mode = options?.mode ?? 'all';

  if (normalized.length === 0) {
    return true;
  }

  try {
    const shared = readShared();
    if (shared?.hasAccessByCodes) {
      return Boolean(
        shared.hasAccessByCodes(
          normalized.length === 1 ? normalized[0] : normalized,
          { mode },
        ),
      );
    }
  } catch {
    // Fall back to the raw access-code snapshot below.
  }

  const accessCodes = new Set(getPluginAccessCodes());
  if (accessCodes.size === 0) {
    return false;
  }

  return mode === 'any'
    ? normalized.some((code) => accessCodes.has(code))
    : normalized.every((code) => accessCodes.has(code));
}

export function hasAnyPluginAccess(codes: AccessCodeInput): boolean {
  return hasPluginAccess(codes, { mode: 'any' });
}

export function hasAllPluginAccess(codes: AccessCodeInput): boolean {
  return hasPluginAccess(codes, { mode: 'all' });
}
