/**
 * PermissionSelector 组件类型定义
 * Permission Selector Component Type Definitions
 */
import type { Key } from 'ant-design-vue/es/_util/type';

/**
 * 权限类型
 * Permission Type
 */
export type PermissionType = 'api' | 'button' | 'menu';

/**
 * 权限来源类型
 * Permission Source Type
 */
export type PermissionSource = 'inherited' | 'own';

/**
 * 权限节点数据（原始）
 * Raw permission node data from backend
 */
export interface PermissionNodeRaw {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  parent_id: null | number;
  sort_order: number;
  /** 图标（Iconify 格式，如 lucide:gauge）
   * Icon (Iconify format, e.g. lucide:gauge)
   */
  icon?: null | string;
  children?: PermissionNodeRaw[];
}

/**
 * 权限节点数据（前端格式）
 * Processed permission node for frontend
 */
export interface PermissionNode {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  parentId: null | number;
  sortOrder: number;
  /** 图标（Iconify 格式，如 lucide:gauge）
   * Icon (Iconify format, e.g. lucide:gauge)
   */
  icon?: null | string;
  children?: PermissionNode[];
}

/**
 * 有效权限项（含继承信息）
 * Effective Permission Item (including inheritance information)
 */
export interface EffectivePermission {
  id: number;
  code: string;
  name: string;
  type: PermissionType;
  /** 权限来源：own=自有权限, inherited=继承权限
   * Permission source: own=self-owned permission, inherited=inherited permission
   */
  source: PermissionSource;
  /** 继承自的角色 ID（仅当 source='inherited' 时有值）
   * Inherited role ID (only available when source='inherited')
   */
  inheritedFromRoleId?: number;
  /** 继承自的角色名称
   * Inherited role name
   */
  inheritedFromRoleName?: string;
}

/**
 * Ant Design Vue Tree 节点数据
 * Ant Design Vue Tree Node Data
 */
export interface AntTreeNode {
  key: number;
  title: string;
  code: string;
  type: PermissionType;
  /** 图标（Iconify 格式）
   * Icon (Iconify format)
   */
  icon?: null | string;
  children?: AntTreeNode[];
  /** 是否为继承权限
   * Whether it is an inherited permission
   */
  isInherited?: boolean;
  /** 继承来源角色名称
   * Inherited source role name
   */
  inheritedFrom?: string;
  /** 是否禁用（继承权限不可取消）
   * Whether disabled (inherited permissions cannot be cancelled)
   */
  disabled?: boolean;
  /** 原始权限数据
   * Raw permission data
   */
  raw: PermissionNode;
}

/**
 * PermissionSelector 组件 Props
 * Permission Selector Component Props
 */
export interface PermissionSelectorProps {
  /**
   * 权限树数据
   * Permission tree data
   */
  permissions: PermissionNode[];

  /**
   * 选中的权限 ID 列表（v-model）
   * Selected permission ID list (v-model)
   */
  modelValue?: number[];

  /**
   * 继承的权限 ID 列表（灰色锁定显示）
   * Inherited permission ID list (gray lock display)
   */
  inheritedPermissionIds?: number[];

  /**
   * 继承权限的来源映射 Map<permissionId, roleName>
   * Inherited permission source mapping Map<permissionId, roleName>
   */
  inheritedFromMap?: Map<number, string>;

  /**
   * 加载状态
   * Loading state
   */
  loading?: boolean;

  /**
   * 是否显示继承标识
   * Whether to display the inheritance mark
   * @default true
   */
  showInheritedBadge?: boolean;

  /**
   * 默认展开层级
   * Default expansion level
   * @default 0
   */
  defaultExpandedLevel?: number;

  /**
   * 是否显示全选/取消按钮
   * Whether to display the select all/cancel button
   * @default true
   */
  showSelectAll?: boolean;
}

/**
 * PermissionSelector 组件 Emits
 * Permission Selector Component Emits
 */
/* eslint-disable @typescript-eslint/unified-signatures */
export interface PermissionSelectorEmits {
  (e: 'update:modelValue', value: number[]): void;
  (e: 'change', value: number[]): void;
}
/* eslint-enable @typescript-eslint/unified-signatures */

/**
 * 将权限树转换为 Ant Tree 格式
 * Convert permission tree to Ant Tree format
 */
export function transformToAntTreeData(
  nodes: PermissionNode[],
  inheritedIds: Set<number> = new Set(),
  inheritedFromMap: Map<number, string> = new Map(),
): AntTreeNode[] {
  return nodes.map((node) => {
    const isInherited = inheritedIds.has(node.id);
    return {
      key: node.id,
      title: node.name,
      code: node.code,
      type: node.type,
      icon: node.icon,
      isInherited,
      inheritedFrom: inheritedFromMap.get(node.id),
      disabled: isInherited,
      children: node.children
        ? transformToAntTreeData(node.children, inheritedIds, inheritedFromMap)
        : undefined,
      raw: node,
    };
  });
}

/**
 * 获取默认展开的 keys
 * Get default expanded keys
 */
export function getExpandedKeys(nodes: PermissionNode[], level: number): Key[] {
  if (level <= 0) return [];
  const keys: Key[] = [];
  for (const node of nodes) {
    keys.push(node.id);
    if (node.children && node.children.length > 0) {
      keys.push(...getExpandedKeys(node.children, level - 1));
    }
  }
  return keys;
}

/**
 * Get all permission IDs (for select all)
 * 获取所有权限 ID（用于全选）
 */
export function getAllPermissionIds(nodes: PermissionNode[]): number[] {
  const ids: number[] = [];
  for (const node of nodes) {
    ids.push(node.id);
    if (node.children && node.children.length > 0) {
      ids.push(...getAllPermissionIds(node.children));
    }
  }
  return ids;
}
