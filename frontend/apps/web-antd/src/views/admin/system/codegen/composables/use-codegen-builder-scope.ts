import { computed, ref } from 'vue';

import { message } from 'ant-design-vue';

import { getCodegenOptionsApi } from '#/api/admin/codegen';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import { pluralize } from '../modules/infer';

const COMMON_MODULE_KEYS = ['system', 'business', 'tenant', 'ai'] as const;

function getSuggestedBaseClassFromEndpoints(
  endpoints: Record<string, unknown>[],
): 'BaseModel' | 'TenantModel' {
  const hasTenant = endpoints.some(
    (item) => (item.scope as string) === 'tenant',
  );
  return hasTenant ? 'TenantModel' : 'BaseModel';
}

function shouldSyncAutoRoutePrefix(
  routePrefix: string,
  previousResource: string,
  previousPlural: string,
): boolean {
  const normalized = routePrefix.trim();
  const candidates = new Set(['/items']);

  if (previousResource) {
    candidates.add(`/${previousResource}`);
    candidates.add(`/${pluralize(previousResource)}`);
  }
  if (previousPlural) {
    candidates.add(`/${previousPlural}`);
  }

  return !normalized || candidates.has(normalized);
}

export function useCodegenBuilderScope() {
  const store = useCodegenBuilderStore();
  const moduleOptions = ref<Array<{ label: string; value: string }>>([]);

  const resource = computed({
    get: () => (store.configJson.resource as string) || '',
    set: (value: string) => store.updateConfig({ resource: value }),
  });
  const moduleVal = computed({
    get: () => (store.configJson.module as string) || 'system',
    set: (value: string) => store.updateConfig({ module: value }),
  });
  const normalizedModuleOptions = computed(() => {
    const seen = new Set<string>();
    const merged: Array<{ label: string; value: string }> = [];
    const candidateCodes = [
      ...moduleOptions.value.map((item) => item.value),
      ...COMMON_MODULE_KEYS,
      moduleVal.value || 'system',
    ];

    for (const code of candidateCodes) {
      if (!code || seen.has(code)) continue;
      seen.add(code);
      const key = `admin.system.codegen.basic.moduleLabels.${code}`;
      const translated = $t(key) as string;
      merged.push({
        label: translated === key ? code : translated,
        value: code,
      });
    }

    return merged;
  });
  const commonModuleOptions = computed(() =>
    normalizedModuleOptions.value.filter((item) =>
      COMMON_MODULE_KEYS.includes(
        item.value as (typeof COMMON_MODULE_KEYS)[number],
      ),
    ),
  );
  const displayName = computed({
    get: () => (store.configJson.display_name as string) || '',
    set: (value: string) => store.updateConfig({ display_name: value }),
  });
  const displayNameEn = computed({
    get: () => (store.configJson.display_name_en as string) || '',
    set: (value: string) => store.updateConfig({ display_name_en: value }),
  });
  const resourcePlural = computed({
    get: () => (store.configJson.resource_plural as string) || '',
    set: (value: string) => store.updateConfig({ resource_plural: value }),
  });
  const model = computed(
    () => (store.configJson.model as Record<string, unknown>) || {},
  );
  const endpoints = computed(
    () => (store.configJson.endpoints as Record<string, unknown>[]) || [],
  );
  const firstEndpoint = computed(() => endpoints.value[0] || {});
  const frontend = computed(
    () => (firstEndpoint.value.frontend as Record<string, unknown>) || {},
  );
  const hasAdmin = computed(() =>
    endpoints.value.some((item) => item.scope === 'admin'),
  );
  const hasTenant = computed(() =>
    endpoints.value.some((item) => item.scope === 'tenant'),
  );
  const scopeCount = computed(
    () => Number(hasAdmin.value) + Number(hasTenant.value),
  );
  const feMode = computed({
    get: () => (frontend.value.mode as string) || 'table',
    set: (value: string) => {
      const list = [...endpoints.value];
      if (list.length === 0) return;
      const next = list.map((item) => ({
        ...item,
        frontend: {
          ...(item.frontend as Record<string, unknown>),
          mode: value,
        },
      }));
      store.updateConfig({ endpoints: next });
    },
  });

  function syncBaseClassFromEndpoints(
    nextEndpoints: Record<string, unknown>[],
    previousEndpoints: Record<string, unknown>[] = endpoints.value,
  ) {
    const currentModel = model.value;
    const currentClass = String(currentModel.base_class || '');
    const previousSuggested =
      getSuggestedBaseClassFromEndpoints(previousEndpoints);
    const nextSuggested = getSuggestedBaseClassFromEndpoints(nextEndpoints);

    if (
      (!currentClass || currentClass === previousSuggested) &&
      currentClass !== nextSuggested
    ) {
      store.updateConfig({
        model: { ...currentModel, base_class: nextSuggested },
      });
    }
  }

  function createDefaultEndpoint(
    scope: 'admin' | 'tenant',
  ): Record<string, unknown> {
    const plural =
      (store.configJson.resource_plural as string) ||
      pluralize((store.configJson.resource as string) || 'item');
    return {
      scope,
      data_mode: scope === 'admin' ? 'independent' : 'tenant_isolated',
      route_prefix: `/${plural}`,
      frontend: {
        mode: 'table',
        page_size: 20,
        default_sort: '-created_at',
        search_default_open: false,
        quick_search: true,
        recycle_bin: false,
        export: false,
        import: false,
        drag_sort: false,
      },
    };
  }

  function onAdminChange(checked: boolean) {
    const previousEndpoints = [...endpoints.value];
    if (checked) {
      const hasAdminEndpoint = previousEndpoints.some(
        (item) => (item.scope as string) === 'admin',
      );
      if (!hasAdminEndpoint) {
        const nextEndpoints = [
          createDefaultEndpoint('admin'),
          ...previousEndpoints,
        ];
        store.updateConfig({ endpoints: nextEndpoints });
        syncBaseClassFromEndpoints(nextEndpoints, previousEndpoints);
      }
      return;
    }

    const nextEndpoints = previousEndpoints.filter(
      (item) => (item.scope as string) !== 'admin',
    );
    if (nextEndpoints.length === 0) {
      message.warning($t('admin.system.codegen.builder.atLeastOneScope'));
      return;
    }
    store.updateConfig({ endpoints: nextEndpoints });
    syncBaseClassFromEndpoints(nextEndpoints, previousEndpoints);
  }

  function onTenantChange(checked: boolean) {
    const previousEndpoints = [...endpoints.value];
    if (checked) {
      const hasTenantEndpoint = previousEndpoints.some(
        (item) => (item.scope as string) === 'tenant',
      );
      if (!hasTenantEndpoint) {
        const nextEndpoints = [
          ...previousEndpoints,
          createDefaultEndpoint('tenant'),
        ];
        store.updateConfig({ endpoints: nextEndpoints });
        syncBaseClassFromEndpoints(nextEndpoints, previousEndpoints);
      }
      return;
    }

    const nextEndpoints = previousEndpoints.filter(
      (item) => (item.scope as string) !== 'tenant',
    );
    if (nextEndpoints.length === 0) {
      message.warning($t('admin.system.codegen.builder.atLeastOneScope'));
      return;
    }
    store.updateConfig({ endpoints: nextEndpoints });
    syncBaseClassFromEndpoints(nextEndpoints, previousEndpoints);
  }

  function onResourceChange(value: string) {
    const previousResource = (store.configJson.resource as string) || '';
    const previousPlural = (store.configJson.resource_plural as string) || '';
    const nextPlural = value ? pluralize(value) : '';
    const currentModel =
      (store.configJson.model as Record<string, unknown>) || {};
    const currentTableName = String(currentModel.table_name || '');
    const shouldUpdatePlural =
      Boolean(value) &&
      (!previousPlural || previousPlural === pluralize(previousResource));
    const shouldUpdateTableName =
      Boolean(value) &&
      (!currentTableName ||
        currentTableName === previousResource ||
        currentTableName === previousPlural);
    const nextEndpoints = endpoints.value.map((item) => {
      const routePrefix = String(item.route_prefix || '');
      if (
        !shouldSyncAutoRoutePrefix(
          routePrefix,
          previousResource,
          previousPlural,
        )
      ) {
        return item;
      }
      return {
        ...item,
        route_prefix: nextPlural ? `/${nextPlural}` : routePrefix,
      };
    });

    const patch: Record<string, unknown> = { resource: value };
    if (shouldUpdatePlural) {
      patch.resource_plural = nextPlural;
    }
    if (shouldUpdateTableName) {
      patch.model = { ...currentModel, table_name: nextPlural };
    }
    if (
      nextEndpoints.some(
        (item, index) =>
          item.route_prefix !== endpoints.value[index]?.route_prefix,
      )
    ) {
      patch.endpoints = nextEndpoints;
    }
    store.updateConfig(patch);
  }

  async function loadModules() {
    try {
      const options = await getCodegenOptionsApi();
      const modules = options?.system_modules ?? [];
      moduleOptions.value = modules.map((item: string) => ({
        label: (() => {
          const key = `admin.system.codegen.basic.moduleLabels.${item}`;
          const translated = $t(key) as string;
          return translated === key ? item : translated;
        })(),
        value: item,
      }));
    } catch {
      moduleOptions.value = [];
    }
  }

  return {
    commonModuleOptions,
    displayName,
    displayNameEn,
    endpoints,
    feMode,
    firstEndpoint,
    frontend,
    hasAdmin,
    hasTenant,
    loadModules,
    model,
    moduleVal,
    normalizedModuleOptions,
    onAdminChange,
    onResourceChange,
    onTenantChange,
    resource,
    resourcePlural,
    scopeCount,
  };
}

export type CodegenBuilderScopeState = ReturnType<
  typeof useCodegenBuilderScope
>;
