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

/** Org tree API type / 组织树 API 类型 */
export type OrgTreeApi = AnyPromiseFunction<any, any>;
export interface MemberRoleOption {
  label: string;
  value: number;
}

/**
 * Admin create/edit form Schema
 * 管理员新建/编辑表单 Schema
 * @param options - Configuration options / 配置选项
 * @param options.apiPrefix - API prefix / API 前缀
 * @param options.isEdit - Whether in edit mode / 是否编辑模式
 * @param options.nodeId - Current org node ID / 当前组织节点 ID
 * @param options.nodeName - Org node name / 组织节点名称
 * @param options.orgTreeApi - Org tree API / 组织树 API
 * @param options.roleOptions - Permission role options / 权限角色选项
 */
export function useAdminFormSchema(options: {
  /** API prefix / API 前缀 */
  apiPrefix?: 'admin' | 'tenant';
  /** Whether current operator can manage account AI availability / 是否可管理账号 AI 对话开关 */
  canManageAi?: boolean;
  /** Whether in edit mode / 是否编辑模式 */
  isEdit?: boolean;
  /** Whether to lock assignment to the current node (create mode) / 是否在新建时锁定组织节点 */
  lockOrgNode?: boolean;
  /** Current org node ID (for default selection) / 当前组织节点 ID（用于默认选中） */
  nodeId?: null | number;
  /** Org node name (for default display) / 组织节点名称（用于默认显示） */
  nodeName?: string;
  /** Org node change hook / 组织节点变更回调 */
  onOrgNodeChange?: (value: unknown) => void;
  /** Org tree API (for node selection) / 组织树 API（可选择节点） */
  orgTreeApi?: OrgTreeApi;
  /** Permission role options / 权限角色选项 */
  roleOptions?: MemberRoleOption[];
}): VbenFormSchema[] {
  const {
    apiPrefix = 'admin',
    canManageAi = false,
    isEdit = false,
    nodeName,
    nodeId,
    orgTreeApi,
    onOrgNodeChange,
    lockOrgNode = false,
    roleOptions = [],
  } = options;
  let assignmentFields: VbenFormSchema[] = [];
  const treeApi = lockOrgNode ? undefined : orgTreeApi;

  if (treeApi) {
    assignmentFields = [
      {
        component: 'ApiTreeSelect',
        componentProps: {
          api: treeApi,
          childrenField: 'children',
          labelField: 'name',
          valueField: 'id',
          placeholder: $t('shared.memberPanel.selectOrgNode'),
          showSearch: true,
          treeNodeFilterProp: 'name',
          treeDefaultExpandAll: true,
          allowClear: true,
          onChange: onOrgNodeChange,
          style: { width: '100%' },
        },
        fieldName: 'org_node_id',
        label: $t('shared.memberPanel.orgNode'),
        rules: 'required',
        defaultValue: nodeId ?? undefined,
      },
    ];
  } else if (nodeName) {
    assignmentFields = [
      {
        component: 'Input',
        componentProps: {
          disabled: true,
        },
        fieldName: 'org_node_display',
        label: $t('shared.memberPanel.orgNode'),
        defaultValue: nodeName || $t('shared.common.notAssigned'),
        help: $t('shared.memberPanel.orgNodeBound'),
      },
    ];
  }

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
    // === Organization Assignment / 组织归属 ===
    {
      component: 'Divider',
      componentProps: {
        orientation: 'left',
      },
      fieldName: 'divider_assignment',
      label: '',
      renderComponentContent: () => ({
        default: () => $t('shared.memberPanel.assignmentTitle'),
      }),
    },
    ...assignmentFields,
    ...(apiPrefix === 'tenant'
      ? [
          {
            component: 'Select',
            componentProps: {
              allowClear: true,
              options: roleOptions,
              optionFilterProp: 'label',
              placeholder: $t('shared.memberPanel.selectPermissionRole'),
              showSearch: true,
              style: { width: '100%' },
            },
            fieldName: 'role_id',
            label: $t('shared.memberPanel.permissionRole'),
            help: $t('shared.memberPanel.permissionRoleHelp'),
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
    {
      component: 'Switch',
      componentProps: {
        checkedChildren: $t('shared.common.enabled'),
        disabled: !canManageAi,
        unCheckedChildren: $t('shared.common.disabled'),
      },
      defaultValue: true,
      fieldName: 'ai_enabled',
      label: $t('shared.memberPanel.aiConversation'),
      help: canManageAi ? undefined : $t('shared.memberPanel.aiReadonlyHelp'),
    },
  ];
}

/**
 * Admin form default values (create mode)
 * 管理员表单默认值（新建模式）
 * @param apiPrefix - API prefix / API 前缀
 * @param nodeName - Org node name / 组织节点名称
 * @param nodeId - Org node ID (for default selection) / 组织节点 ID（用于默认选中）
 */
export function getAdminFormDefaults(
  apiPrefix: 'admin' | 'tenant' = 'admin',
  nodeName?: string,
  nodeId?: null | number,
): Record<string, unknown> {
  return {
    is_active: true,
    ai_enabled: true,
    org_node_display: nodeName || $t('shared.common.notAssigned'),
    org_node_id: nodeId ?? undefined,
    ...(apiPrefix === 'tenant' ? { role_id: undefined } : {}),
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
