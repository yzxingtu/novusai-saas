/**
 * User architecture page - filters, role form, and user table config
 * 用户架构页面 - 筛选、权限角色表单与用户表格配置
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
import { checkboxColumn } from '#/adapter/vxe-table';
import { $t } from '#/locales';
import { usePresenceStore } from '#/store';

function getStatusOptions() {
  return [
    { label: $t('shared.status.active'), value: 'true' },
    { label: $t('shared.status.inactive'), value: 'false' },
  ];
}

function getApprovalStatusOptions() {
  return [
    { label: $t('tenant.system.user.approvalStatus.pending'), value: 'pending' },
    { label: $t('tenant.system.user.approvalStatus.approved'), value: 'approved' },
    { label: $t('tenant.system.user.approvalStatus.rejected'), value: 'rejected' },
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

export function useMemberColumns<T = TenantUserInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    checkboxColumn,
    {
      field: 'username',
      title: $t('tenant.system.user.username'),
      minWidth: 140,
      slots: { default: 'username_cell' },
    },
    {
      field: 'orgNodeName',
      title: $t('tenant.system.userArchitecture.orgColumn'),
      minWidth: 140,
      formatter: ({ row }: { row: TenantUserInfo }) =>
        row.orgNodeName || $t('tenant.system.userArchitecture.unassignedOrg'),
    },
    {
      field: 'roleName',
      title: $t('tenant.system.userArchitecture.permissionRoleColumn'),
      minWidth: 140,
      formatter: ({ row }: { row: TenantUserInfo }) =>
        row.roleName || $t('tenant.system.userArchitecture.unassignedPermissionRole'),
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
      field: 'approvalStatus',
      title: $t('tenant.system.user.approval'),
      width: 110,
      align: 'center',
      slots: { default: 'approval_cell' },
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
          {
            code: 'forceLogout',
            text: $t('common.auth.forceLogout'),
            icon: 'lucide:log-out',
            accessCodes: ['tenant_user:force_logout'],
            show: (row: TenantUserInfo) =>
              usePresenceStore().isOnline('tenant_user', row.id),
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
    select('filter[approval_status][eq]', $t('tenant.system.user.approval'), {
      options: getApprovalStatusOptions(),
      placeholder: $t('tenant.system.user.placeholder.allApprovalStatus'),
    }),
  ];
}

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
      component: 'TreeSelect',
      componentProps: {
        allowClear: true,
        class: 'w-full',
        placeholder: $t('tenant.system.userArchitecture.selectOrgPlaceholder'),
        showSearch: true,
        treeData: [],
        treeNodeFilterProp: 'label',
      },
      fieldName: 'org_node_id',
      label: $t('tenant.system.userArchitecture.orgField'),
      help: $t('tenant.system.userArchitecture.orgFieldHelp'),
    },
    {
      ...select('role_id', $t('tenant.system.userArchitecture.permissionRoleField'), {
        options: [],
        placeholder: $t('tenant.system.userArchitecture.selectPermissionRolePlaceholder'),
      }),
      help: $t('tenant.system.userArchitecture.permissionRoleHelp'),
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
