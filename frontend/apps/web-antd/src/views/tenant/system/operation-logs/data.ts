/**
 * 操作日志管理（租户端） - 表格列和搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { tenantApi } from '#/api';

import { searchDateRange, searchInput } from '#/adapter/form';
import { $t } from '#/locales';

type OperationLogInfo = tenantApi.OperationLogInfo;

/**
 * 获取响应状态颜色
 */
export function getStatusColor(status: number | undefined): string {
  if (status === undefined || status === null) return 'default';
  if (status >= 200 && status < 300) return 'success';
  if (status >= 400 && status < 500) return 'warning';
  if (status >= 500) return 'error';
  return 'default';
}

/**
 * 获取请求方法颜色
 */
export function getMethodColor(method: string | undefined): string {
  if (!method) return 'default';
  switch (method.toUpperCase()) {
    case 'DELETE': {
      return 'red';
    }
    case 'GET': {
      return 'blue';
    }
    case 'PATCH': {
      return 'purple';
    }
    case 'POST': {
      return 'green';
    }
    case 'PUT': {
      return 'orange';
    }
    default: {
      return 'default';
    }
  }
}

/**
 * 表格列定义（租户端无删除操作）
 */
export function useColumns<T = OperationLogInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'username',
      title: $t('tenant.system.operationLog.username'),
      width: 180,
      slots: {
        default: 'username_cell',
      },
    },
    {
      field: 'module',
      title: $t('tenant.system.operationLog.module'),
      width: 100,
      slots: {
        default: 'module_cell',
      },
    },
    {
      field: 'action',
      title: $t('tenant.system.operationLog.action'),
      width: 100,
      slots: {
        default: 'action_cell',
      },
    },
    {
      field: 'method',
      title: $t('tenant.system.operationLog.method'),
      width: 100,
      align: 'center',
      slots: {
        default: 'method_cell',
      },
    },
    {
      field: 'path',
      title: $t('tenant.system.operationLog.path'),
      minWidth: 200,
      slots: {
        default: 'path_cell',
      },
    },
    {
      field: 'statusCode',
      title: $t('tenant.system.operationLog.statusCode'),
      width: 100,
      align: 'center',
      slots: {
        default: 'statusCode_cell',
      },
    },
    {
      field: 'durationMs',
      title: $t('tenant.system.operationLog.durationMs'),
      width: 100,
      align: 'center',
      slots: {
        default: 'durationMs_cell',
      },
    },
    {
      field: 'ip',
      title: $t('tenant.system.operationLog.ip'),
      width: 140,
      slots: {
        default: 'ip_cell',
      },
    },
    {
      field: 'createdAt',
      title: $t('tenant.system.operationLog.createdAt'),
      width: 160,
      slots: {
        default: 'createdAt_cell',
      },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'operation_log',
          nameField: 'id',
          nameTitle: 'ID',
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('tenant.system.operationLog.detail'),
            icon: 'lucide:eye',
            accessCodes: ['operation_log:detail'],
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('tenant.common.operation'),
      width: 100,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Select',
      componentProps: {
        allowClear: true,
        class: 'w-full',
        options: [],
        placeholder: $t(
          'tenant.system.operationLog.placeholder.searchUsername',
        ),
        showSearch: true,
        optionFilterProp: 'label',
      },
      fieldName: 'filter[username]',
      label: $t('tenant.system.operationLog.username'),
    },
    searchInput('module', $t('tenant.system.operationLog.module'), {
      placeholder: $t('tenant.system.operationLog.placeholder.searchModule'),
    }),
    searchInput('action', $t('tenant.system.operationLog.action'), {
      placeholder: $t('tenant.system.operationLog.placeholder.searchAction'),
    }),
    searchInput('ip', $t('tenant.system.operationLog.ip'), {
      placeholder: $t('tenant.system.operationLog.placeholder.searchIp'),
    }),
    searchDateRange({
      field: 'created_at',
      label: $t('tenant.system.operationLog.createdAt'),
      placeholder: [
        $t('tenant.system.operationLog.placeholder.startDate'),
        $t('tenant.system.operationLog.placeholder.endDate'),
      ],
    }),
  ];
}
