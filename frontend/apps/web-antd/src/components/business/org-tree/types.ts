/**
 * Organization Tree Component Type Definitions
 * 组织树组件类型定义
 */
import type { OrgNodeInfo, OrgNodeType } from '#/api/admin/organization';

/** Organization tree node data (extends OrgNodeInfo) / 组织架构树节点数据（扩展 OrgNodeInfo） */
export interface OrgTreeNodeData extends OrgNodeInfo {
  /** Child nodes (dynamically filled during lazy loading) / 子节点（懒加载时动态填充） */
  children: OrgTreeNodeData[];
  /** Whether loading child nodes / 是否正在加载子节点 */
  loading?: boolean;
  /** Whether child nodes have been loaded / 是否已加载子节点 */
  loaded?: boolean;
}

/** Node type configuration / 节点类型配置 */
export interface NodeTypeConfig {
  /** Label / 标签 */
  label: string;
  /** Icon / 图标 */
  icon: string;
  /** Background color / 背景色 */
  bgColor: string;
  /** Text color / 文本色 */
  textColor: string;
}

/** Node type configuration mapping / 节点类型配置映射 */
export const NODE_TYPE_CONFIG: Record<OrgNodeType, NodeTypeConfig> = {
  department: {
    icon: 'lucide:building-2',
    label: 'organization.nodeType.department',
    bgColor: 'blue',
    textColor: 'white',
  },
  position: {
    icon: 'lucide:briefcase',
    label: 'organization.nodeType.position',
    bgColor: 'purple',
    textColor: 'white',
  },
  role: {
    icon: 'lucide:shield',
    label: 'organization.nodeType.role',
    bgColor: 'green',
    textColor: 'white',
  },
};

/** Level color configuration / 层级颜色配置 */
export interface LevelColorConfig {
  bar: string;
  badge: string;
}

/** Context menu action / 上下文菜单操作 */
export type ContextMenuAction =
  | 'addDepartment'
  | 'addPosition'
  | 'addRole'
  | 'delete'
  | 'edit'
  | 'move'
  | 'setLeader'
  | 'viewMembers';

/** Context menu item / 上下文菜单项 */
export interface ContextMenuItem {
  /** Action type / 操作类型 */
  action: ContextMenuAction;
  /** Display text / 显示文本 */
  label: string;
  /** Icon / 图标 */
  icon: string;
  /** Whether it is a dangerous action / 是否危险操作 */
  danger?: boolean;
  /** Whether disabled / 是否禁用 */
  disabled?: boolean;
  /** Disabled tooltip / 禁用提示 */
  disabledTip?: string;
  /** Whether visible (determined by node type) / 是否显示（根据节点类型判断） */
  visible?: (node: OrgTreeNodeData) => boolean;
}

/** Organization tree Props / 组织树 Props */
export interface OrgTreeProps {
  /** Currently selected node ID / 当前选中的节点 ID */
  selectedNodeId?: null | number;
  /** Whether in readonly mode (disables context menu) / 是否只读模式（禁用右键菜单） */
  readonly?: boolean;
  /** API prefix (admin or tenant) / API 前缀（admin 或 tenant） */
  apiPrefix?: 'admin' | 'tenant';
  /** Whether to show context menu / 是否显示右键菜单 */
  showContextMenu?: boolean;
  /** Whether to support drag-and-drop sorting / 是否支持拖拽排序 */
  draggable?: boolean;
  /** i18n prefix / i18n 前缀 */
  i18nPrefix?: 'admin' | 'tenant';
}

/** Organization tree Emits / 组织树 Emits */
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

/** useOrgTree return type / useOrgTree 返回类型 */
export interface UseOrgTreeReturn {
  /** Tree node data / 树节点数据 */
  treeData: import('vue').ShallowRef<OrgTreeNodeData[]>;
  /** Whether loading root nodes / 是否正在加载根节点 */
  loading: import('vue').Ref<boolean>;
  /** Currently expanded node IDs / 当前展开的节点 ID 集合 */
  expandedIds: import('vue').Ref<Set<number>>;
  /** Load root nodes / 加载根节点 */
  loadRootNodes: () => Promise<null | OrgTreeNodeData>;
  /** Load child nodes / 加载子节点 */
  loadChildren: (nodeId: number) => Promise<void>;
  /** Toggle node expand/collapse / 切换节点展开/收起 */
  toggleExpand: (nodeId: number) => Promise<void>;
  /** Expand all loaded nodes / 展开所有已加载的节点 */
  expandAll: () => void;
  /** Collapse all nodes / 收起所有节点 */
  collapseAll: () => void;
  /** Check if a node is expanded / 检查节点是否展开 */
  isExpanded: (nodeId: number) => boolean;
  /** Refresh entire tree / 刷新整棵树 */
  refresh: () => Promise<null | OrgTreeNodeData>;
  /** Update a single node's data / 更新单个节点数据 */
  updateNode: (nodeId: number, data: Partial<OrgTreeNodeData>) => void;
  /** Remove a node / 删除节点 */
  removeNode: (nodeId: number) => void;
  /** Add a node / 添加节点 */
  addNode: (parentId: null | number, node: OrgTreeNodeData) => void;
}
