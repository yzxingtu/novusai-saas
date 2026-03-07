/**
 * 用户架构页面 - 角色表单 & 用户成员表格配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { TenantUserInfo } from '#/api/tenant/tenant-users';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { $t } from '#/locales';

// ============================================================
// 角色表单 Schema（创建/编辑角色用）
// ============================================================

function getStatusOptions() {
  return [
    { label: $t('shared.status.active'), value: 'true' },
    { label: $t('shared.status.inactive'), value: 'false' },
  ];
}

export function useRoleFormSchema(isEdit: boolean): VbenFormSchema[] {
  return [
    inputField('name', $t('tenant.system.userRole.name'), {
      required: true,
      placeholder: $t('tenant.system.userRole.placeholder.inputName'),
    }),
    ...(isEdit
      ? [
          {
            ...inputField('code', $t('tenant.system.userRole.code'), {
              disabled: true,
            }),
            help: $t('tenant.system.userRole.help.codeHelp'),
          },
        ]
      : []),
    textareaField('description', $t('tenant.system.userRole.description'), {
      placeholder: $t('tenant.system.userRole.placeholder.inputDescription'),
    }),
    numberField('sort_order', $t('tenant.system.userRole.sortOrder'), {
      placeholder: $t('tenant.system.userRole.placeholder.inputSortOrder'),
      defaultValue: 0,
    }),
    switchField('is_active', $t('tenant.system.userRole.status'), {
      defaultValue: true,
    }),
  ];
}

export function getRoleFormDefaults(): Record<string, unknown> {
  return {
    is_active: true,
    sort_order: 0,
  };
}

// ============================================================
// 用户成员表格列定义（右侧面板）
// ============================================================

export function useMemberColumns<T = TenantUserInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'username',
      title: $t('tenant.system.user.username'),
      minWidth: 120,
      slots: { default: 'username_cell' },
    },
    {
      field: 'nickname',
      title: $t('tenant.system.user.nickname'),
      minWidth: 100,
    },
    {
      field: 'email',
      title: $t('tenant.system.user.email'),
      minWidth: 180,
    },
    {
      field: 'phone',
      title: $t('tenant.system.user.phone'),
      minWidth: 130,
    },
    {
      field: 'isActive',
      title: $t('tenant.system.user.status'),
      width: 100,
      align: 'center',
      slots: { default: 'status_cell' },
    },
    {
      field: 'lastLoginAt',
      title: $t('tenant.system.user.lastLoginAt'),
      width: 160,
      slots: { default: 'lastLoginAt_cell' },
    },
    {
      field: 'createdAt',
      title: $t('tenant.system.user.createdAt'),
      width: 160,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'tenant_user',
          nameField: 'username',
          nameTitle: $t('tenant.system.user.username'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          'edit',
          {
            code: 'resetPassword',
            text: $t('tenant.system.user.resetPassword'),
            icon: 'lucide:key',
            accessCodes: ['tenant_user:reset_password'],
          },
          'delete',
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('tenant.common.operation'),
      width: 220,
    },
  ];
}

export function useMemberSearchSchema(): VbenFormSchema[] {
  return [
    searchInput('username', $t('tenant.system.user.username'), {
      placeholder: $t('tenant.system.user.placeholder.searchUsername'),
    }),
    searchInput('email', $t('tenant.system.user.email'), {
      placeholder: $t('tenant.system.user.placeholder.searchEmail'),
    }),
    select('filter[is_active][eq]', $t('tenant.system.user.status'), {
      options: getStatusOptions(),
      placeholder: $t('tenant.system.user.placeholder.allStatus'),
    }),
  ];
}

// ============================================================
// 用户表单 Schema（创建/编辑用户用）
// ============================================================

export function useUserFormSchema(isEdit: boolean): VbenFormSchema[] {
  return [
    {
      ...inputField('username', $t('tenant.system.user.username'), {
        required: true,
        placeholder: $t('tenant.system.user.placeholder.inputUsername'),
        disabled: isEdit,
      }),
      help: isEdit
        ? $t('tenant.system.user.help.usernameEdit')
        : $t('tenant.system.user.help.usernameCreate'),
    },
    inputField('email', $t('tenant.system.user.email'), {
      required: true,
      placeholder: $t('tenant.system.user.placeholder.inputEmail'),
    }),
    ...(isEdit
      ? []
      : [
          {
            component: 'InputPassword',
            componentProps: {
              placeholder: $t('tenant.system.user.placeholder.inputPassword'),
            },
            fieldName: 'password',
            label: $t('tenant.system.user.password'),
            rules: 'required',
          },
        ]),
    inputField('phone', $t('tenant.system.user.phone'), {
      placeholder: $t('tenant.system.user.placeholder.inputPhone'),
    }),
    inputField('nickname', $t('tenant.system.user.nickname'), {
      placeholder: $t('tenant.system.user.placeholder.inputNickname'),
    }),
    {
      ...select('role_id', $t('tenant.system.user.role'), {
        options: [],
        placeholder: $t('tenant.system.user.placeholder.selectRole'),
      }),
      help: $t('tenant.system.user.help.roleHelp'),
    },
    switchField('is_active', $t('tenant.system.user.status'), {
      defaultValue: true,
    }),
  ];
}

export function getUserFormDefaults(): Record<string, unknown> {
  return {
    is_active: true,
  };
}
