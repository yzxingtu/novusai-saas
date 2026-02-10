/**
 * 租户端工具管理 - 表格列、搜索配置、表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { ToolDefinitionInfo } from '#/api/tenant/tools';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { $t } from '#/locales';

/**
 * 获取工具类型下拉选项
 */
export function getToolTypeOptions() {
  return [
    { label: $t('tenant.ai.tool.type_options.http'), value: 'http' },
    { label: $t('tenant.ai.tool.type_options.database'), value: 'database' },
    { label: $t('tenant.ai.tool.type_options.email'), value: 'email' },
    { label: $t('tenant.ai.tool.type_options.builtin'), value: 'builtin' },
  ];
}

/**
 * 获取工具类型文本
 */
export function getToolTypeText(type: string | undefined): string {
  if (!type) return '-';
  switch (type) {
    case 'http': return $t('tenant.ai.tool.type_options.http');
    case 'database': return $t('tenant.ai.tool.type_options.database');
    case 'email': return $t('tenant.ai.tool.type_options.email');
    case 'code': return $t('tenant.ai.tool.type_options.code');
    case 'builtin': return $t('tenant.ai.tool.type_options.builtin');
    default: return type;
  }
}

/**
 * 获取工具类型颜色
 */
export function getToolTypeColor(type: string | undefined): string {
  switch (type) {
    case 'http': return 'blue';
    case 'database': return 'green';
    case 'email': return 'orange';
    case 'code': return 'purple';
    case 'builtin': return 'cyan';
    default: return 'default';
  }
}

/**
 * 表格列定义
 */
export function useColumns<T = ToolDefinitionInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('tenant.ai.tool.name'),
      minWidth: 180,
      slots: { default: 'name_cell' },
    },
    {
      field: 'type',
      title: $t('tenant.ai.tool.type'),
      width: 120,
      align: 'center',
      slots: { default: 'type_cell' },
    },
    {
      field: 'description',
      title: $t('tenant.ai.tool.description'),
      minWidth: 200,
      slots: { default: 'description_cell' },
    },
    {
      field: 'is_system',
      title: $t('tenant.ai.tool.isSystem'),
      width: 100,
      align: 'center',
      slots: { default: 'isSystem_cell' },
    },
    {
      field: 'is_active',
      title: $t('tenant.ai.tool.isActive'),
      width: 100,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'timeout',
      title: $t('tenant.ai.tool.timeout'),
      width: 100,
      align: 'right',
      slots: { default: 'timeout_cell' },
    },
    {
      field: 'created_at',
      title: $t('tenant.ai.tool.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'agent_tool',
          nameField: 'name',
          nameTitle: $t('tenant.ai.tool.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'test',
            text: $t('tenant.ai.tool.testExecute'),
            icon: 'lucide:play',
            accessCodes: ['agent_tool:update'],
          },
          'edit',
          'delete',
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('tenant.common.operation'),
      width: 200,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('tenant.ai.tool.name'), {
      placeholder: $t('tenant.ai.tool.placeholder.searchName'),
    }),
    select('filter[type][eq]', $t('tenant.ai.tool.type'), {
      options: getToolTypeOptions(),
      placeholder: $t('tenant.ai.tool.placeholder.allTypes'),
    }),
  ];
}

/**
 * 工具表单 Schema
 */
export function useFormSchema(): VbenFormSchema[] {
  return [
    inputField('name', $t('tenant.ai.tool.name'), {
      required: true,
      placeholder: $t('tenant.ai.tool.placeholder.inputName'),
    }),
    select('type', $t('tenant.ai.tool.type'), {
      options: getToolTypeOptions(),
      required: true,
      placeholder: $t('tenant.ai.tool.placeholder.selectType'),
    }),
    textareaField('description', $t('tenant.ai.tool.description'), {
      placeholder: $t('tenant.ai.tool.placeholder.inputDescription'),
    }),
    numberField('timeout', $t('tenant.ai.tool.timeout'), {
      min: 1,
      max: 300,
      placeholder: $t('tenant.ai.tool.placeholder.inputTimeout'),
    }),
    textareaField('input_schema_str', $t('tenant.ai.tool.inputSchema'), {
      placeholder: $t('tenant.ai.tool.placeholder.inputSchema'),
      rows: 6,
    }),
    textareaField('config_str', $t('tenant.ai.tool.config'), {
      placeholder: $t('tenant.ai.tool.placeholder.inputConfig'),
      rows: 6,
    }),
    switchField('is_active', $t('tenant.ai.tool.isActive'), {
      defaultValue: true,
    }),
  ];
}

/**
 * 工具表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    type: 'http',
    timeout: 30,
    is_active: true,
    input_schema_str: '{}',
    config_str: '{}',
  };
}
