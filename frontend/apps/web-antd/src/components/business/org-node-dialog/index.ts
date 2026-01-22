/**
 * 组织节点弹窗组件
 * @description 用于创建和编辑组织架构节点（部门/岗位/角色）
 */

export { default as OrgNodeDialog } from './org-node-dialog.vue';
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
