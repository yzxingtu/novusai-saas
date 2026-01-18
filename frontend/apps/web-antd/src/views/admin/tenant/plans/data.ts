/**
 * 套餐管理 - 表格列和表单配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { adminApi } from '#/api';

import { checkboxColumn, dragColumn } from '#/adapter/vxe-table';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

type TenantPlanInfo = adminApi.TenantPlanInfo;
type BillingCycle = adminApi.BillingCycle;

/**
 * 计费周期选项
 */
export function getBillingCycleOptions(): {
  label: string;
  value: BillingCycle;
}[] {
  return [
    {
      label: $t('admin.tenant.plan.billingCycleOptions.monthly'),
      value: 'monthly',
    },
    {
      label: $t('admin.tenant.plan.billingCycleOptions.quarterly'),
      value: 'quarterly',
    },
    {
      label: $t('admin.tenant.plan.billingCycleOptions.yearly'),
      value: 'yearly',
    },
    {
      label: $t('admin.tenant.plan.billingCycleOptions.lifetime'),
      value: 'lifetime',
    },
    {
      label: $t('admin.tenant.plan.billingCycleOptions.one_time'),
      value: 'one_time',
    },
  ];
}

/**
 * 获取计费周期显示文本
 */
export function getBillingCycleText(cycle: BillingCycle): string {
  const key = `admin.tenant.plan.billingCycleOptions.${cycle}`;
  return $t(key);
}

/**
 * 格式化价格显示
 */
export function formatPrice(
  price?: null | number | string,
  cycle?: BillingCycle,
): string {
  if (price === null || price === undefined) return '-';
  const priceNum = typeof price === 'string' ? Number.parseFloat(price) : price;
  if (Number.isNaN(priceNum)) return '-';

  const priceStr = `¥${priceNum.toFixed(2)}`;
  if (!cycle) return priceStr;

  const cycleText = getBillingCycleText(cycle);
  return `${priceStr}/${cycleText}`;
}

/**
 * 表格列定义
 */
export function useColumns<T = TenantPlanInfo>(
  onActionClick: OnActionClickFn<T>,
  onStatusChange?: (newStatus: boolean, row: T) => Promise<boolean | undefined>,
): VxeTableGridOptions['columns'] {
  return [
    // 复选框列
    checkboxColumn,
    // 拖拽排序列
    dragColumn,
    {
      field: 'name',
      title: $t('admin.tenant.plan.name'),
      minWidth: 150,
      className: 'font-medium',
    },
    {
      field: 'code',
      title: $t('admin.tenant.plan.code'),
      minWidth: 120,
      className: 'font-mono text-gray-500',
    },
    {
      field: 'price',
      title: $t('admin.tenant.plan.price'),
      width: 150,
      align: 'right',
      formatter: ({ row }: { row: TenantPlanInfo }) =>
        formatPrice(row.price, row.billingCycle),
    },
    {
      field: 'sortOrder',
      title: $t('admin.tenant.plan.sortOrder'),
      width: 80,
      align: 'center',
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
          { color: 'error', label: $t('admin.common.disabled'), value: false },
        ],
      },
      field: 'isActive',
      title: $t('admin.tenant.plan.isActive'),
      width: 90,
      align: 'center',
    },
    {
      field: 'createdAt',
      formatter: ({ cellValue }) => formatDate(cellValue),
      title: $t('admin.common.createdAt'),
      width: 170,
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'tenant_plan',
          nameField: 'name',
          nameTitle: $t('admin.tenant.plan.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          'edit',
          {
            code: 'permissions',
            text: $t('admin.tenant.plan.setPermissions'),
            icon: 'lucide:shield-check',
            accessCodes: ['tenant_plan:assign_permissions'],
          },
          'delete',
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 180,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      componentProps: {
        allowClear: true,
        placeholder: $t('admin.tenant.plan.placeholder.searchName'),
      },
      fieldName: 'filter[name][ilike]',
      label: $t('admin.tenant.plan.name'),
    },
    {
      component: 'Input',
      componentProps: {
        allowClear: true,
        placeholder: $t('admin.tenant.plan.placeholder.searchCode'),
      },
      fieldName: 'filter[code][ilike]',
      label: $t('admin.tenant.plan.code'),
    },
    {
      component: 'Select',
      componentProps: {
        allowClear: true,
        options: [
          { label: $t('admin.common.enabled'), value: true },
          { label: $t('admin.common.disabled'), value: false },
        ],
        placeholder: $t('admin.tenant.plan.placeholder.allStatus'),
      },
      fieldName: 'filter[is_active]',
      label: $t('admin.tenant.plan.isActive'),
    },
  ];
}

/**
 * 新建/编辑表单 Schema
 */
export function useFormSchema(_isEdit: boolean = false): VbenFormSchema[] {
  const schema: VbenFormSchema[] = [];

  // 套餐代码由后端自动生成，不需要在表单中填写

  schema.push(
    {
      component: 'Input',
      componentProps: {
        maxLength: 100,
        placeholder: $t('admin.tenant.plan.placeholder.inputName'),
      },
      fieldName: 'name',
      label: $t('admin.tenant.plan.name'),
      rules: 'required',
    },
    {
      component: 'Textarea',
      componentProps: {
        maxLength: 500,
        placeholder: $t('admin.tenant.plan.placeholder.inputDescription'),
        rows: 2,
      },
      fieldName: 'description',
      label: $t('admin.tenant.plan.description'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        min: 0,
        precision: 2,
        placeholder: $t('admin.tenant.plan.placeholder.inputPrice'),
        style: { width: '100%' },
      },
      fieldName: 'price',
      label: $t('admin.tenant.plan.price'),
    },
    {
      component: 'Select',
      componentProps: {
        options: getBillingCycleOptions(),
        placeholder: $t('admin.tenant.plan.placeholder.selectBillingCycle'),
      },
      defaultValue: 'monthly',
      fieldName: 'billing_cycle',
      label: $t('admin.tenant.plan.billingCycle'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.inputSortOrder'),
        style: { width: '100%' },
      },
      defaultValue: 0,
      fieldName: 'sort_order',
      label: $t('admin.tenant.plan.sortOrder'),
    },
    {
      component: 'Switch',
      defaultValue: true,
      fieldName: 'is_active',
      label: $t('admin.tenant.plan.isActive'),
    },
    // 配额设置 - 分组显示
    {
      component: 'Divider',
      componentProps: {
        orientation: 'left',
      },
      fieldName: '_quota_divider',
      label: $t('admin.tenant.plan.quota'),
      renderComponentContent: () => ({
        default: () => $t('admin.tenant.plan.quota'),
      }),
    },
    {
      component: 'InputNumber',
      componentProps: {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
        style: { width: '100%' },
      },
      fieldName: 'quota.storage_limit_gb',
      label: $t('admin.tenant.plan.storageLimitGb'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
        style: { width: '100%' },
      },
      fieldName: 'quota.max_users',
      label: $t('admin.tenant.plan.maxUsers'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
        style: { width: '100%' },
      },
      fieldName: 'quota.max_admins',
      label: $t('admin.tenant.plan.maxAdmins'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
        style: { width: '100%' },
      },
      fieldName: 'quota.max_custom_domains',
      label: $t('admin.tenant.plan.maxCustomDomains'),
    },
    {
      component: 'Switch',
      defaultValue: false,
      fieldName: 'quota.allow_custom_domain',
      label: $t('admin.tenant.plan.allowCustomDomain'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
        style: { width: '100%' },
      },
      fieldName: 'quota.api_calls_per_month',
      label: $t('admin.tenant.plan.apiCallsPerMonth'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
        style: { width: '100%' },
      },
      fieldName: 'quota.max_file_size_mb',
      label: $t('admin.tenant.plan.maxFileSizeMb'),
    },
    // 特性标记 - 分组显示
    {
      component: 'Divider',
      componentProps: {
        orientation: 'left',
      },
      fieldName: '_features_divider',
      label: $t('admin.tenant.plan.features'),
      renderComponentContent: () => ({
        default: () => $t('admin.tenant.plan.features'),
      }),
    },
    {
      component: 'Switch',
      defaultValue: false,
      fieldName: 'features.ai_enabled',
      label: $t('admin.tenant.plan.aiEnabled'),
    },
    {
      component: 'Switch',
      defaultValue: false,
      fieldName: 'features.advanced_analytics',
      label: $t('admin.tenant.plan.advancedAnalytics'),
    },
    {
      component: 'Switch',
      defaultValue: false,
      fieldName: 'features.white_label',
      label: $t('admin.tenant.plan.whiteLabel'),
    },
    {
      component: 'Switch',
      defaultValue: false,
      fieldName: 'features.priority_support',
      label: $t('admin.tenant.plan.prioritySupport'),
    },
  );

  return schema;
}

/**
 * 表单默认值
 */
export function getFormDefaults(): Record<string, any> {
  return {
    billing_cycle: 'monthly',
    is_active: true,
    sort_order: 0,
    'quota.allow_custom_domain': false,
    'features.ai_enabled': false,
    'features.advanced_analytics': false,
    'features.white_label': false,
    'features.priority_support': false,
  };
}
