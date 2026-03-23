import type { VbenFormSchema } from '#/adapter/form';
import type {
  OnActionClickFn,
  VxeTableGridOptions,
} from '#/adapter/vxe-table';
import type {
  RecycleBinItem,
  RecycleBinModuleMeta,
} from '#/api/shared/recycle-bin';

import { searchInput, statusSelect } from '#/adapter/form';
import { $t } from '#/locales';

import type {
  RecycleBinColumnPreset,
  RecycleBinModuleAdapter,
  RecycleBinSortOption,
} from './types';

interface BuildFilterOptions {
  includeTenantFilter?: boolean;
  tenantFieldSchema?: ((fieldName: string) => VbenFormSchema) | null;
}

interface BuildColumnOptions {
  includeTenantColumn?: boolean;
}

const COMMON_LABELS: Record<string, () => string> = {
  created_at: () => $t('common.createdAt'),
  deleted_at: () => $t('common.recycleBin.deletedAt'),
  is_active: () => $t('common.status'),
  promoted_to_global_at: () => $t('common.recycleBin.movedToGlobalAt'),
  tenant_name: () => $t('admin.system.recycleBin.tenant'),
};

function extractBackendField(fieldName: string | undefined): null | string {
  if (!fieldName) return null;
  const filterMatch = fieldName.match(/^filter\[([^\]]+)\]/);
  if (filterMatch) return filterMatch[1] ?? null;
  if (fieldName.startsWith('page[')) return null;
  return fieldName;
}

function humanizeField(field: string) {
  return field.replaceAll('_', ' ');
}

function getColumnLabel(
  meta: RecycleBinModuleMeta | null,
  field: string,
): string {
  const label = meta?.column_labels?.[field];
  if (label) return label;
  const common = COMMON_LABELS[field];
  return common ? common() : humanizeField(field);
}

function filterSupportedSchema(
  schema: VbenFormSchema[],
  meta: RecycleBinModuleMeta | null,
): VbenFormSchema[] {
  if (!meta) return schema;
  const supported = new Set(meta.filterable ?? []);
  const seen = new Set<string>();

  return schema.filter((item) => {
    const fieldName = String(item.fieldName ?? '');
    if (!fieldName || seen.has(fieldName)) return false;
    const backendField = extractBackendField(fieldName);
    if (backendField && !supported.has(backendField)) {
      return false;
    }
    seen.add(fieldName);
    return true;
  });
}

function pickFallbackFilterFields(meta: RecycleBinModuleMeta): string[] {
  const tenantField = meta.tenant_field ?? 'tenant_id';
  const preferredOrder = [
    'id',
    meta.label_field,
    'name',
    'code',
    'status',
    'is_active',
    'type',
    'scope',
    'visibility',
    'created_at',
    tenantField,
  ];
  const available = new Set(meta.filterable ?? []);
  const picked: string[] = [];

  for (const field of preferredOrder) {
    if (!field || !available.has(field) || picked.includes(field)) {
      continue;
    }
    picked.push(field);
  }

  if (picked.length === 0) {
    return (meta.filterable ?? []).slice(0, 4);
  }

  return picked.slice(0, 5);
}

export function buildDynamicFilterSchema(
  meta: RecycleBinModuleMeta | null,
  adapter: null | RecycleBinModuleAdapter | undefined,
  options: BuildFilterOptions = {},
): VbenFormSchema[] {
  const businessSchema = adapter?.searchSchema?.();
  if (businessSchema?.length) {
    return filterSupportedSchema(businessSchema, meta);
  }
  if (!meta?.filterable?.length) return [];

  const out: VbenFormSchema[] = [];
  const seen = new Set<string>();
  const tenantField = meta.tenant_field ?? 'tenant_id';
  const fallbackFields = pickFallbackFilterFields(meta);
  if (
    options.includeTenantFilter &&
    options.tenantFieldSchema &&
    meta.filterable.includes(tenantField) &&
    !fallbackFields.includes(tenantField)
  ) {
    if (fallbackFields.length >= 5) {
      fallbackFields.pop();
    }
    fallbackFields.unshift(tenantField);
  }

  for (const field of fallbackFields) {
    if (seen.has(field)) continue;
    seen.add(field);

    if (
      options.includeTenantFilter &&
      options.tenantFieldSchema &&
      field === tenantField
    ) {
      out.push(options.tenantFieldSchema(field));
      continue;
    }

    const label = getColumnLabel(meta, field);
    if (field === 'is_active') {
      out.push(statusSelect({ field: 'is_active', label }));
      continue;
    }

    out.push(searchInput(field, label));
  }
  return out;
}

function resolveColumnSlot(
  field: string,
  preset: RecycleBinColumnPreset,
): string | undefined {
  if (preset.slot) return preset.slot;
  switch (field) {
    case 'billing_cycle': {
      return 'billing_cycle_cell';
    }
    case 'created_at': {
      return 'created_at_cell';
    }
    case 'deleted_at': {
      return 'deleted_at_cell';
    }
    case 'execution_mode': {
      return 'execution_mode_cell';
    }
    case 'expires_at': {
      return 'expires_at_cell';
    }
    case 'is_active': {
      return 'is_active_cell';
    }
    case 'promoted_to_global_at': {
      return 'promoted_to_global_at_cell';
    }
    case 'schedule_display': {
      return 'schedule_cell';
    }
    case 'scope': {
      return 'scope_cell';
    }
    case 'status': {
      return 'status_cell';
    }
    case 'tenant_name': {
      return 'tenant_name_cell';
    }
    case 'tier': {
      return 'tier_cell';
    }
    case 'total_size_bytes': {
      return 'size_cell';
    }
    case 'type': {
      return 'type_cell';
    }
    case 'visibility': {
      return 'visibility_cell';
    }
    default: {
      return undefined;
    }
  }
}

function toVxeColumn(
  preset: RecycleBinColumnPreset,
): NonNullable<VxeTableGridOptions['columns']>[number] {
  const slot = resolveColumnSlot(preset.field, preset);
  return {
    align: preset.align,
    field: preset.field,
    minWidth: preset.minWidth ?? 120,
    showOverflow: 'tooltip',
    slots: slot ? { default: slot } : undefined,
    title: preset.title,
    width: preset.width,
  };
}

export function buildRecycleColumns(
  meta: RecycleBinModuleMeta | null,
  adapter: null | RecycleBinModuleAdapter | undefined,
  onActionClick: OnActionClickFn<RecycleBinItem>,
  options: BuildColumnOptions = {},
): VxeTableGridOptions['columns'] {
  const presets =
    adapter?.columns?.() ??
    (meta?.columns ?? []).map((field) => ({
      field,
      title: getColumnLabel(meta, field),
    }));

  const cols: NonNullable<VxeTableGridOptions['columns']> = presets.map(
    (preset) => toVxeColumn(preset),
  );

  if (options.includeTenantColumn && meta?.is_tenant) {
    cols.push({
      field: 'tenant_name',
      minWidth: 140,
      slots: { default: 'tenant_name_cell' },
      title: $t('admin.system.recycleBin.tenant'),
    });
  }

  cols.push(
    {
      field: 'promoted_to_global_at',
      minWidth: 170,
      slots: { default: 'promoted_to_global_at_cell' },
      title: $t('common.recycleBin.movedToGlobalAt'),
      width: 180,
    },
    {
      field: 'deleted_at',
      minWidth: 170,
      slots: { default: 'deleted_at_cell' },
      title: $t('common.recycleBin.deletedAt'),
      width: 170,
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          nameField: meta?.label_field ?? 'name',
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'restore',
            icon: 'lucide:rotate-ccw',
            text: $t('common.recycleBin.restore'),
          },
          {
            code: 'delete',
            danger: true,
            icon: 'lucide:x',
            text: $t('common.recycleBin.permanentDelete'),
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('common.operation'),
      width: 120,
    },
  );

  return cols;
}

export function buildSortOptions(
  meta: RecycleBinModuleMeta | null,
  adapter: null | RecycleBinModuleAdapter | undefined,
): RecycleBinSortOption[] {
  const adapterOptions = adapter?.sortOptions?.();
  if (adapterOptions?.length) {
    return adapterOptions;
  }

  const orderedFields: string[] = [];
  const seen = new Set<string>();
  for (const field of [
    'promoted_to_global_at',
    'deleted_at',
    ...(meta?.sortable ?? []),
  ]) {
    if (!field || seen.has(field)) continue;
    seen.add(field);
    orderedFields.push(field);
  }

  return orderedFields.flatMap((field) => {
    const label = getColumnLabel(meta, field);
    return [
      { label: `${label} ↓`, value: `-${field}` },
      { label: `${label} ↑`, value: field },
    ];
  });
}
