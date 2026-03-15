/**
 * 技能包管理（平台端） - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { $t } from '#/locales';

export function getAudienceColor(audience: string | undefined): string {
  switch (audience) {
    case 'admin_only': return 'error';
    case 'admin_tenant': return 'processing';
    case 'all': return 'success';
    default: return 'default';
  }
}

export function getAudienceOptions() {
  return [
    { label: $t('admin.ai.agent.audience_options.all'), value: 'all' },
    { label: $t('admin.ai.agent.audience_options.admin_only'), value: 'admin_only' },
    { label: $t('admin.ai.agent.audience_options.admin_tenant'), value: 'admin_tenant' },
  ];
}

/** 表格列定义 / Table column definitions */
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
      field: 'target_audience',
      title: $t('admin.ai.skillPackage.targetAudience'),
      width: 120,
      align: 'center',
      slots: { default: 'targetAudience_cell' },
    },
    {
      field: 'is_recommended',
      title: $t('admin.ai.skillPackage.isRecommended'),
      width: 100,
      align: 'center',
      slots: { default: 'isRecommended_cell' },
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

/**
 * Package form schema (for AI field extraction)
 * 技能包表单 Schema（供 AI 字段提取使用）
 */
export function usePackageFormSchema(): VbenFormSchema[] {
  return [
    inputField('name', $t('admin.ai.skillPackage.name'), {
      required: true,
      placeholder: $t('admin.ai.skillPackage.placeholder.inputName'),
    }),
    textareaField('description', $t('admin.ai.skillPackage.description'), {
      placeholder: $t('admin.ai.skillPackage.placeholder.inputDescription'),
    }),
    select('target_audience', $t('admin.ai.skillPackage.targetAudience'), {
      options: getAudienceOptions(),
      required: true,
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

/** 搜索表单 Schema / Search form schema */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('filter[name][ilike]', $t('admin.ai.skillPackage.name'), {
      placeholder: $t('admin.ai.skillPackage.placeholder.searchName'),
    }),
    select('filter[target_audience][eq]', $t('admin.ai.skillPackage.targetAudience'), {
      options: getAudienceOptions(),
      placeholder: $t('admin.ai.skillPackage.placeholder.allScopes'),
    }),
  ];
}
