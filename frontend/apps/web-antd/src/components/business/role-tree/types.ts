/**
 * Role Tree Component Type Definitions
 * 角色树组件类型定义
 */

/** Role tree node data / 角色树节点数据 */
export interface RoleTreeNodeData {
  id: number;
  code: string;
  name: string;
  description?: null | string;
  isActive: boolean;
  sortOrder?: number;
  parentId?: null | number;
  permissionsCount?: number;
  createdAt?: null | string;
  children: RoleTreeNodeData[];
}

/** Level color configuration / 层级颜色配置 */
export interface LevelColorConfig {
  bar: string;
  badge: string;
}

/** Role tree component Props / 角色树组件 Props */
export interface RoleTreeProps {
  /** Tree data / 树形数据 */
  data: RoleTreeNodeData[];
  /** Loading state / 加载状态 */
  loading?: boolean;
  /** i18n prefix / i18n 前缀 */
  i18nPrefix?: 'admin' | 'tenant';
}

/** Role tree component Emits / 角色树组件 Emits */
/* eslint-disable @typescript-eslint/unified-signatures */
export interface RoleTreeEmits {
  (e: 'edit', row: RoleTreeNodeData): void;
  (e: 'addChild', row: RoleTreeNodeData): void;
  (e: 'delete', row: RoleTreeNodeData): void;
  (e: 'refresh'): void;
}
/* eslint-enable @typescript-eslint/unified-signatures */
