import type { MaybeRefOrGetter } from 'vue';

import { computed, toValue } from 'vue';

import { usePublicConfigStore } from '#/store/shared/public-config';

interface DiagnosticsPolicyOptions {
  apiPrefix?: MaybeRefOrGetter<string | undefined>;
  forceShow?: MaybeRefOrGetter<boolean | undefined>;
}

const TENANT_DIAGNOSTICS_FEATURE_KEYS = [
  'tenant.ai.show_diagnostics',
  'ai.show_diagnostics',
  'show_diagnostics',
  'dev_diagnostics',
] as const;

function readDiagnosticsFeature(
  features?: Record<string, unknown>,
): boolean | undefined {
  if (!features) {
    return undefined;
  }
  for (const key of TENANT_DIAGNOSTICS_FEATURE_KEYS) {
    const feature = features[key];
    if (typeof feature === 'boolean') {
      return feature;
    }
  }
  return undefined;
}

export function useDiagnosticsPolicy(
  options: DiagnosticsPolicyOptions = {},
) {
  let publicConfigStore: null | ReturnType<typeof usePublicConfigStore> = null;
  try {
    publicConfigStore = usePublicConfigStore();
  } catch {
    publicConfigStore = null;
  }

  function isAdminPrefix(apiPrefix: string): boolean {
    return apiPrefix.startsWith('/admin') || apiPrefix.startsWith('/api/admin');
  }

  function isEndUserPrefix(apiPrefix: string): boolean {
    return (
      apiPrefix.startsWith('/tenant') ||
      apiPrefix.startsWith('/api/tenant') ||
      apiPrefix.startsWith('/user') ||
      apiPrefix.startsWith('/api/user')
    );
  }

  const showDiagnostics = computed(() => {
    if (toValue(options.forceShow) === true) {
      return true;
    }

    const apiPrefix = (toValue(options.apiPrefix) ?? '').trim();
    const tenantFeature = readDiagnosticsFeature(
      publicConfigStore?.tenantConfig?.features,
    );
    if (tenantFeature !== undefined && isEndUserPrefix(apiPrefix)) {
      return tenantFeature;
    }

    const platformFeature = readDiagnosticsFeature(
      (
        publicConfigStore?.platformConfig as
          | undefined
          | { features?: Record<string, unknown> }
      )?.features,
    );
    if (platformFeature !== undefined && isAdminPrefix(apiPrefix)) {
      return platformFeature;
    }

    return false;
  });

  return {
    showDiagnostics,
  };
}
