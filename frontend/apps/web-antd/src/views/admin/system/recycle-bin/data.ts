/**
 * Admin recycle bin — dynamic search form & column labels
 * 管理端总回收站 — 动态搜索表单 & 列标签
 *
 * 固定筛选项仅「数据模块」「删除来源」，其余由后端 meta.filterable + column_labels 驱动。
 * Fixed filters: module + delete source; remaining filters follow backend meta.filterable + column_labels.
 */
import type { VbenFormSchema } from '#/adapter/form';
import type {
  OnActionClickFn,
  VxeTableGridOptions,
} from '#/adapter/vxe-table';
import type {
  RecycleBinItem,
  RecycleBinModuleMeta,
} from '#/api/admin/recycle-bin';

import { searchInput, select, statusSelect } from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

function tenantSelect(): VbenFormSchema {
  return select('filter[tenant_id]', $t('admin.system.recycleBin.tenant'), {
    api: getTenantSelectApi,
    placeholder: $t('admin.system.recycleBin.allTenants'),
  });
}

/**
 * 按模块元数据构建动态筛选 Schema（不含模块、删除来源）
 * Build dynamic filter schemas from module metadata (excludes module & delete_level).
 */
export function buildDynamicFilterSchema(
  meta: RecycleBinModuleMeta | null,
  moduleCode: string,
): VbenFormSchema[] {
  if (!meta?.filterable?.length) return [];
  const seen = new Set<string>();
  const out: VbenFormSchema[] = [];
  for (const field of meta.filterable) {
    if (seen.has(field)) continue;
    seen.add(field);
    if (field === 'tenant_id') {
      if (!meta.is_tenant) continue;
      out.push(tenantSelect());
      continue;
    }
    const label =
      (meta.column_labels && meta.column_labels[field]) ||
      getColumnLabel(field, moduleCode);
    if (field === 'is_active') {
      out.push(statusSelect({ field: 'is_active', label }));
      continue;
    }
    out.push(searchInput(field, label));
  }
  return out;
}

// ── Module × field → translated label / 各模块字段翻译标签（后端无 column_labels 时回退）
const COLUMN_LABELS: Record<string, () => string> = {
  status: () => $t('shared.common.status'),
  'ai_providers:name': () => $t('admin.ai.provider.name'),
  'ai_providers:code': () => $t('admin.ai.provider.code'),
  'ai_models:name': () => $t('admin.ai.model.name'),
  'ai_models:model_id': () => $t('admin.ai.model.code'),
  'ai_models:provider_id': () => $t('admin.ai.model.providerId'),
  'ai_api_keys:name': () => $t('admin.ai.apiKey.name'),
  'ai_api_keys:provider_id': () => $t('admin.ai.model.providerId'),
  'agents:name': () => $t('admin.ai.agent.name'),
  'skill_packages:name': () => $t('admin.ai.skillPackage.name'),
  'skill_packages:scope': () => $t('admin.ai.skillPackage.scope'),
  'knowledge_bases:name': () => $t('admin.knowledgeBase.field.name'),
  'admin_roles:name': () => $t('admin.system.organization.node.name'),
  'admin_roles:code': () => $t('admin.system.organization.node.code'),
  'tenant_plans:name': () => $t('admin.tenant.plan.name'),
  'tenant_plans:code': () => $t('admin.tenant.plan.code'),
  'tenants:name': () => $t('admin.tenant.name'),
  'tenants:code': () => $t('admin.tenant.code'),
  'tenant_domains:domain': () => $t('admin.tenant.domain.domain'),
  'table_policies:table_name': () => $t('admin.ai.tablePolicy.tableName'),
  'table_policies:label': () => $t('admin.ai.tablePolicy.label'),
  'periodic_tasks:name': () => $t('admin.system.periodicTask.name'),
  'periodic_tasks:is_active': () => $t('shared.common.status'),
  'tenant_admin_roles:name': () => $t('admin.system.organization.node.name'),
  'tenant_admin_roles:code': () => $t('admin.system.organization.node.code'),
};

export function getColumnLabel(field: string, moduleCode?: string): string {
  if (moduleCode) {
    const specific = COLUMN_LABELS[`${moduleCode}:${field}`];
    if (specific) return specific();
  }
  const generic = COLUMN_LABELS[field];
  return generic ? generic() : field;
}

export function buildRecycleColumns(
  meta: RecycleBinModuleMeta | null,
  moduleCode: string,
  onActionClick: OnActionClickFn<RecycleBinItem>,
): VxeTableGridOptions['columns'] {
  const nameField = meta?.label_field ?? 'name';
  const cols: NonNullable<VxeTableGridOptions['columns']> = [];

  if (meta) {
    for (const field of meta.columns) {
      const title =
        (meta.column_labels && meta.column_labels[field]) ||
        getColumnLabel(field, moduleCode);
      cols.push({
        field,
        minWidth: 120,
        showOverflow: 'tooltip',
        title,
      });
    }
    if (meta.is_tenant) {
      cols.push({
        field: 'tenant_name',
        slots: { default: 'tenant_name_cell' },
        title: $t('admin.system.recycleBin.tenant'),
        width: 150,
      });
    }
  } else {
    cols.push({
      field: 'name',
      minWidth: 140,
      showOverflow: 'tooltip',
      title: $t('common.basicInfo'),
    });
  }

  cols.push(
    {
      align: 'center',
      field: 'delete_level',
      slots: { default: 'delete_level_cell' },
      title: $t('admin.system.recycleBin.deleteLevel'),
      width: 110,
    },
    {
      field: 'deleted_at',
      slots: { default: 'deleted_at_cell' },
      title: $t('common.recycleBin.deletedAt'),
      width: 170,
    },
    {
      align: 'center',
      cellRender: {
        attrs: { nameField, onClick: onActionClick },
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
      title: $t('admin.common.operation'),
      width: 110,
    },
  );

  return cols;
}
