/**
 * Skill package view helpers (admin)
 * 技能包页面辅助函数（管理端）
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';

import {
  inputField,
  numberField,
  searchInput,
  switchField,
  textareaField,
} from '#/adapter/form';
import { $t } from '#/locales';

function getFallbackTextKey(): string {
  return 'admin.ai.skillPackage.roleOptions.platform_catalog';
}

export function getPackageRoleColor(roleKey: null | string | undefined): string {
  switch (roleKey) {
    case 'platform_system': {
      return 'gold';
    }
    case 'plugin_managed': {
      return 'geekblue';
    }
    case 'tenant_owned': {
      return 'green';
    }
    case 'platform_catalog': {
      return 'purple';
    }
    default: {
      return 'default';
    }
  }
}

export function getPackageRoleText(roleKey: null | string | undefined): string {
  if (!roleKey) {
    return $t(getFallbackTextKey());
  }
  return $t(`admin.ai.skillPackage.roleOptions.${roleKey}`);
}

export function getRuntimeBindingModeColor(
  mode: null | string | undefined,
): string {
  switch (mode) {
    case 'direct_agent_skill_grant': {
      return 'cyan';
    }
    default: {
      return 'default';
    }
  }
}

export function getRuntimeBindingModeText(
  mode: null | string | undefined,
): string {
  if (!mode) {
    return $t('admin.ai.skillPackage.runtimeBindingOptions.direct_agent_skill_grant');
  }
  return $t(`admin.ai.skillPackage.runtimeBindingOptions.${mode}`);
}

export function getSourceSummaryText(
  summary: null | string | undefined,
  sourcePlugin?: null | string,
): string {
  if (!summary) {
    return $t('admin.ai.skillPackage.sourceSummaryOptions.platform_catalog');
  }

  if (summary.startsWith('plugin:')) {
    return $t('admin.ai.skillPackage.sourceSummaryValue.plugin', {
      plugin: sourcePlugin || summary.replace(/^plugin:/, ''),
    });
  }

  if (summary.startsWith('tenant:')) {
    return $t('admin.ai.skillPackage.sourceSummaryValue.tenant', {
      tenantId: summary.replace(/^tenant:/, ''),
    });
  }

  return $t(`admin.ai.skillPackage.sourceSummaryOptions.${summary.replace(':', '_')}`);
}

/** Table column definitions / 表格列定义 */
export function useColumns<T = AdminSkillPackageInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('admin.ai.skillPackage.name'),
      minWidth: 220,
      slots: { default: 'name_cell' },
    },
    {
      field: 'package_role_key',
      title: $t('admin.ai.skillPackage.packageRole'),
      width: 140,
      align: 'center',
      slots: { default: 'package_role_cell' },
    },
    {
      field: 'source_summary',
      title: $t('admin.ai.skillPackage.sourceSummary'),
      minWidth: 200,
      slots: { default: 'source_summary_cell' },
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
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_skill_package',
          nameField: 'name',
          nameTitle: $t('admin.ai.skillPackage.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          'edit',
          {
            code: 'delete',
            show: (row: AdminSkillPackageInfo) => !row.is_system,
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 160,
    },
  ];
}

/** Package form schema / 技能包表单 Schema */
export function usePackageFormSchema(): VbenFormSchema[] {
  return [
    inputField('name', $t('admin.ai.skillPackage.name'), {
      required: true,
      placeholder: $t('admin.ai.skillPackage.placeholder.inputName'),
    }),
    textareaField('description', $t('admin.ai.skillPackage.description'), {
      placeholder: $t('admin.ai.skillPackage.placeholder.inputDescription'),
    }),
    switchField('is_recommended', $t('admin.ai.skillPackage.isRecommended'), {
      defaultValue: false,
    }),
    switchField('is_active', $t('admin.ai.skillPackage.isActive'), {
      defaultValue: true,
    }),
    numberField('sort_order', $t('admin.ai.skillPackage.sortOrder'), {
      min: 0,
      defaultValue: 0,
    }),
  ];
}

/** Search form schema / 搜索表单 Schema */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('filter[name][ilike]', $t('admin.ai.skillPackage.name'), {
      placeholder: $t('admin.ai.skillPackage.placeholder.searchName'),
    }),
  ];
}
