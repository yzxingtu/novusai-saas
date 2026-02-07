/**
 * 成员管理面板组件类型定义
 */
import type { AdminInfo } from '#/api/admin/admin-user';
import type { OrgMember } from '#/api/admin/organization';

/** 成员面板 Props */
export interface MemberPanelProps {
  /** 当前选中的节点 ID */
  nodeId?: null | number;
  /** 节点名称（用于显示标题） */
  nodeName?: string;
  /** 是否允许添加成员 */
  allowMembers?: boolean;
  /** 负责人 ID */
  leaderId?: null | number;
  /** API 前缀（admin 或 tenant） */
  apiPrefix?: 'admin' | 'tenant';
}

/** 成员面板 Emits */
export interface MemberPanelEmits {
  (e: 'memberAdded', member: OrgMember): void;
  (e: 'memberRemoved', memberId: number): void;
  (e: 'leaderChanged', leaderId: null | number): void;
  (e: 'refresh'): void;
}

/** 成员列表项 Props */
export interface MemberItemProps {
  /** 成员信息 */
  member: OrgMember;
  /** 是否为负责人 */
  isLeader?: boolean;
  /** 是否禁用操作 */
  disabled?: boolean;
  /** 是否显示操作按钮 */
  showActions?: boolean;
}

/** 成员列表项 Emits */
/* eslint-disable @typescript-eslint/unified-signatures */
export interface MemberItemEmits {
  (e: 'remove', member: OrgMember): void;
  (e: 'setLeader', member: OrgMember): void;
  (e: 'cancelLeader', member: OrgMember): void;
}
/* eslint-enable @typescript-eslint/unified-signatures */

/** 分页状态 */
export interface PaginationState {
  page: number;
  pageSize: number;
  total: number;
}

/** useMemberPanel hook 参数 */
export interface UseMemberPanelOptions {
  /** 节点 ID */
  nodeId: () => null | number | undefined;
  /** API 前缀 */
  apiPrefix?: 'admin' | 'tenant';
}

/** useMemberPanel hook 返回类型 */
export interface UseMemberPanelReturn {
  /** 成员列表 */
  members: import('vue').Ref<OrgMember[]>;
  /** 是否正在加载 */
  loading: import('vue').Ref<boolean>;
  /** 是否正在操作（添加/移除/设置负责人） */
  operating: import('vue').Ref<boolean>;
  /** 错误信息 */
  error: import('vue').Ref<null | string>;
  /** 分页状态 */
  pagination: import('vue').Ref<PaginationState>;
  /** 搜索关键词 */
  searchKeyword: import('vue').Ref<string>;
  /** 是否包含子节点成员（递归查询） */
  includeDescendants: import('vue').Ref<boolean>;
  /** 加载成员列表 */
  loadMembers: (resetPage?: boolean) => Promise<void>;
  /** 添加成员 */
  addMember: (adminId: number) => Promise<boolean>;
  /** 批量添加成员 */
  addMembers: (adminIds: number[]) => Promise<boolean>;
  /** 移除成员 */
  removeMember: (adminId: number, targetRoleId?: number) => Promise<boolean>;
  /** 设置负责人 */
  setLeader: (
    adminId: null | number,
    targetRoleId?: number,
  ) => Promise<boolean>;
  /** 刷新列表 */
  refresh: () => Promise<void>;
  /** 切换页码 */
  changePage: (page: number) => Promise<void>;
  /** 切换每页数量 */
  changePageSize: (pageSize: number) => Promise<void>;
  /** 搜索成员 */
  search: (keyword: string) => Promise<void>;
  /** 切换是否包含子节点成员 */
  toggleIncludeDescendants: (value: boolean) => Promise<void>;
}

/**
 * 提取用于重置密码弹窗所需的最小信息
 */
export function toResetPasswordInfo(member: OrgMember): {
  id: number;
  roleId?: number;
  username: string;
} {
  return {
    id: member.id,
    username: member.username,
    roleId: member.roleId,
  };
}

/**
 * 提取用于管理员编辑抽屉所需的信息
 */
export function toAdminInfo(member: OrgMember): AdminInfo {
  return {
    id: member.id,
    username: member.username,
    nickname: member.nickname,
    email: member.email,
    avatar: member.avatar,
    isActive: member.isActive,
    isSuper: false,
    roleId: member.roleId,
    roleName: member.roleName,
    createdAt: member.createdAt || '',
    updatedAt: member.updatedAt,
  };
}
