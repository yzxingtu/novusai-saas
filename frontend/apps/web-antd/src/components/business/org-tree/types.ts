/**
 * 组织架构树组件类型定义
 */
import type { OrgNodeInfo, OrgNodeType } from '#/api/admin/organization';

/** 组织架构树节点数据（扩展 OrgNodeInfo） */
export interface OrgTreeNodeData extends OrgNodeInfo {
  /** 子节点（懒加载时动态填充） */
  children: OrgTreeNodeData[];
  /** 是否正在加载子节点 */
  loading?: boolean;
  /** 是否已加载子节点 */
  loaded?: boolean;
}

/** 节点类型配置 */
export interface NodeTypeConfig {
  /** 图标 */
  icon: string;
  /** 标签文本 key */
  label: string;
  /** 颜色主题 */
  color: string;
}

/** 节点类型配置映射 */
export const NODE_TYPE_CONFIG: Record<OrgNodeType, NodeTypeConfig> = {
  department: {
    icon: 'lucide:building-2',
    label: 'organization.nodeType.department',
    color: 'blue',
  },
  position: {
    icon: 'lucide:briefcase',
    label: 'organization.nodeType.position',
    color: 'purple',
  },
  role: {
    icon: 'lucide:shield',
    label: 'organization.nodeType.role',
    color: 'green',
  },
};

/** 层级颜色配置 */
export interface LevelColorConfig {
  bar: string;
  badge: string;
}

/** 右键菜单操作类型 */
export type ContextMenuAction =
  | 'addDepartment'
  | 'addPosition'
  | 'addRole'
  | 'delete'
  | 'edit'
  | 'move'
  | 'setLeader'
  | 'viewMembers';

/** 右键菜单项 */
export interface ContextMenuItem {
  key: ContextMenuAction;
  label: string;
  icon: string;
  danger?: boolean;
  /** 是否显示（根据节点类型判断） */
  visible?: (node: OrgTreeNodeData) => boolean;
}

/** 组织架构树组件 Props */
export interface OrgTreeProps {
  /** API 前缀（admin 或 tenant） */
  apiPrefix?: 'admin' | 'tenant';
  /** 是否显示右键菜单 */
  showContextMenu?: boolean;
  /** 是否支持拖拽排序 */
  draggable?: boolean;
  /** 选中的节点 ID */
  selectedId?: null | number;
  /** i18n 前缀 */
  i18nPrefix?: 'admin' | 'tenant';
}

/** 组织架构树组件 Emits */
/* eslint-disable @typescript-eslint/unified-signatures */
export interface OrgTreeEmits {
  (e: 'select', node: OrgTreeNodeData): void;
  (e: 'edit', node: OrgTreeNodeData): void;
  (e: 'delete', node: OrgTreeNodeData): void;
  (e: 'addChild', node: OrgTreeNodeData, type: OrgNodeType): void;
  (e: 'setLeader', node: OrgTreeNodeData): void;
  (e: 'viewMembers', node: OrgTreeNodeData): void;
  (e: 'move', node: OrgTreeNodeData, newParentId: null | number): void;
  (e: 'refresh'): void;
}
/* eslint-enable @typescript-eslint/unified-signatures */

/** useOrgTree hook 返回类型 */
export interface UseOrgTreeReturn {
  /** 树形数据 */
  treeData: import('vue').ShallowRef<OrgTreeNodeData[]>;
  /** 根节点加载状态 */
  loading: import('vue').Ref<boolean>;
  /** 展开的节点 ID 集合 */
  expandedIds: import('vue').Ref<Set<number>>;
  /** 加载根节点，返回第一个根节点（用于自动选择） */
  loadRootNodes: () => Promise<null | OrgTreeNodeData>;
  /** 加载子节点 */
  loadChildren: (nodeId: number) => Promise<void>;
  /** 切换展开状态 */
  toggleExpand: (nodeId: number) => Promise<void>;
  /** 展开所有已加载节点 */
  expandAll: () => void;
  /** 收起所有节点 */
  collapseAll: () => void;
  /** 检查节点是否展开 */
  isExpanded: (nodeId: number) => boolean;
  /** 刷新数据，返回第一个根节点 */
  refresh: () => Promise<null | OrgTreeNodeData>;
  /** 更新单个节点数据 */
  updateNode: (nodeId: number, data: Partial<OrgTreeNodeData>) => void;
  /** 删除节点 */
  removeNode: (nodeId: number) => void;
  /** 添加节点 */
  addNode: (parentId: null | number, node: OrgTreeNodeData) => void;
}
