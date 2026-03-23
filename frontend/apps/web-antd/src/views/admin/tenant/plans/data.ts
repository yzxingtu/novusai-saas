/**
 * Plan management - table columns & form config
 * 套餐管理 - 表格列和表单配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { adminApi } from '#/api';

import {
  dividerField,
  inputField,
  numberField,
  searchDateRange,
  searchInput,
  select,
  statusSelect,
  switchField,
  textareaField,
} from '#/adapter/form';
import { checkboxColumn, dragColumn } from '#/adapter/vxe-table';
import { $t } from '#/locales';

// ... (keep type definitions and helper functions) / (保留类型定义和辅助函数)

// ... (keep useColumns) / (保留 useColumns)

/**
 * Get billing cycle options / 获取计费周期选项
 */
export function getBillingCycleOptions(): {
  label: string;
  value: adminApi.BillingCycle;
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
 * Get billing cycle display text / 获取计费周期显示文本
 */
export function getBillingCycleText(cycle: adminApi.BillingCycle): string {
  const key = `admin.tenant.plan.billingCycleOptions.${cycle}`;
  return $t(key);
}

/**
 * Format price display / 格式化价格显示
 */
export function formatPrice(
  price?: null | number | string,
  cycle?: adminApi.BillingCycle,
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
 * Table column definitions / 表格列定义
 */
export function useColumns<T = adminApi.TenantPlanInfo>(
  onActionClick: OnActionClickFn<T>,
  onStatusChange?: (newStatus: boolean, row: T) => Promise<boolean | undefined>,
): VxeTableGridOptions['columns'] {
  return [
    // Checkbox column / 复选框列
    checkboxColumn,
    // Drag sort column / 拖拽排序列
    dragColumn,
    {
      field: 'name',
      title: $t('admin.tenant.plan.name'),
      minWidth: 180,
      slots: {
        default: 'name_cell',
      },
    },
    {
      field: 'code',
      title: $t('admin.tenant.plan.code'),
      minWidth: 140,
      align: 'center',
      slots: {
        default: 'code_cell',
      },
    },
    {
      field: 'price',
      title: $t('admin.tenant.plan.price'),
      width: 140,
      align: 'center',
      slots: {
        default: 'price_cell',
      },
    },
    {
      field: 'quota',
      title: $t('admin.tenant.plan.quota'),
      minWidth: 180,
      align: 'center',
      slots: {
        default: 'quota_cell',
      },
    },
    {
      field: 'features',
      title: $t('admin.tenant.plan.features'),
      minWidth: 180,
      align: 'center',
      slots: {
        default: 'features_cell',
      },
    },
    {
      field: 'billingCycle',
      title: $t('admin.tenant.plan.billingCycle'),
      width: 100,
      align: 'center',
      slots: {
        default: 'billingCycle_cell',
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
      title: $t('admin.common.createdAt'),
      width: 130,
      align: 'center',
      slots: {
        default: 'createdAt_cell',
      },
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
 * Search form Schema / 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('admin.tenant.plan.name'), {
      placeholder: $t('admin.tenant.plan.placeholder.searchName'),
    }),
    searchInput('code', $t('admin.tenant.plan.code'), {
      placeholder: $t('admin.tenant.plan.placeholder.searchCode'),
    }),
    statusSelect({ label: $t('admin.tenant.plan.isActive') }),
    searchDateRange({
      field: 'created_at',
      label: $t('admin.common.createdAt'),
    }),
  ];
}

/**
 * Create/edit form Schema / 新建/编辑表单 Schema
 */
export function useFormSchema(_isEdit: boolean = false): VbenFormSchema[] {
  return [
    // Basic info / 基本信息
    inputField('name', $t('admin.tenant.plan.name'), {
      required: true,
      maxLength: 100,
      placeholder: $t('admin.tenant.plan.placeholder.inputName'),
    }),
    textareaField('description', $t('admin.tenant.plan.description'), {
      maxLength: 500,
      rows: 2,
      placeholder: $t('admin.tenant.plan.placeholder.inputDescription'),
    }),
    numberField('price', $t('admin.tenant.plan.price'), {
      min: 0,
      precision: 2,
      placeholder: $t('admin.tenant.plan.placeholder.inputPrice'),
    }),
    select('billing_cycle', $t('admin.tenant.plan.billingCycle'), {
      options: getBillingCycleOptions(),
      placeholder: $t('admin.tenant.plan.placeholder.selectBillingCycle'),
    }),
    numberField('sort_order', $t('admin.tenant.plan.sortOrder'), {
      min: 0,
      defaultValue: 0,
      placeholder: $t('admin.tenant.plan.placeholder.inputSortOrder'),
    }),
    switchField('is_active', $t('admin.tenant.plan.isActive'), {
      defaultValue: true,
    }),

    // Quota settings / 配额设置
    dividerField('_quota_divider', $t('admin.tenant.plan.quota')),
    numberField(
      'quota.storage_limit_gb',
      $t('admin.tenant.plan.storageLimitGb'),
      {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
      },
    ),
    numberField('quota.max_users', $t('admin.tenant.plan.maxUsers'), {
      min: 0,
      placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
    }),
    numberField('quota.max_admins', $t('admin.tenant.plan.maxAdmins'), {
      min: 0,
      placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
    }),
    numberField(
      'quota.max_custom_domains',
      $t('admin.tenant.plan.maxCustomDomains'),
      {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
      },
    ),
    switchField(
      'quota.allow_custom_domain',
      $t('admin.tenant.plan.allowCustomDomain'),
    ),
    numberField(
      'quota.api_calls_per_month',
      $t('admin.tenant.plan.apiCallsPerMonth'),
      {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
      },
    ),
    numberField(
      'quota.max_file_size_mb',
      $t('admin.tenant.plan.maxFileSizeMb'),
      {
        min: 0,
        placeholder: $t('admin.tenant.plan.placeholder.unlimited'),
      },
    ),

    // Feature flags / 特性标记
    dividerField('_features_divider', $t('admin.tenant.plan.features')),
    switchField('features.ai_enabled', $t('admin.tenant.plan.aiEnabled')),
    switchField(
      'features.advanced_analytics',
      $t('admin.tenant.plan.advancedAnalytics'),
    ),
    switchField('features.white_label', $t('admin.tenant.plan.whiteLabel')),
    switchField(
      'features.priority_support',
      $t('admin.tenant.plan.prioritySupport'),
    ),
    switchField(
      'features.storage_billing_enabled',
      $t('admin.tenant.plan.storageBillingEnabled'),
      {
        help: $t('admin.tenant.plan.storageBillingHelp'),
      },
    ),
  ];
}

/**
 * Form default values / 表单默认值
 */
export function getFormDefaults(): Record<string, any> {
  return {
    billing_cycle: 'monthly',
    is_active: true,
    sort_order: 0,
    quota: {
      allow_custom_domain: false,
    },
    features: {
      ai_enabled: false,
      advanced_analytics: false,
      white_label: false,
      priority_support: false,
      storage_billing_enabled: false,
    },
  };
}
