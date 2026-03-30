/**
 * Member Management Panel Component Type Definitions
 * 成员管理面板组件类型定义
 */
import type { OrgMember } from '#/api/admin/organization';
import type { TenantOrgMember } from '#/api/tenant/organization';

export type MemberPanelMember = OrgMember | TenantOrgMember;

/** Member Panel Props / 成员面板 Props */
export interface MemberPanelProps {
  /** Currently selected node ID / 当前选中的节点 ID */
  nodeId?: null | number;
  /** Node name (for displaying title) / 节点名称（用于显示标题） */
  nodeName?: string;
  /** Whether adding members is allowed / 是否允许添加成员 */
  allowMembers?: boolean;
  /** Leader ID / 负责人 ID */
  leaderId?: null | number;
  /** API prefix (admin or tenant) / API 前缀（admin 或 tenant） */
  apiPrefix?: 'admin' | 'tenant';
}

/** Member Panel Emits / 成员面板 Emits */
export interface MemberPanelEmits {
  (e: 'memberAdded', member: MemberPanelMember): void;
  (e: 'memberRemoved', memberId: number): void;
  (e: 'leaderChanged', leaderId: null | number): void;
  (e: 'refresh'): void;
}

/** Member List Item Props / 成员列表项 Props */
export interface MemberItemProps {
  /** Member info / 成员信息 */
  member: MemberPanelMember;
  /** Whether this member is the leader / 是否为负责人 */
  isLeader?: boolean;
  /** Whether actions are disabled / 是否禁用操作 */
  disabled?: boolean;
  /** Whether to show action buttons / 是否显示操作按钮 */
  showActions?: boolean;
}

/** Member List Item Emits / 成员列表项 Emits */
/* eslint-disable @typescript-eslint/unified-signatures */
export interface MemberItemEmits {
  (e: 'remove', member: MemberPanelMember): void;
  (e: 'setLeader', member: MemberPanelMember): void;
  (e: 'cancelLeader', member: MemberPanelMember): void;
}
/* eslint-enable @typescript-eslint/unified-signatures */

/** Pagination state / 分页状态 */
export interface PaginationState {
  page: number;
  pageSize: number;
  total: number;
}

/** useMemberPanel hook options / useMemberPanel hook 参数 */
export interface UseMemberPanelOptions {
  /** Node ID / 节点 ID */
  nodeId: () => null | number | undefined;
  /** API prefix / API 前缀 */
  apiPrefix?: 'admin' | 'tenant';
}

/** useMemberPanel hook return type / useMemberPanel hook 返回类型 */
export interface UseMemberPanelReturn {
  /** Member list / 成员列表 */
  members: import('vue').Ref<MemberPanelMember[]>;
  /** Whether loading / 是否正在加载 */
  loading: import('vue').Ref<boolean>;
  /** Whether operating (add/remove/set leader) / 是否正在操作（添加/移除/设置负责人） */
  operating: import('vue').Ref<boolean>;
  /** Error message / 错误信息 */
  error: import('vue').Ref<null | string>;
  /** Pagination state / 分页状态 */
  pagination: import('vue').Ref<PaginationState>;
  /** Search keyword / 搜索关键词 */
  searchKeyword: import('vue').Ref<string>;
  /** Whether to include descendant node members (recursive query) / 是否包含子节点成员（递归查询） */
  includeDescendants: import('vue').Ref<boolean>;
  /** Load member list / 加载成员列表 */
  loadMembers: (resetPage?: boolean) => Promise<void>;
  /** Add a member / 添加成员 */
  addMember: (adminId: number) => Promise<boolean>;
  /** Batch add members / 批量添加成员 */
  addMembers: (adminIds: number[]) => Promise<boolean>;
  /** Remove a member / 移除成员 */
  removeMember: (adminId: number, targetOrgNodeId?: number) => Promise<boolean>;
  /** Set leader / 设置负责人 */
  setLeader: (
    adminId: null | number,
    targetOrgNodeId?: number,
  ) => Promise<boolean>;
  /** Refresh list / 刷新列表 */
  refresh: () => Promise<void>;
  /** Change page / 切换页码 */
  changePage: (page: number) => Promise<void>;
  /** Change page size / 切换每页数量 */
  changePageSize: (pageSize: number) => Promise<void>;
  /** Search members / 搜索成员 */
  search: (keyword: string) => Promise<void>;
  /** Toggle include descendant members / 切换是否包含子节点成员 */
  toggleIncludeDescendants: (value: boolean) => Promise<void>;
}

/**
 * Extract minimal info needed for reset password dialog
 * 提取用于重置密码弹窗所需的最小信息
 */
export function toResetPasswordInfo(member: MemberPanelMember): {
  id: number;
  orgNodeId?: null | number;
  username: string;
} {
  return {
    id: member.id,
    username: member.username,
    orgNodeId: member.orgNodeId,
  };
}

