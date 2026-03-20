/**
 * 代码生成器配置列表 — 列定义、搜索 Schema
 * Codegen config list — column defs, search schema
 */
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';

/** 状态颜色映射 / Status color mapping */
export function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    draft: 'default',
    generated: 'processing',
    applied: 'success',
    rolled_back: 'warning',
  };
  return map[status] || 'default';
}

/**
 * 回滚以 codegen_manifest.json 为准；新 API 返回 manifest_present。
 * Rollback requires manifest; prefer manifest_present from API.
 */
function canCodegenRollback(row: Record<string, unknown>): boolean {
  if (typeof row.manifest_present === 'boolean') {
    return row.manifest_present;
  }
  const s = row.status as string | undefined;
  return s === 'generated' || s === 'applied';
}

/** 状态选项（搜索用） / Status options (for search) */
function getStatusOptions() {
  return [
    { label: $t('admin.system.codegen.status_options.draft'), value: 'draft' },
    {
      label: $t('admin.system.codegen.status_options.generated'),
      value: 'generated',
    },
    {
      label: $t('admin.system.codegen.status_options.applied'),
      value: 'applied',
    },
    {
      label: $t('admin.system.codegen.status_options.rolled_back'),
      value: 'rolled_back',
    },
  ];
}

/** 列定义 / Column definitions */
export function useColumns<T = Record<string, unknown>>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('admin.system.codegen.name'),
      minWidth: 160,
    },
    {
      field: 'resource',
      title: $t('admin.system.codegen.resource'),
      width: 120,
    },
    {
      field: 'module',
      title: $t('admin.system.codegen.module'),
      width: 100,
    },
    {
      field: 'display_name',
      title: $t('admin.system.codegen.displayName'),
      minWidth: 120,
    },
    {
      field: 'status',
      title: $t('admin.system.codegen.status'),
      width: 110,
      align: 'center',
      cellRender: {
        name: 'CellTag',
        options: [
          {
            color: 'default',
            label: $t('admin.system.codegen.status_options.draft'),
            value: 'draft',
          },
          {
            color: 'processing',
            label: $t('admin.system.codegen.status_options.generated'),
            value: 'generated',
          },
          {
            color: 'success',
            label: $t('admin.system.codegen.status_options.applied'),
            value: 'applied',
          },
          {
            color: 'warning',
            label: $t('admin.system.codegen.status_options.rolled_back'),
            value: 'rolled_back',
          },
        ],
      },
    },
    {
      field: 'generation_count',
      title: $t('admin.system.codegen.generationCount'),
      width: 100,
      align: 'center',
    },
    {
      field: 'last_generated_at',
      title: $t('admin.system.codegen.lastGeneratedAt'),
      width: 170,
      slots: { default: 'last_generated_at_cell' },
    },
    {
      field: 'last_error',
      title: $t('admin.system.codegen.lastError'),
      minWidth: 140,
      showOverflow: 'tooltip',
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          nameField: 'name',
          nameTitle: $t('admin.system.codegen.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'edit',
            text: $t('common.edit'),
            icon: 'lucide:pencil',
            accessCodes: ['action.codegen.update'],
          },
          {
            code: 'generate',
            text: $t('admin.system.codegen.actions.generate'),
            icon: 'lucide:wand-2',
            accessCodes: ['action.codegen.generate'],
          },
          {
            code: 'download',
            text: $t('admin.system.codegen.actions.download'),
            icon: 'lucide:download',
            accessCodes: ['action.codegen.download'],
          },
          {
            code: 'duplicate',
            text: $t('admin.system.codegen.actions.duplicate'),
            icon: 'lucide:copy',
            accessCodes: ['action.codegen.duplicate'],
          },
          {
            code: 'rollback',
            text: (row: Record<string, unknown>) =>
              canCodegenRollback(row)
                ? $t('admin.system.codegen.actions.rollback')
                : $t('admin.system.codegen.actions.rollbackDisabledHint'),
            icon: 'lucide:undo-2',
            accessCodes: ['action.codegen.rollback'],
            disabled: (row: Record<string, unknown>) => !canCodegenRollback(row),
          },
          {
            code: 'delete',
            text: $t('common.delete'),
            icon: 'lucide:trash-2',
            accessCodes: ['action.codegen.delete'],
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 220,
    },
  ];
}

/** 搜索 Schema / Search schema */
export function useGridFormSchema() {
  return [
    searchInput('name', $t('admin.system.codegen.placeholder.searchName')),
    searchInput('resource', $t('admin.system.codegen.placeholder.searchResource')),
    select('filter[status][eq]', $t('admin.system.codegen.status'), {
      options: getStatusOptions(),
      placeholder: $t('admin.system.codegen.placeholder.allStatus'),
    }),
  ];
}
