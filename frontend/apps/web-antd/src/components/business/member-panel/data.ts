import type { AnyPromiseFunction } from '@vben/types';

/**
 * Member Management - Form Configuration
 * Follows vben-admin conventions, independent of specific view pages
 * 成员管理 - 表单配置
 * 遵循 vben-admin 规范，独立于具体视图页面
 */
import type { VbenFormSchema } from '#/adapter/form';

import { z } from '#/adapter/form';
import { $t } from '#/locales';

/** Role tree API type / 角色树 API 类型 */
export type RoleTreeApi = AnyPromiseFunction<any, any>;

/**
 * Admin create/edit form Schema
 * 管理员新建/编辑表单 Schema
 * @param options - Configuration options / 配置选项
 */
export function useAdminFormSchema(options: {
  /** Whether in edit mode / 是否编辑模式 */
  isEdit?: boolean;
  /** Current org node ID (for default selection) / 当前组织节点 ID（用于默认选中） */
  nodeId?: null | number;
  /** Org node name (for default display) / 组织节点名称（用于默认显示） */
  nodeName?: string;
  /** Role tree API (for role selection) / 角色树 API（可选择角色） */
  roleTreeApi?: RoleTreeApi;
}): VbenFormSchema[] {
  const { isEdit = false, nodeName, nodeId, roleTreeApi } = options;

  return [
    // === Basic Info / 基本信息 ===
    {
      component: 'Divider',
      componentProps: {
        orientation: 'left',
      },
      fieldName: 'divider_basic',
      label: '',
      renderComponentContent: () => ({
        default: () => $t('admin.common.basicInfo'),
      }),
    },
    {
      component: 'Input',
      componentProps: {
        disabled: isEdit,
        placeholder: $t('admin.system.admin.placeholder.inputUsername'),
      },
      fieldName: 'username',
      label: $t('admin.system.admin.username'),
      rules: isEdit ? undefined : 'required',
      help: isEdit
        ? $t('admin.system.admin.help.usernameEdit')
        : $t('admin.system.admin.help.usernameCreate'),
    },
    {
      component: 'Input',
      componentProps: {
        placeholder: $t('admin.system.admin.placeholder.inputNickname'),
      },
      fieldName: 'nickname',
      label: $t('admin.system.admin.nickname'),
    },
    // Password field only shown in create mode / 密码字段仅在新建模式显示
    ...(isEdit
      ? []
      : [
          {
            component: 'Input',
            componentProps: {
              placeholder: $t('admin.system.admin.placeholder.inputPassword'),
              type: 'password',
            },
            fieldName: 'password',
            label: $t('admin.system.admin.password'),
            rules: 'required',
          },
        ]),
    // === Contact Info / 联系方式 ===
    {
      component: 'Divider',
      componentProps: {
        orientation: 'left',
      },
      fieldName: 'divider_contact',
      label: '',
      renderComponentContent: () => ({
        default: () => $t('admin.common.contactInfo'),
      }),
    },
    {
      component: 'Input',
      componentProps: {
        placeholder: $t('admin.system.admin.placeholder.inputEmail'),
      },
      fieldName: 'email',
      label: $t('admin.system.admin.email'),
      rules: 'required',
    },
    {
      component: 'Input',
      componentProps: {
        placeholder: $t('admin.system.admin.placeholder.inputPhone'),
      },
      fieldName: 'phone',
      label: $t('admin.system.admin.phone'),
    },
    // === Permission Settings / 权限设置 ===
    {
      component: 'Divider',
      componentProps: {
        orientation: 'left',
      },
      fieldName: 'divider_permission',
      label: '',
      renderComponentContent: () => ({
        default: () => $t('admin.common.permissionSettings'),
      }),
    },
    // Role selection: if roleTreeApi provided, show selectable dropdown tree with current node selected; otherwise show read-only text
    // 角色选择：若提供 roleTreeApi，则显示可选下拉树，默认选中当前节点；否则显示只读文本
    ...(roleTreeApi
      ? [
          {
            component: 'ApiTreeSelect',
            componentProps: {
              api: roleTreeApi,
              childrenField: 'children',
              labelField: 'name',
              valueField: 'id',
              placeholder: $t('admin.system.admin.placeholder.selectRole'),
              showSearch: true,
              treeNodeFilterProp: 'name',
              treeDefaultExpandAll: true,
              allowClear: true,
              style: { width: '100%' },
            },
            fieldName: 'role_id',
            label: $t('admin.system.admin.role'),
            rules: 'required',
            defaultValue: nodeId ?? undefined,
          },
        ]
      : nodeName
        ? [
            {
              component: 'Input',
              componentProps: {
                disabled: true,
              },
              fieldName: 'role_display',
              label: $t('admin.system.admin.role'),
              defaultValue: nodeName,
              help: $t('admin.system.admin.help.roleAutoBinding'),
            },
          ]
        : []),
    {
      component: 'RadioGroup',
      componentProps: {
        buttonStyle: 'solid',
        optionType: 'button',
        options: [
          { label: $t('admin.common.enabled'), value: true },
          { label: $t('admin.common.disabled'), value: false },
        ],
      },
      defaultValue: true,
      fieldName: 'is_active',
      label: $t('admin.common.accountStatus'),
    },
  ];
}

/**
 * Admin form default values (create mode)
 * 管理员表单默认值（新建模式）
 * @param nodeName - Org node name / 组织节点名称
 * @param nodeId - Org node ID (for default role selection) / 组织节点 ID（用于默认选中角色）
 */
export function getAdminFormDefaults(
  nodeName?: string,
  nodeId?: null | number,
): Record<string, any> {
  return {
    is_active: true,
    role_display: nodeName || $t('admin.common.notSelected'),
    role_id: nodeId ?? undefined,
  };
}

/**
 * Reset Password Form Schema
 * Password consistency validation implemented via Zod dependencies
 * 重置密码表单 Schema
 * 密码一致性校验通过 Zod dependencies 实现
 */
export function useResetPasswordSchema(): VbenFormSchema[] {
  return [
    {
      component: 'InputPassword',
      componentProps: {
        placeholder: $t('admin.system.admin.placeholder.inputNewPassword'),
      },
      fieldName: 'new_password',
      label: $t('admin.system.admin.newPassword'),
      rules: z.string().min(6, $t('admin.system.admin.validation.passwordMin')),
    },
    {
      component: 'InputPassword',
      componentProps: {
        placeholder: $t('admin.system.admin.placeholder.confirmPassword'),
      },
      fieldName: 'confirm_password',
      label: $t('admin.system.admin.confirmPassword'),
      dependencies: {
        triggerFields: ['new_password'],
        rules: (values) =>
          z
            .string()
            .min(1, $t('admin.system.admin.validation.confirmRequired'))
            .refine((v) => v === values.new_password, {
              message: $t('admin.system.admin.messages.passwordMismatch'),
            }),
      },
    },
  ];
}
