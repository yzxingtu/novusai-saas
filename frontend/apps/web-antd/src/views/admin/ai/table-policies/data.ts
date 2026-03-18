/**
 * AI 表策略管理 - 表格列、搜索和表单配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AITablePolicyInfo } from '#/api/admin/ai';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { getAITablePolicyColumnsApi } from '#/api/admin/ai';
import { $t } from '#/locales';

/**
 * 表格列定义
 */
export function useColumns<T = AITablePolicyInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      type: 'expand',
      width: 40,
      slots: { content: 'expand_content' },
    },
    {
      field: 'table_name',
      title: $t('admin.ai.tablePolicy.tableName'),
      minWidth: 260,
      slots: { default: 'tableName_cell' },
    },
    {
      field: 'allow_read',
      title: $t('admin.ai.tablePolicy.crud'),
      width: 260,
      align: 'center',
      slots: { default: 'crud_cell' },
    },
    {
      field: 'max_rows',
      title: $t('admin.ai.tablePolicy.maxRows'),
      width: 90,
      align: 'center',
    },
    {
      field: 'is_active',
      title: $t('admin.ai.tablePolicy.isActive'),
      width: 90,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_table_policy',
          nameField: 'table_name',
          nameTitle: $t('admin.ai.tablePolicy.tableName'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: ['edit'],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 100,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('table_name', $t('admin.ai.tablePolicy.tableName'), {
      placeholder: $t('admin.ai.tablePolicy.placeholder.searchTableName'),
    }),
    searchInput('label', $t('admin.ai.tablePolicy.label'), {
      placeholder: $t('admin.ai.tablePolicy.placeholder.searchLabel'),
    }),
  ];
}

/**
 * 编辑表单 Schema
 */
export function useFormSchema(_policyId?: number): VbenFormSchema[] {
  return [
    {
      ...inputField('table_name', $t('admin.ai.tablePolicy.tableName')),
      componentProps: { disabled: true },
    },
    inputField('label', $t('admin.ai.tablePolicy.label'), {
      required: true,
      placeholder: $t('admin.ai.tablePolicy.placeholder.inputLabel'),
    }),
    textareaField('description', $t('admin.ai.tablePolicy.description'), {
      placeholder: $t('admin.ai.tablePolicy.placeholder.inputDescription'),
    }),
    {
      component: 'Select',
      componentProps: {
        mode: 'tags',
        tokenSeparators: [',', ' '],
        placeholder: $t('admin.ai.tablePolicy.placeholder.inputKeywords'),
      },
      fieldName: 'keywords',
      label: $t('admin.ai.tablePolicy.keywords'),
      help: $t('admin.ai.tablePolicy.keywordsHelp'),
    },
    {
      component: 'Divider',
      fieldName: 'column_desc_divider',
      label: '',
      componentProps: {
        orientation: 'left',
        plain: true,
      },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.tablePolicy.columnDescriptions'),
      }),
    },
    inputField('permission_code', $t('admin.ai.tablePolicy.permissionCode'), {
      placeholder: $t('admin.ai.tablePolicy.placeholder.inputPermissionCode'),
    }),
    numberField('max_rows', $t('admin.ai.tablePolicy.maxRows'), {
      min: 1,
      max: 10_000,
      placeholder: $t('admin.ai.tablePolicy.placeholder.inputMaxRows'),
    }),
    switchField('allow_read', $t('admin.ai.tablePolicy.allowRead'), {
      defaultValue: true,
    }),
    switchField('allow_create', $t('admin.ai.tablePolicy.allowCreate'), {
      defaultValue: false,
    }),
    switchField('allow_update', $t('admin.ai.tablePolicy.allowUpdate'), {
      defaultValue: false,
    }),
    switchField('allow_delete', $t('admin.ai.tablePolicy.allowDelete'), {
      defaultValue: false,
    }),
    {
      ...select('blocked_columns', $t('admin.ai.tablePolicy.blockedColumns'), {
        placeholder: $t(
          'admin.ai.tablePolicy.placeholder.selectBlockedColumns',
        ),
      }),
      componentProps: {
        class: 'w-full',
        mode: 'multiple',
        options: [],
        placeholder: $t(
          'admin.ai.tablePolicy.placeholder.selectBlockedColumns',
        ),
      },
    },
    {
      ...select(
        'readonly_columns',
        $t('admin.ai.tablePolicy.readonlyColumns'),
        {
          placeholder: $t(
            'admin.ai.tablePolicy.placeholder.selectReadonlyColumns',
          ),
        },
      ),
      componentProps: {
        class: 'w-full',
        mode: 'multiple',
        options: [],
        placeholder: $t(
          'admin.ai.tablePolicy.placeholder.selectReadonlyColumns',
        ),
      },
    },
    numberField('sort_order', $t('admin.ai.tablePolicy.sortOrder'), {
      min: 0,
    }),
    switchField('is_active', $t('admin.ai.tablePolicy.isActive'), {
      defaultValue: true,
    }),
  ];
}

/**
 * 加载表列选项（用于 blocked_columns / readonly_columns 选择器）
 */
export async function loadColumnOptions(policyId: number) {
  const columns = await getAITablePolicyColumnsApi(policyId);
  return columns.map((col) => ({
    label: col.comment ? `${col.name} (${col.comment})` : col.name,
    value: col.name,
  }));
}
