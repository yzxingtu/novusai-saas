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

export function getStatusText(status: string): string {
  const map: Record<string, string> = {
    draft: $t('admin.system.codegen.status_options.draft'),
    generated: $t('admin.system.codegen.status_options.generated'),
    applied: $t('admin.system.codegen.status_options.applied'),
    rolled_back: $t('admin.system.codegen.status_options.rolled_back'),
  };
  return map[status] || status || '-';
}

export function getManifestStatusColor(present: boolean): string {
  return present ? 'success' : 'default';
}

export function getManifestStatusText(present: boolean): string {
  return present
    ? $t('admin.system.codegen.manifest.present')
    : $t('admin.system.codegen.manifest.absent');
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

function canDownloadGenerated(row: Record<string, unknown>): boolean {
  return row.manifest_present === true;
}

function canDeleteCodegenConfig(row: Record<string, unknown>): boolean {
  return row.delete_allowed !== false;
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
      minWidth: 240,
      slots: { default: 'name_cell' },
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
      width: 136,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'manifest_present',
      title: $t('admin.system.codegen.manifestStatus'),
      width: 118,
      align: 'center',
      slots: { default: 'manifest_present_cell' },
    },
    {
      field: 'generation_count',
      title: $t('admin.system.codegen.generationCount'),
      width: 92,
      align: 'center',
      slots: { default: 'generation_count_cell' },
    },
    {
      field: 'last_generated_at',
      title: $t('admin.system.codegen.lastGeneratedAt'),
      width: 152,
      slots: { default: 'last_generated_at_cell' },
    },
    {
      field: 'last_error',
      title: $t('admin.system.codegen.lastError'),
      minWidth: 220,
      slots: { default: 'last_error_cell' },
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
            text: (row: Record<string, unknown>) =>
              canDownloadGenerated(row)
                ? $t('admin.system.codegen.actions.download')
                : $t('admin.system.codegen.actions.downloadDisabledHint'),
            icon: 'lucide:download',
            accessCodes: ['action.codegen.download'],
            disabled: (row: Record<string, unknown>) =>
              !canDownloadGenerated(row),
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
            disabled: (row: Record<string, unknown>) =>
              !canCodegenRollback(row),
          },
          {
            code: 'delete',
            text: (row: Record<string, unknown>) =>
              canDeleteCodegenConfig(row)
                ? $t('common.delete')
                : (row.delete_reason_message as string | undefined) ||
                  $t('admin.system.codegen.actions.deleteDisabledHint'),
            icon: 'lucide:trash-2',
            accessCodes: ['action.codegen.delete'],
            disabled: (row: Record<string, unknown>) =>
              !canDeleteCodegenConfig(row),
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 208,
    },
  ];
}

/** 搜索 Schema / Search schema */
export function useGridFormSchema() {
  return [
    searchInput('name', $t('admin.system.codegen.placeholder.searchName')),
    searchInput(
      'resource',
      $t('admin.system.codegen.placeholder.searchResource'),
    ),
    select('filter[status][eq]', $t('admin.system.codegen.status'), {
      options: getStatusOptions(),
      placeholder: $t('admin.system.codegen.placeholder.allStatus'),
    }),
  ];
}
