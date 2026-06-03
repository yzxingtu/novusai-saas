/**
 * Organization Tree Component
 * 组织树组件
 * @description Displays organization structure tree (department/position/role) / 用于展示组织架构树形结构（部门/岗位/角色）
 */

export { default as OrgTreeNode } from './OrgTreeNode.vue';
export type {
  ContextMenuAction,
  ContextMenuItem,
  LevelColorConfig,
  NodeTypeConfig,
  OrgTreeEmits,
  OrgTreeNodeData,
  OrgTreeProps,
  UseOrgTreeReturn,
} from './types';
export { NODE_TYPE_CONFIG } from './types';
export { useOrgTree } from './use-org-tree';
export type { UseOrgTreeOptions } from './use-org-tree';
