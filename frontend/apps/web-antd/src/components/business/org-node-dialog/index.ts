/**
 * Organization Node Dialog Component
 * 组织节点弹窗组件
 * @description For creating and editing organization structure nodes (department/position/role) / 用于创建和编辑组织架构节点（部门/岗位/角色）
 */

export { default as OrgNodeDialog } from './OrgNodeDialog.vue';
export type {
  DialogMode,
  NodeTypeOption,
  OrgNodeDialogEmits,
  OrgNodeDialogProps,
  OrgNodeFormData,
} from './types';
export {
  formRules,
  getAllowedChildTypes,
  getDefaultAllowMembers,
  getNodeTypeOptions,
} from './types';
