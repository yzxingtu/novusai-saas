/**
 * 租户管理 - 表格列和表单配置
 * 遵循 vben-admin 规范
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { adminApi } from '#/api';

import { getTenantPlanSelectApi } from '#/api/admin/plan';
import { $t } from '#/locales';

type TenantInfo = adminApi.TenantInfo;
type TenantPlan = adminApi.TenantPlan;

/**
 * 套餐选项
 */
export function getPlanOptions(): { label: string; value: TenantPlan }[] {
  return [
    { label: $t('admin.tenant.planOptions.free'), value: 'free' },
    { label: $t('admin.tenant.planOptions.basic'), value: 'basic' },
    { label: $t('admin.tenant.planOptions.pro'), value: 'pro' },
    { label: $t('admin.tenant.planOptions.enterprise'), value: 'enterprise' },
  ];
}

// For backward compatibility - 使用函数获取以支持 i18n
export function PLAN_OPTIONS(): { label: string; value: TenantPlan }[] {
  return getPlanOptions();
}

/**
 * 获取套餐显示文本
 */
export function getPlanText(plan: null | TenantPlan | undefined): string {
  if (!plan) return '-';
  const key = `admin.tenant.planOptions.${plan}`;
  return $t(key);
}

/**
 * 获取套餐颜色
 */
export function getPlanColor(plan: null | TenantPlan | undefined): string {
  if (!plan) return 'default';
  switch (plan) {
    case 'basic': {
      return 'blue';
    }
    case 'enterprise': {
      return 'gold';
    }
    case 'free': {
      return 'default';
    }
    case 'pro': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}

/**
 * 表格列定义
 * @param onActionClick 操作按钮点击回调
 * @param onStatusChange 状态切换回调
 */
export function useColumns<T = TenantInfo>(
  onActionClick: OnActionClickFn<T>,
  onStatusChange?: (newStatus: boolean, row: T) => Promise<boolean | undefined>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'code',
      title: $t('admin.tenant.code'),
      minWidth: 140,
      slots: {
        default: 'code_cell',
      },
    },
    {
      field: 'name',
      title: $t('admin.tenant.name'),
      minWidth: 180,
      slots: {
        default: 'name_cell',
      },
    },
    {
      field: 'primaryDomain',
      title: $t('admin.tenant.domain.primaryDomain'),
      minWidth: 180,
      slots: {
        default: 'primaryDomain_cell',
      },
    },
    {
      field: 'domainCount',
      title: $t('admin.tenant.domain.domainCount'),
      width: 90,
      align: 'center',
      slots: {
        default: 'domainCount_cell',
      },
    },
    {
      field: 'contactName',
      title: $t('admin.tenant.contactName'),
      width: 100,
      slots: {
        default: 'contactName_cell',
      },
    },
    {
      field: 'contactPhone',
      title: $t('admin.tenant.contactPhone'),
      width: 130,
      slots: {
        default: 'contactPhone_cell',
      },
    },
    {
      field: 'planInfo',
      title: $t('admin.tenant.planField'),
      width: 140,
      align: 'center',
      slots: {
        default: 'planInfo_cell',
      },
    },
    {
      cellRender: {
        attrs: {
          beforeChange: onStatusChange,
          checkedValue: true,
          unCheckedValue: false,
        },
        name: onStatusChange ? 'CellSwitch' : 'CellTag',
        options: [
          { color: 'success', label: $t('admin.common.enabled'), value: true },
          {
            color: 'error',
            label: $t('admin.common.disabled'),
            value: false,
          },
        ],
      },
      field: 'isActive',
      title: $t('admin.tenant.status'),
      width: 90,
      align: 'center',
    },
    {
      field: 'expiresAt',
      title: $t('admin.tenant.expiresAt'),
      width: 120,
      align: 'center',
      slots: {
        default: 'expiresAt_cell',
      },
    },
    {
      field: 'createdAt',
      title: $t('admin.tenant.createdAt'),
      width: 130,
      slots: {
        default: 'createdAt_cell',
      },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'tenant', // 自动检查 tenant:update, tenant:delete
          nameField: 'name',
          nameTitle: $t('admin.tenant.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'manageDomains',
            text: $t('admin.tenant.manageDomains'),
            icon: 'lucide:globe',
            accessCodes: ['tenant:update'], // 域名管理需要更新权限
          },
          {
            code: 'impersonate',
            text: $t('admin.tenant.enterBackend'),
            icon: 'lucide:log-in',
            accessCodes: ['tenant:impersonate'], // 自定义权限
          },
          'edit', // 自动鉴权: tenant:update
          'delete', // 自动鉴权: tenant:delete
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 120,
    },
  ];
}

/**
 * 搜索表单 Schema
 * 字段名直接使用 JSON:API 格式
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      componentProps: {
        allowClear: true,
        placeholder: $t('admin.tenant.placeholder.searchCode'),
      },
      fieldName: 'filter[code][ilike]',
      label: $t('admin.tenant.code'),
    },
    {
      component: 'Input',
      componentProps: {
        allowClear: true,
        placeholder: $t('admin.tenant.placeholder.searchName'),
      },
      fieldName: 'filter[name][ilike]',
      label: $t('admin.tenant.name'),
    },
    {
      component: 'Input',
      componentProps: {
        allowClear: true,
        placeholder: $t('admin.tenant.placeholder.searchContact'),
      },
      fieldName: 'filter[contact_name][ilike]',
      label: $t('admin.tenant.contactName'),
    },
    {
      component: 'Input',
      componentProps: {
        allowClear: true,
        placeholder: $t('admin.tenant.placeholder.searchPhone'),
      },
      fieldName: 'filter[contact_phone][ilike]',
      label: $t('admin.tenant.contactPhone'),
    },
    {
      component: 'Select',
      componentProps: {
        allowClear: true,
        class: 'w-full',
        options: [
          { label: $t('admin.common.enabled'), value: true },
          { label: $t('admin.common.disabled'), value: false },
        ],
        placeholder: $t('admin.tenant.placeholder.allStatus'),
      },
      fieldName: 'filter[is_active]',
      label: $t('admin.tenant.status'),
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: getTenantPlanSelectApi,
        class: 'w-full',
        filterOption: false,
        params: { is_active: 'true' },
        placeholder: $t('admin.tenant.placeholder.allPlan'),
        resultField: 'items',
        showSearch: true,
        pagination: true,
        clickPagination: true,
        pageSize: 10,
        optionRightField: 'extra.code',
      },
      fieldName: 'filter[plan_id]',
      label: $t('admin.tenant.planField'),
    },
  ];
}

/**
 * 新建/编辑表单 Schema
 * @param isEdit 是否编辑模式
 */
export function useFormSchema(isEdit: boolean = false): VbenFormSchema[] {
  const schema: VbenFormSchema[] = [];

  // 编辑模式时显示租户编码（只读）
  if (isEdit) {
    schema.push({
      component: 'Input',
      componentProps: {
        disabled: true,
      },
      fieldName: 'code',
      label: $t('admin.tenant.code'),
    });
  }

  schema.push(
    {
      component: 'Input',
      componentProps: {
        maxLength: 100,
        placeholder: $t('admin.tenant.placeholder.inputName'),
      },
      fieldName: 'name',
      label: $t('admin.tenant.name'),
      rules: 'required',
    },
    {
      component: 'Input',
      componentProps: {
        placeholder: $t('admin.tenant.placeholder.inputContactName'),
      },
      fieldName: 'contact_name',
      label: $t('admin.tenant.contactName'),
    },
    {
      component: 'Input',
      componentProps: {
        placeholder: $t('admin.tenant.placeholder.inputContactPhone'),
      },
      fieldName: 'contact_phone',
      label: $t('admin.tenant.contactPhone'),
    },
    {
      component: 'Input',
      componentProps: {
        placeholder: $t('admin.tenant.placeholder.inputContactEmail'),
        type: 'email',
      },
      fieldName: 'contact_email',
      label: $t('admin.tenant.contactEmail'),
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: getTenantPlanSelectApi,
        class: 'w-full',
        filterOption: false,
        params: { is_active: 'true' },
        placeholder: $t('admin.tenant.placeholder.selectPlanId'),
        resultField: 'items',
        showSearch: true,
        pagination: true,
        clickPagination: true,
        pageSize: 10,
        optionRightField: 'extra.code',
      },
      fieldName: 'plan_id',
      label: $t('admin.tenant.planId'),
    },
    {
      component: 'DatePicker',
      componentProps: {
        class: 'w-full',
        format: 'YYYY-MM-DD',
        placeholder: $t('admin.tenant.placeholder.selectExpiresAt'),
        valueFormat: 'YYYY-MM-DD',
      },
      fieldName: 'expires_at',
      label: $t('admin.tenant.expiresAt'),
    },
    {
      component: 'Textarea',
      componentProps: {
        placeholder: $t('admin.tenant.placeholder.inputRemark'),
        rows: 3,
      },
      fieldName: 'remark',
      label: $t('admin.tenant.remark'),
    },
  );

  return schema;
}
