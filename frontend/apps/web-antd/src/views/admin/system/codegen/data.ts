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
      formatter: ({ cellValue }) =>
        cellValue
          ? new Date(cellValue).toLocaleString(undefined, {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
            })
          : '—',
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
          },
          {
            code: 'generate',
            text: $t('admin.system.codegen.actions.generate'),
            icon: 'lucide:wand-2',
          },
          {
            code: 'download',
            text: $t('admin.system.codegen.actions.download'),
            icon: 'lucide:download',
          },
          {
            code: 'duplicate',
            text: $t('admin.system.codegen.actions.duplicate'),
            icon: 'lucide:copy',
          },
          {
            code: 'rollback',
            text: $t('admin.system.codegen.actions.rollback'),
            icon: 'lucide:undo-2',
          },
          {
            code: 'delete',
            text: $t('common.delete'),
            icon: 'lucide:trash-2',
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
    searchInput('filter[name][ilike]', $t('admin.system.codegen.placeholder.searchName')),
    searchInput('filter[resource][ilike]', $t('admin.system.codegen.placeholder.searchResource')),
    select('filter[status][eq]', $t('admin.system.codegen.status'), {
      options: getStatusOptions(),
      placeholder: $t('admin.system.codegen.placeholder.allStatus'),
    }),
  ];
}
