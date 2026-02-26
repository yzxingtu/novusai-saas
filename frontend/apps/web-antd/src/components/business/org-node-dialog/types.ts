/**
 * 组织节点弹窗组件类型定义
 */
import type { OrgNodeType } from '#/api/admin/organization';

import { $t } from '#/locales';

/** 弹窗模式 */
export type DialogMode = 'create' | 'edit';

/** 节点表单数据 */
export interface OrgNodeFormData {
  /** 名称 */
  name: string;
  /** 描述 */
  description?: string;
  /** 节点类型 */
  type: OrgNodeType;
  /** 是否允许添加成员 */
  allowMembers: boolean;
  /** 是否启用 */
  isActive: boolean;
  /** 排序号 */
  sortOrder: number;
  /** 权限 ID 列表 */
  permissionIds: number[];
}

/** 节点弹窗 Props */
export interface OrgNodeDialogProps {
  /** 是否显示弹窗 */
  open?: boolean;
  /** 弹窗模式：创建/编辑 */
  mode?: DialogMode;
  /** 父节点 ID（创建时使用） */
  parentId?: null | number;
  /** 父节点类型（用于限制子节点类型） */
  parentType?: null | OrgNodeType;
  /** 父节点名称（显示用） */
  parentName?: string;
  /** 编辑的节点 ID */
  nodeId?: null | number;
  /** 编辑时的初始数据 */
  initialData?: Partial<OrgNodeFormData>;
  /** API 前缀 */
  apiPrefix?: 'admin' | 'tenant';
}

/** 节点弹窗 Emits */
export interface OrgNodeDialogEmits {
  (e: 'update:open', value: boolean): void;
  (e: 'success', node: { id: number; name: string; type: OrgNodeType }): void;
  (e: 'cancel'): void;
}

/** 节点类型选项 */
export interface NodeTypeOption {
  value: OrgNodeType;
  label: string;
  icon: string;
  description: string;
  /** 是否禁用 */
  disabled?: boolean;
}

/**
 * 根据父节点类型获取允许的子节点类型
 * 规则：
 * - 根节点（无父节点）：可创建 department, position, role
 * - department: 可创建 department, position
 * - position: 不能创建子节点
 * - role: 可创建 role
 */
export function getAllowedChildTypes(
  parentType: null | OrgNodeType | undefined,
): OrgNodeType[] {
  if (!parentType) {
    // 根节点可创建所有类型
    return ['department', 'position', 'role'];
  }

  switch (parentType) {
    case 'department': {
      // 部门可创建部门和岗位
      return ['department', 'position'];
    }
    case 'position': {
      // 岗位不能创建子节点
      return [];
    }
    case 'role': {
      // 角色只能创建角色
      return ['role'];
    }
    default: {
      return [];
    }
  }
}

/**
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
 * 获取节点类型的默认 allowMembers 值
 */
export function getDefaultAllowMembers(type: OrgNodeType): boolean {
  switch (type) {
    case 'department': {
      // 部门默认不允许直接添加成员
      return false;
    }
    case 'position': {
      // 岗位允许添加成员
      return true;
    }
    case 'role': {
      // 角色允许添加成员
      return true;
    }
    default: {
      return true;
    }
  }
}

/** 表单验证规则 */
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
