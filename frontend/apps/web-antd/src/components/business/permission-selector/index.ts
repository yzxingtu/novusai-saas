/**
 * Permission Selector Component
 * 权限选择器组件
 * @description For selecting and displaying permissions in organization structure / 用于组织架构中选择和展示权限
 */

export { default as PermissionSelector } from './PermissionSelector.vue';
export type {
  AntTreeNode,
  EffectivePermission,
  PermissionNode,
  PermissionNodeRaw,
  PermissionSelectorEmits,
  PermissionSelectorProps,
  PermissionSource,
  PermissionType,
} from './types';
export {
  getAllPermissionIds,
  getExpandedKeys,
  transformToAntTreeData,
} from './types';
