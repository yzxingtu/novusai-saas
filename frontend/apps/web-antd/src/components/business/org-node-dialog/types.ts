/**
 * Organization Node Dialog Component Type Definitions
 * 组织节点弹窗组件类型定义
 */
import type { OrgNodeType } from '#/api/admin/organization';

import { $t } from '#/locales';

export type DialogMode = 'create' | 'edit';

export type DataScopeType =
  | 'all'
  | 'custom'
  | 'dept_children'
  | 'dept_only'
  | 'self';

export interface OrgNodeFormData {
  name: string;
  description?: string;
  type: OrgNodeType;
  allowMembers: boolean;
  isActive: boolean;
  sortOrder: number;
  permissionIds: number[];
  dataScope: DataScopeType;
  customDeptIds: number[];
}

export interface OrgNodeDialogProps {
  open?: boolean;
  mode?: DialogMode;
  parentId?: null | number;
  parentType?: null | OrgNodeType;
  parentName?: string;
  nodeId?: null | number;
  initialData?: Partial<OrgNodeFormData>;
  apiPrefix?: 'admin' | 'tenant';
  canAssignPermissions?: boolean;
}

export interface OrgNodeDialogEmits {
  (e: 'update:open', value: boolean): void;
  (e: 'success', node: { id: number; name: string; type: OrgNodeType }): void;
  (e: 'cancel'): void;
}

export interface NodeTypeOption {
  value: OrgNodeType;
  label: string;
  icon: string;
  description: string;
  disabled?: boolean;
}

export interface LeaderScopeOption {
  value: DataScopeType;
  label: string;
  description: string;
}

export function getAllowedChildTypes(
  parentType: null | OrgNodeType | undefined,
): OrgNodeType[] {
  if (!parentType) {
    return ['department', 'position'];
  }

  switch (parentType) {
    case 'department': {
      return ['department', 'position'];
    }
    case 'position': {
      return [];
    }
    default: {
      return [];
    }
  }
}

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
  ];

  return allOptions.map((option) => ({
    ...option,
    disabled: !allowedTypes.includes(option.value),
  }));
}

export function getDefaultAllowMembers(type: OrgNodeType): boolean {
  switch (type) {
    case 'department': {
      return false;
    }
    case 'position': {
      return true;
    }
    default: {
      return true;
    }
  }
}

export function getLeaderScopeOptions(): LeaderScopeOption[] {
  return [
    {
      value: 'all',
      label: $t('shared.orgNode.scope.all'),
      description: $t('shared.orgNode.scope.allDesc'),
    },
    {
      value: 'dept_children',
      label: $t('shared.orgNode.scope.deptChildren'),
      description: $t('shared.orgNode.scope.deptChildrenDesc'),
    },
    {
      value: 'dept_only',
      label: $t('shared.orgNode.scope.deptOnly'),
      description: $t('shared.orgNode.scope.deptOnlyDesc'),
    },
    {
      value: 'self',
      label: $t('shared.orgNode.scope.self'),
      description: $t('shared.orgNode.scope.selfDesc'),
    },
    {
      value: 'custom',
      label: $t('shared.orgNode.scope.custom'),
      description: $t('shared.orgNode.scope.customDesc'),
    },
  ];
}

export function getLeaderScopeLabel(scope?: null | string): string {
  const option = getLeaderScopeOptions().find((item) => item.value === scope);
  return option?.label ?? $t('shared.orgNode.scope.unknown');
}

export function getLeaderScopeDescription(scope?: null | string): string {
  const option = getLeaderScopeOptions().find((item) => item.value === scope);
  return option?.description ?? $t('shared.orgNode.scope.unknownDesc');
}

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
