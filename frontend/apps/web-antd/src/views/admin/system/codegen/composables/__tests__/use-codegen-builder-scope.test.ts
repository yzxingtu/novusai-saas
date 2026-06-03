import { reactive } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

type BuilderRecord = Record<string, unknown>;

const storeState = reactive<{
  configJson: BuilderRecord;
}>({
  configJson: {},
});

function deepMerge(target: BuilderRecord, patch: BuilderRecord): BuilderRecord {
  const result: BuilderRecord = { ...target };
  for (const [key, value] of Object.entries(patch)) {
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      const current = result[key];
      result[key] = deepMerge(
        typeof current === 'object' &&
          current !== null &&
          !Array.isArray(current)
          ? (current as BuilderRecord)
          : {},
        value as BuilderRecord,
      );
      continue;
    }
    result[key] = value;
  }
  return result;
}

const updateConfig = vi.fn((patch: BuilderRecord) => {
  storeState.configJson = deepMerge(storeState.configJson, patch);
});

vi.mock('ant-design-vue', () => ({
  message: {
    warning: vi.fn(),
  },
}));

vi.mock('#/api/admin/codegen', () => ({
  getCodegenOptionsApi: vi.fn(async () => ({
    system_modules: ['system', 'tenant'],
  })),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/store', () => ({
  useCodegenBuilderStore: () => ({
    configJson: storeState.configJson,
    updateConfig,
  }),
}));

describe('useCodegenBuilderScope', () => {
  beforeEach(() => {
    updateConfig.mockClear();
    storeState.configJson = {};
  });

  it('ignores malformed model and endpoint entries while preserving valid tenant scope', async () => {
    const { useCodegenBuilderScope } =
      await import('../use-codegen-builder-scope');

    storeState.configJson = {
      endpoints: [
        'broken',
        {
          frontend: 'invalid',
          route_prefix: '/tenant-items',
          scope: 'tenant',
        },
        null,
      ],
      model: ['bad'],
      module: 'tenant',
      resource: 'item',
      resource_plural: 'items',
    };

    const scope = useCodegenBuilderScope();

    expect(scope.model.value).toEqual({});
    expect(scope.endpoints.value).toHaveLength(1);
    expect(scope.hasAdmin.value).toBe(false);
    expect(scope.hasTenant.value).toBe(true);
    expect(scope.feMode.value).toBe('table');

    scope.feMode.value = 'cards';

    expect(storeState.configJson.endpoints).toEqual([
      expect.objectContaining({
        frontend: expect.objectContaining({
          mode: 'cards',
        }),
        route_prefix: '/tenant-items',
        scope: 'tenant',
      }),
    ]);
  });

  it('syncs base class from normalized endpoint scopes when enabling admin scope', async () => {
    const { useCodegenBuilderScope } =
      await import('../use-codegen-builder-scope');

    storeState.configJson = {
      endpoints: [{ route_prefix: '/orders', scope: 'tenant' }],
      model: {},
      resource: 'order',
      resource_plural: 'orders',
    };

    const scope = useCodegenBuilderScope();
    scope.onAdminChange(true);

    const endpoints = storeState.configJson.endpoints as BuilderRecord[];
    expect(endpoints).toHaveLength(2);
    expect(endpoints[0]).toEqual(
      expect.objectContaining({
        scope: 'admin',
      }),
    );
    expect((storeState.configJson.model as BuilderRecord).base_class).toBe(
      'TenantModel',
    );
  });
});
