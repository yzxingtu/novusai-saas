/**
 * 智能体管理（平台端） - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AIAgentInfo } from '#/api/admin/ai';

import { searchInput, select } from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

function getStatusOptions() {
  return [
    { label: $t('admin.ai.agent.status_options.draft'), value: 'draft' },
    { label: $t('admin.ai.agent.status_options.published'), value: 'published' },
    { label: $t('admin.ai.agent.status_options.disabled'), value: 'disabled' },
  ];
}

function getExecutionModeOptions() {
  return [
    { label: $t('admin.ai.agent.mode_options.conversation'), value: 'conversation' },
    { label: $t('admin.ai.agent.mode_options.task'), value: 'task' },
    { label: $t('admin.ai.agent.mode_options.batch'), value: 'batch' },
    { label: $t('admin.ai.agent.mode_options.api'), value: 'api' },
  ];
}

/**
 * 获取状态文本
 */
export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  switch (status) {
    case 'draft': {
      return $t('admin.ai.agent.status_options.draft');
    }
    case 'published': {
      return $t('admin.ai.agent.status_options.published');
    }
    case 'disabled': {
      return $t('admin.ai.agent.status_options.disabled');
    }
    default: {
      return status;
    }
  }
}

/**
 * 获取执行模式文本
 */
export function getExecutionModeText(mode: string | undefined): string {
  if (!mode) return '-';
  switch (mode) {
    case 'conversation': {
      return $t('admin.ai.agent.mode_options.conversation');
    }
    case 'task': {
      return $t('admin.ai.agent.mode_options.task');
    }
    case 'batch': {
      return $t('admin.ai.agent.mode_options.batch');
    }
    case 'api': {
      return $t('admin.ai.agent.mode_options.api');
    }
    default: {
      return mode;
    }
  }
}

/**
 * 表格列定义
 */
export function useColumns<T = AIAgentInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('admin.ai.agent.name'),
      minWidth: 160,
      slots: { default: 'name_cell' },
    },
    {
      field: 'status',
      title: $t('admin.ai.agent.status'),
      width: 110,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'execution_mode',
      title: $t('admin.ai.agent.executionMode'),
      width: 120,
      align: 'center',
      slots: { default: 'mode_cell' },
    },
    {
      field: 'model_name',
      title: $t('admin.ai.agent.modelName'),
      width: 160,
      align: 'center',
      slots: { default: 'modelName_cell' },
    },
    {
      field: 'tenant_id',
      title: $t('admin.ai.agent.tenantId'),
      width: 100,
      align: 'center',
    },
    {
      field: 'published_version',
      title: $t('admin.ai.agent.version'),
      width: 90,
      align: 'center',
      slots: { default: 'version_cell' },
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
          resource: 'ai_agent',
          nameField: 'name',
          nameTitle: $t('admin.ai.agent.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'toggleStatus',
            text: $t('admin.common.toggleStatus'),
            icon: 'lucide:toggle-right',
            accessCodes: ['ai_agent:update'],
          },
          {
            code: 'detail',
            text: $t('admin.ai.agent.viewDetail'),
            icon: 'lucide:eye',
            accessCodes: ['ai_agent:detail'],
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
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('filter[name][ilike]', $t('admin.ai.agent.name'), {
      placeholder: $t('admin.ai.agent.placeholder.searchName'),
    }),
    select('filter[status][eq]', $t('admin.ai.agent.status'), {
      options: getStatusOptions(),
      placeholder: $t('admin.ai.agent.placeholder.allStatuses'),
    }),
    select('filter[execution_mode][eq]', $t('admin.ai.agent.executionMode'), {
      options: getExecutionModeOptions(),
      placeholder: $t('admin.ai.agent.placeholder.allModes'),
    }),
    select('filter[tenant_id]', $t('admin.ai.agent.tenantId'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.ai.agent.placeholder.allTenants'),
    }),
  ];
}
