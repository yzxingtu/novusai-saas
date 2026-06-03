/**
 * 企业管理 - 表格列和表单配置
 * 遵循 vben-admin 规范
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { adminApi } from '#/api';

import {
  dateField,
  dividerField,
  inputField,
  searchDateRange,
  searchInput,
  select,
  statusSelect,
  textareaField,
  z,
} from '#/adapter/form';
import { getTenantPlanSelectApi } from '#/api/admin/plan';
import { $t } from '#/locales';
import { useAccess } from '#/utils';

type TenantInfo = adminApi.TenantInfo;

/**
 * 表格列定义
 * @param _onActionClick 操作按钮点击回调
 * @param onStatusChange 状态切换回调
 */
export function useColumns<T = TenantInfo>(
  _onActionClick: OnActionClickFn<T>,
  onStatusChange?: (newStatus: boolean, row: T) => Promise<boolean | undefined>,
): VxeTableGridOptions['columns'] {
  const { hasAccessByCodes } = useAccess();
  const canToggleStatus =
    !!onStatusChange && hasAccessByCodes(['tenant:update']);

  return [
    {
      type: 'expand',
      width: 40,
      slots: { content: 'expand_content' },
    },
    {
      field: 'name',
      title: $t('admin.tenant.name'),
      minWidth: 200,
      slots: {
        default: 'name_cell',
      },
    },
    {
      field: 'primaryDomain',
      title: $t('admin.tenant.domain.primaryDomain'),
      minWidth: 220,
      slots: {
        default: 'primaryDomain_cell',
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
          beforeChange: canToggleStatus ? onStatusChange : undefined,
          checkedValue: true,
          unCheckedValue: false,
        },
        name: canToggleStatus ? 'CellSwitch' : 'CellTag',
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
      field: 'operation',
      fixed: 'right',
      slots: {
        default: 'operation_cell',
      },
      title: $t('admin.common.operation'),
      width: 140,
    },
  ];
}

// ============ 业务预设 / Business presets ============

/** 套餐选择器 / Plan selector */
function planSelect(
  options: { required?: boolean; search?: boolean } = {},
): VbenFormSchema {
  const { search = false, required = false } = options;
  return select(
    search ? 'filter[plan_id]' : 'plan_id',
    $t('admin.tenant.planField'),
    {
      api: getTenantPlanSelectApi,
      params: { is_active: 'true' },
      extraField: 'code',
      required,
      placeholder: search
        ? $t('admin.tenant.placeholder.allPlan')
        : $t('admin.tenant.placeholder.selectPlanId'),
    },
  );
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('code', $t('admin.tenant.code'), {
      placeholder: $t('admin.tenant.placeholder.searchCode'),
    }),
    searchInput('name', $t('admin.tenant.name'), {
      placeholder: $t('admin.tenant.placeholder.searchName'),
    }),
    searchInput('contact_name', $t('admin.tenant.contactName'), {
      placeholder: $t('admin.tenant.placeholder.searchContact'),
    }),
    searchInput('contact_phone', $t('admin.tenant.contactPhone'), {
      placeholder: $t('admin.tenant.placeholder.searchPhone'),
    }),
    statusSelect(),
    planSelect({ search: true }),
    searchDateRange({
      field: 'created_at',
      label: $t('admin.tenant.createdAt'),
    }),
  ];
}

/**
 * 新建/编辑表单 Schema
 * @param isEdit 是否编辑模式
 */
export function useFormSchema(isEdit: boolean = false): VbenFormSchema[] {
  return [
    // Show tenant code in edit mode (readonly) / 编辑模式时显示企业编码（只读）
    ...(isEdit
      ? [inputField('code', $t('admin.tenant.code'), { disabled: true })]
      : []),
    inputField('name', $t('admin.tenant.name'), {
      required: true,
      maxLength: 100,
      placeholder: $t('admin.tenant.placeholder.inputName'),
    }),
    inputField('contact_name', $t('admin.tenant.contactName'), {
      placeholder: $t('admin.tenant.placeholder.inputContactName'),
    }),
    inputField('contact_phone', $t('admin.tenant.contactPhone'), {
      placeholder: $t('admin.tenant.placeholder.inputContactPhone'),
    }),
    inputField('contact_email', $t('admin.tenant.contactEmail'), {
      placeholder: $t('admin.tenant.placeholder.inputContactEmail'),
    }),
    planSelect(),
    dateField('expires_at', $t('admin.tenant.expiresAt'), {
      placeholder: $t('admin.tenant.placeholder.selectExpiresAt'),
    }),
    textareaField('remark', $t('admin.tenant.remark'), {
      placeholder: $t('admin.tenant.placeholder.inputRemark'),
    }),
    // Show admin info in create mode / 新建时显示管理员信息
    ...(isEdit
      ? []
      : [
          dividerField('_admin_divider', $t('admin.tenant.adminInfo')),
          {
            component: 'Input',
            componentProps: {
              maxLength: 50,
              placeholder: $t('admin.tenant.placeholder.inputAdminUsername'),
            },
            fieldName: 'admin_username',
            label: $t('admin.tenant.adminUsername'),
            rules: z
              .string()
              .min(2, $t('admin.tenant.validation.usernameMin'))
              .max(50, $t('admin.tenant.validation.usernameMax')),
          } as VbenFormSchema,
          {
            component: 'Input',
            componentProps: {
              placeholder: $t('admin.tenant.placeholder.inputAdminEmail'),
              type: 'email',
            },
            fieldName: 'admin_email',
            label: $t('admin.tenant.adminEmail'),
            rules: z.string().email($t('admin.tenant.validation.emailInvalid')),
          } as VbenFormSchema,
          {
            component: 'InputPassword',
            componentProps: {
              placeholder: $t('admin.tenant.placeholder.inputAdminPassword'),
            },
            fieldName: 'admin_password',
            label: $t('admin.tenant.adminPassword'),
            rules: z
              .string()
              .min(6, $t('admin.tenant.validation.passwordMin'))
              .max(100, $t('admin.tenant.validation.passwordMax')),
          } as VbenFormSchema,
        ]),
  ];
}

/**
 * 重置企业管理员密码表单 Schema
 */
export function useResetPasswordSchema(): VbenFormSchema[] {
  return [
    {
      component: 'InputPassword',
      componentProps: {
        placeholder: $t('admin.tenant.placeholder.inputNewPassword'),
      },
      fieldName: 'new_password',
      label: $t('admin.tenant.newPassword'),
      rules: z
        .string()
        .min(6, $t('admin.tenant.validation.passwordMin'))
        .max(100, $t('admin.tenant.validation.passwordMax')),
    },
    {
      component: 'InputPassword',
      componentProps: {
        placeholder: $t('admin.tenant.placeholder.confirmPassword'),
      },
      fieldName: 'confirm_password',
      label: $t('admin.tenant.confirmPassword'),
      dependencies: {
        triggerFields: ['new_password'],
        rules: (values) =>
          z
            .string()
            .min(1, $t('admin.tenant.validation.confirmRequired'))
            .refine((v) => v === values.new_password, {
              message: $t('admin.tenant.messages.passwordMismatch'),
            }),
      },
    },
  ];
}
