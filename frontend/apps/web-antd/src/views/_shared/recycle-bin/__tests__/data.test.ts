import type { VbenFormSchema } from '#/adapter/form';

import { describe, expect, it, vi } from 'vitest';

vi.mock('#/adapter/form', () => ({
  searchInput: (
    field: string,
    label: string,
    options: { op?: 'eq' | 'ilike' | 'like' } = {},
  ) => ({
    component: 'Input',
    fieldName:
      options.op === 'eq'
        ? `filter[${field}]`
        : `filter[${field}][${options.op ?? 'ilike'}]`,
    label,
  }),
  statusSelect: ({ field = 'is_active', label = 'Status' } = {}) => ({
    component: 'Select',
    fieldName: `filter[${field}]`,
    label,
  }),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

import {
  buildDynamicFilterSchema,
  buildRecycleColumns,
  buildSortOptions,
} from '../data';

const baseMeta = {
  columns: ['name', 'status'],
  filterable: ['owner_tenant_id', 'is_active', 'name'],
  is_tenant: true,
  label: 'Agents',
  label_field: 'name',
  sortable: ['name'],
  tenant_field: 'owner_tenant_id',
};

describe('shared recycle-bin helpers', () => {
  it('uses backend tenant field names when building fallback filters', () => {
    const tenantFieldSchema = vi.fn(
      (fieldName: string) =>
        ({
          component: 'Select',
          fieldName: `filter[${fieldName}]`,
          label: 'Tenant',
        }) as unknown as VbenFormSchema,
    );

    const schema = buildDynamicFilterSchema(baseMeta, null, {
      includeTenantFilter: true,
      tenantFieldSchema,
    });

    expect(tenantFieldSchema).toHaveBeenCalledWith('owner_tenant_id');
    expect(schema.map((item) => item.fieldName)).toEqual([
      'filter[name][ilike]',
      'filter[is_active]',
      'filter[owner_tenant_id]',
    ]);
  });

  it('filters adapter search schema against backend filterable fields', () => {
    const schema = buildDynamicFilterSchema(
      { ...baseMeta, filterable: ['name'] },
      {
        searchSchema: () =>
          [
            {
              component: 'Input',
              fieldName: 'filter[name][ilike]',
              label: 'Name',
            },
            {
              component: 'Input',
              fieldName: 'filter[provider_name][ilike]',
              label: 'Provider',
            },
          ] as unknown as VbenFormSchema[],
      },
    );

    expect(schema.map((item) => item.fieldName)).toEqual([
      'filter[name][ilike]',
    ]);
  });

  it('adds global recycle-bin columns and default sort options', () => {
    const columns = buildRecycleColumns(baseMeta, null, vi.fn(), {
      includeTenantColumn: true,
    }) ?? [];
    const sortOptions = buildSortOptions(baseMeta, null);

    expect(columns.map((item) => item.field)).toEqual(
      expect.arrayContaining([
        'tenant_name',
        'promoted_to_global_at',
        'deleted_at',
        'operation',
      ]),
    );
    expect(sortOptions[0]).toEqual({
      label: 'common.recycleBin.movedToGlobalAt ↓',
      value: '-promoted_to_global_at',
    });
    expect(sortOptions[1]).toEqual({
      label: 'common.recycleBin.movedToGlobalAt ↑',
      value: 'promoted_to_global_at',
    });
  });

  it('limits fallback filters to high-signal fields', () => {
    const schema = buildDynamicFilterSchema(
      {
        ...baseMeta,
        filterable: [
          'owner_tenant_id',
          'is_active',
          'name',
          'code',
          'status',
          'visibility',
          'created_at',
          'updated_at',
          'description',
        ],
      },
      null,
      {
        includeTenantFilter: true,
        tenantFieldSchema: (fieldName: string) =>
          ({
            component: 'Select',
            fieldName: `filter[${fieldName}]`,
            label: 'Tenant',
          }) as unknown as VbenFormSchema,
      },
    );

    expect(schema.map((item) => item.fieldName)).toEqual([
      'filter[owner_tenant_id]',
      'filter[name][ilike]',
      'filter[code][ilike]',
      'filter[status][ilike]',
      'filter[is_active]',
    ]);
  });
});
