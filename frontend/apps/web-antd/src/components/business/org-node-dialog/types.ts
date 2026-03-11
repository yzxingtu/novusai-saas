/**
 * Organization Node Dialog Component Type Definitions
 * 组织节点弹窗组件类型定义
 */
import type { OrgNodeType } from '#/api/admin/organization';

import { $t } from '#/locales';

/** Dialog mode / 弹窗模式 */
export type DialogMode = 'create' | 'edit';

/** Node form data / 节点表单数据 */
export interface OrgNodeFormData {
  /** Name / 名称 */
  name: string;
  /** Description / 描述 */
  description?: string;
  /** Node type / 节点类型 */
  type: OrgNodeType;
  /** Whether adding members is allowed / 是否允许添加成员 */
  allowMembers: boolean;
  /** Whether enabled / 是否启用 */
  isActive: boolean;
  /** Sort order / 排序号 */
  sortOrder: number;
  /** Permission ID list / 权限 ID 列表 */
  permissionIds: number[];
}

/** Node Dialog Props / 节点弹窗 Props */
export interface OrgNodeDialogProps {
  /** Whether to show dialog / 是否显示弹窗 */
  open?: boolean;
  /** Dialog mode: create/edit / 弹窗模式：创建/编辑 */
  mode?: DialogMode;
  /** Parent node ID (used when creating) / 父节点 ID（创建时使用） */
  parentId?: null | number;
  /** Parent node type (for restricting child node types) / 父节点类型（用于限制子节点类型） */
  parentType?: null | OrgNodeType;
  /** Parent node name (for display) / 父节点名称（显示用） */
  parentName?: string;
  /** Node ID being edited / 编辑的节点 ID */
  nodeId?: null | number;
  /** Initial data when editing / 编辑时的初始数据 */
  initialData?: Partial<OrgNodeFormData>;
  /** API prefix / API 前缀 */
  apiPrefix?: 'admin' | 'tenant';
}

/** Node Dialog Emits / 节点弹窗 Emits */
export interface OrgNodeDialogEmits {
  (e: 'update:open', value: boolean): void;
  (e: 'success', node: { id: number; name: string; type: OrgNodeType }): void;
  (e: 'cancel'): void;
}

/** Node type option / 节点类型选项 */
export interface NodeTypeOption {
  value: OrgNodeType;
  label: string;
  icon: string;
  description: string;
  /** Whether disabled / 是否禁用 */
  disabled?: boolean;
}

/**
 * Get allowed child node types based on parent node type
 * 根据父节点类型获取允许的子节点类型
 * Rules / 规则：
 * - Root node (no parent): can create department, position, role / 根节点（无父节点）：可创建 department, position, role
 * - department: can create department, position / 可创建 department, position
 * - position: cannot create child nodes / 不能创建子节点
 * - role: can create role / 可创建 role
 */
export function getAllowedChildTypes(
  parentType: null | OrgNodeType | undefined,
): OrgNodeType[] {
  if (!parentType) {
    // Root node can create all types / 根节点可创建所有类型
    return ['department', 'position', 'role'];
  }

  switch (parentType) {
    case 'department': {
      // Department can create departments and positions / 部门可创建部门和岗位
      return ['department', 'position'];
    }
    case 'position': {
      // Position cannot create child nodes / 岗位不能创建子节点
      return [];
    }
    case 'role': {
      // Role can only create roles / 角色只能创建角色
      return ['role'];
    }
    default: {
      return [];
    }
  }
}

/**
 * Get node type options list
 * 获取节点类型选项列表
 */
export function getNodeTypeOptions(
  allowedTypes: OrgNodeType[],
): NodeTypeOption[] {
  const allOptions: NodeTypeOption[] = [
    {
      value: 'department',
      label: $t('shared.orgNode.type.department'),
      icon: 'lucide:building-2',
      description: $t('shared.orgNode.type.departmentDesc'),
    },
    {
      value: 'position',
      label: $t('shared.orgNode.type.position'),
      icon: 'lucide:briefcase',
      description: $t('shared.orgNode.type.positionDesc'),
    },
    {
      value: 'role',
      label: $t('shared.orgNode.type.role'),
      icon: 'lucide:shield',
      description: $t('shared.orgNode.type.roleDesc'),
    },
  ];

  return allOptions.map((option) => ({
    ...option,
    disabled: !allowedTypes.includes(option.value),
  }));
}

/**
 * Get default allowMembers value for a node type
 * 获取节点类型的默认 allowMembers 值
 */
export function getDefaultAllowMembers(type: OrgNodeType): boolean {
  switch (type) {
    case 'department': {
      // Department: do not allow adding members directly by default / 部门默认不允许直接添加成员
      return false;
    }
    case 'position': {
      // Position: allows adding members / 岗位允许添加成员
      return true;
    }
    case 'role': {
      // Role: allows adding members / 角色允许添加成员
      return true;
    }
    default: {
      return true;
    }
  }
}

/** Form validation rules / 表单验证规则 */
export const formRules = {
  name: [
    {
      required: true,
      message: $t('shared.orgNode.validation.nameRequired'),
      trigger: 'blur' as const,
      type: 'string' as const,
    },
    {
      max: 50,
      message: $t('shared.orgNode.validation.nameMaxLength'),
      trigger: 'blur' as const,
      type: 'string' as const,
    },
  ],
  type: [
    {
      required: true,
      message: $t('shared.orgNode.validation.typeRequired'),
      trigger: 'change' as const,
      type: 'string' as const,
    },
  ],
  sortOrder: [
    {
      required: true,
      message: $t('shared.orgNode.validation.sortOrderRequired'),
      trigger: 'blur' as const,
      type: 'number' as const,
    },
    {
      type: 'number' as const,
      min: 0,
      max: 9999,
      message: $t('shared.orgNode.validation.sortOrderRange'),
      trigger: 'blur' as const,
    },
  ],
};
