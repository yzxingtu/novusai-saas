/**
 * 租户端技能包管理 - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { TenantSkillPackageInfo } from '#/api/tenant/skill-packages';

import { searchInput } from '#/adapter/form';
import { $t } from '#/locales';

/** 作用域颜色映射 */
export function getScopeColor(scope: string): string {
  const map: Record<string, string> = {
    tenant: 'green',
    global: 'purple',
  };
  return map[scope] || 'default';
}

/** 作用域文本映射 */
export function getScopeText(scope: string): string {
  const map: Record<string, string> = {
    tenant: $t('tenant.ai.skillPackage.scope_options.tenant'),
    global: $t('tenant.ai.skillPackage.scope_options.global'),
  };
  return map[scope] || scope;
}

/** 表格列定义 */
export function useColumns<T = TenantSkillPackageInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('tenant.ai.skillPackage.name'),
      minWidth: 200,
      slots: { default: 'name_cell' },
    },
    {
      field: 'scope',
      title: $t('tenant.ai.skillPackage.scope'),
      width: 100,
      align: 'center',
      slots: { default: 'scope_cell' },
    },
    {
      field: 'skill_count',
      title: $t('tenant.ai.skillPackage.skillCount'),
      width: 100,
      align: 'center',
      slots: { default: 'skill_count_cell' },
    },
    {
      field: 'is_active',
      title: $t('tenant.ai.skillPackage.isActive'),
      width: 100,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'created_at',
      title: $t('tenant.common.createdAt'),
      width: 130,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'skill_package',
          nameField: 'name',
          nameTitle: $t('tenant.ai.skillPackage.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          { code: 'edit', show: (row: TenantSkillPackageInfo) => row.scope !== 'global' },
          { code: 'delete', show: (row: TenantSkillPackageInfo) => !row.is_system && row.scope !== 'global' },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('tenant.common.operation'),
      width: 160,
    },
  ];
}

/** 搜索表单 Schema */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('filter[name][ilike]', $t('tenant.ai.skillPackage.name'), {
      placeholder: $t('tenant.ai.skillPackage.placeholder.searchName'),
    }),
  ];
}
