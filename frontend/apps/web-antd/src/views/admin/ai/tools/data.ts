/**
 * 工具定义管理（平台端） - 表格列、搜索和表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AIToolInfo } from '#/api/admin/ai';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

function getToolTypeOptions() {
  return [
    { label: $t('admin.ai.tool.type_options.http'), value: 'http' },
    { label: $t('admin.ai.tool.type_options.database'), value: 'database' },
    { label: $t('admin.ai.tool.type_options.email'), value: 'email' },
    { label: $t('admin.ai.tool.type_options.code'), value: 'code' },
    { label: $t('admin.ai.tool.type_options.builtin'), value: 'builtin' },
  ];
}

function getSystemFilterOptions() {
  return [
    { label: $t('admin.ai.tool.filter.systemOnly'), value: 'true' },
    { label: $t('admin.ai.tool.filter.tenantOnly'), value: 'false' },
  ];
}

/**
 * 表格列定义
 */
export function useColumns<T = AIToolInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('admin.ai.tool.name'),
      minWidth: 160,
      slots: { default: 'name_cell' },
    },
    {
      field: 'type',
      title: $t('admin.ai.tool.type'),
      width: 100,
      align: 'center',
      slots: { default: 'type_cell' },
    },
    {
      field: 'is_system',
      title: $t('admin.ai.tool.isSystem'),
      width: 100,
      align: 'center',
      slots: { default: 'isSystem_cell' },
    },
    {
      field: 'is_active',
      title: $t('admin.ai.tool.isActive'),
      width: 100,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'tenant_id',
      title: $t('admin.ai.tool.tenantId'),
      width: 100,
      align: 'center',
      slots: { default: 'tenantId_cell' },
    },
    {
      field: 'timeout',
      title: $t('admin.ai.tool.timeout'),
      width: 100,
      align: 'center',
      slots: { default: 'timeout_cell' },
    },
    {
      field: 'created_at',
      title: $t('admin.common.createdAt'),
      width: 170,
      sortable: true,
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_tool',
          nameField: 'name',
          nameTitle: $t('admin.ai.tool.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: ['edit', 'delete'],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 160,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('filter[name][ilike]', $t('admin.ai.tool.name'), {
      placeholder: $t('admin.ai.tool.placeholder.searchName'),
    }),
    select('filter[type][eq]', $t('admin.ai.tool.type'), {
      options: getToolTypeOptions(),
      placeholder: $t('admin.ai.tool.placeholder.allTypes'),
    }),
    select('filter[is_system][eq]', $t('admin.ai.tool.isSystem'), {
      options: getSystemFilterOptions(),
      placeholder: $t('admin.ai.tool.placeholder.allScopes'),
    }),
    select('filter[tenant_id]', $t('admin.ai.tool.tenantId'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.ai.tool.placeholder.allTenants'),
    }),
  ];
}

/**
 * 表单 Schema（系统工具 CRUD）
 */
export function useFormSchema(): VbenFormSchema[] {
  return [
    inputField('name', $t('admin.ai.tool.name'), {
      required: true,
      placeholder: $t('admin.ai.tool.placeholder.inputName'),
    }),
    textareaField('description', $t('admin.ai.tool.description'), {
      placeholder: $t('admin.ai.tool.placeholder.inputDescription'),
    }),
    select('type', $t('admin.ai.tool.type'), {
      options: getToolTypeOptions(),
      required: true,
      placeholder: $t('admin.ai.tool.placeholder.selectType'),
    }),
    numberField('timeout', $t('admin.ai.tool.timeout'), {
      min: 1,
      max: 300,
      placeholder: $t('admin.ai.tool.placeholder.inputTimeout'),
    }),
    switchField('is_active', $t('admin.ai.tool.isActive'), {
      defaultValue: true,
    }),
    textareaField('input_schema_json', $t('admin.ai.tool.inputSchema'), {
      placeholder: $t('admin.ai.tool.placeholder.inputSchema'),
      rows: 6,
      rules: [
        {
          validator: (_rule: unknown, value: string) => {
            if (!value) return Promise.resolve();
            try {
              JSON.parse(value);
              return Promise.resolve();
            } catch {
              return Promise.reject(new Error('Invalid JSON'));
            }
          },
          trigger: 'blur',
        },
      ],
    }),
    textareaField('config_json', $t('admin.ai.tool.config'), {
      placeholder: $t('admin.ai.tool.placeholder.config'),
      rows: 6,
      rules: [
        {
          validator: (_rule: unknown, value: string) => {
            if (!value) return Promise.resolve();
            try {
              JSON.parse(value);
              return Promise.resolve();
            } catch {
              return Promise.reject(new Error('Invalid JSON'));
            }
          },
          trigger: 'blur',
        },
      ],
    }),
  ];
}

/**
 * 表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    type: 'http',
    timeout: 30,
    is_active: true,
  };
}
