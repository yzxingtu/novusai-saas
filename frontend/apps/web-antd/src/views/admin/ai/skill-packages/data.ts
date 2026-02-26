/**
 * 技能包管理（平台端） - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';
import { getScopeColor, getScopeOptions, getScopeText } from '#/utils/scope-helpers';

export { getScopeColor, getScopeText };

function getScopeFilterOptions() {
  return getScopeOptions(['admin_only', 'all_tenants', 'admin_and_all', 'admin_and_assigned', 'assigned_tenants']);
}

/** 表格列定义 */
export function useColumns<T = AdminSkillPackageInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('admin.ai.skillPackage.name'),
      minWidth: 200,
      slots: { default: 'name_cell' },
    },
    {
      field: 'scope',
      title: $t('admin.ai.skillPackage.scope'),
      width: 100,
      align: 'center',
      slots: { default: 'scope_cell' },
    },
    {
      field: 'bind_mode',
      title: $t('common.bindMode.label'),
      width: 100,
      align: 'center',
      slots: { default: 'bind_mode_cell' },
    },
    {
      field: 'skill_count',
      title: $t('admin.ai.skillPackage.skillCount'),
      width: 100,
      align: 'center',
      slots: { default: 'skill_count_cell' },
    },
    {
      field: 'is_active',
      title: $t('admin.ai.skillPackage.isActive'),
      width: 100,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'created_at',
      title: $t('admin.common.createdAt'),
      width: 130,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_skill_package',
          nameField: 'name',
          nameTitle: $t('admin.ai.skillPackage.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: ['edit', { code: 'delete', show: (row: AdminSkillPackageInfo) => !row.is_system }],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 160,
    },
  ];
}

/** 搜索表单 Schema */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('filter[name][ilike]', $t('admin.ai.skillPackage.name'), {
      placeholder: $t('admin.ai.skillPackage.placeholder.searchName'),
    }),
    select('filter[scope][eq]', $t('admin.ai.skillPackage.scope'), {
      options: getScopeFilterOptions(),
      placeholder: $t('admin.ai.skillPackage.placeholder.allScopes'),
    }),
  ];
}
