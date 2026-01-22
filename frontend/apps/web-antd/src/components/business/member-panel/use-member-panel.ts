import type { UseMemberPanelOptions, UseMemberPanelReturn } from './types';

/**
 * 成员面板业务逻辑 composable
 */
import type { MemberListParams, OrgMember } from '#/api/admin/organization';
import type { TenantMemberListParams } from '#/api/tenant/organization';

import { ref, watch } from 'vue';

import { message } from 'ant-design-vue';

// Admin API
import {
  addMemberToNodeApi as adminAddMemberApi,
  getNodeMembersApi as adminGetMembersApi,
  removeMemberFromNodeApi as adminRemoveMemberApi,
  setNodeLeaderApi as adminSetLeaderApi,
} from '#/api/admin/organization';
// Tenant API
import {
  addTenantMemberToNodeApi as tenantAddMemberApi,
  getTenantNodeMembersApi as tenantGetMembersApi,
  removeTenantMemberFromNodeApi as tenantRemoveMemberApi,
  setTenantNodeLeaderApi as tenantSetLeaderApi,
} from '#/api/tenant/organization';

/** 默认每页数量 */
const DEFAULT_PAGE_SIZE = 20;

/**
 * 成员面板管理 hook
 * 支持 admin 和 tenant 两种 API 前缀
 */
export function useMemberPanel(
  options: UseMemberPanelOptions,
): UseMemberPanelReturn {
  const { nodeId, apiPrefix = 'admin' } = options;

  // 状态
  const members = ref<OrgMember[]>([]);
  const loading = ref(false);
  const operating = ref(false);
  const error = ref<null | string>(null);

  // 分页状态
  const pagination = ref({
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    total: 0,
  });

  // 搜索关键词
  const searchKeyword = ref('');

  // 是否包含子节点成员（递归查询）
  const includeDescendants = ref(true);

  // 根据前缀选择 API
  const getMembersApi =
    apiPrefix === 'tenant' ? tenantGetMembersApi : adminGetMembersApi;
  const addMemberApi =
    apiPrefix === 'tenant' ? tenantAddMemberApi : adminAddMemberApi;
  const removeMemberApi =
    apiPrefix === 'tenant' ? tenantRemoveMemberApi : adminRemoveMemberApi;
  const setLeaderApi =
    apiPrefix === 'tenant' ? tenantSetLeaderApi : adminSetLeaderApi;

  /**
   * 加载成员列表
   * @param resetPage - 是否重置到第一页
   */
  async function loadMembers(resetPage = false): Promise<void> {
    const id = nodeId();
    if (!id) {
      members.value = [];
      pagination.value.total = 0;
      return;
    }

    if (resetPage) {
      pagination.value.page = 1;
    }

    loading.value = true;
    error.value = null;

    try {
      const params: MemberListParams | TenantMemberListParams = {
        page: pagination.value.page,
        pageSize: pagination.value.pageSize,
        includeDescendants: includeDescendants.value,
      };
      if (searchKeyword.value.trim()) {
        params.search = searchKeyword.value.trim();
      }

      const response = await getMembersApi(id, params);
      members.value = response.items;
      pagination.value.total = response.total;
      pagination.value.page = response.page;
    } catch (error_) {
      console.error('Failed to load members:', error_);
      error.value = '加载成员列表失败';
      members.value = [];
      pagination.value.total = 0;
    } finally {
      loading.value = false;
    }
  }

  /**
   * 添加单个成员
   */
  async function addMember(adminId: number): Promise<boolean> {
    const id = nodeId();
    if (!id) {
      message.error('请先选择节点');
      return false;
    }

    operating.value = true;
    try {
      await addMemberApi(id, adminId);
      message.success('成员添加成功');
      await loadMembers();
      return true;
    } catch (error_) {
      console.error('Failed to add member:', error_);
      message.error('添加成员失败');
      return false;
    } finally {
      operating.value = false;
    }
  }

  /**
   * 批量添加成员
   */
  async function addMembers(adminIds: number[]): Promise<boolean> {
    const id = nodeId();
    if (!id) {
      message.error('请先选择节点');
      return false;
    }

    if (adminIds.length === 0) {
      return true;
    }

    operating.value = true;
    try {
      // 串行添加，避免并发问题
      for (const adminId of adminIds) {
        await addMemberApi(id, adminId);
      }
      message.success(`成功添加 ${adminIds.length} 名成员`);
      await loadMembers();
      return true;
    } catch (error_) {
      console.error('Failed to add members:', error_);
      message.error('批量添加成员失败');
      // 即使部分失败也刷新列表
      await loadMembers();
      return false;
    } finally {
      operating.value = false;
    }
  }

  /**
   * 移除成员
   */
  async function removeMember(adminId: number): Promise<boolean> {
    const id = nodeId();
    if (!id) {
      message.error('请先选择节点');
      return false;
    }

    operating.value = true;
    try {
      await removeMemberApi(id, adminId);
      message.success('成员已移除');
      // 从本地列表移除
      members.value = members.value.filter((m) => m.id !== adminId);
      return true;
    } catch (error_) {
      console.error('Failed to remove member:', error_);
      message.error('移除成员失败');
      return false;
    } finally {
      operating.value = false;
    }
  }

  /**
   * 设置负责人
   * @param adminId - 负责人 ID，传 null 取消负责人
   */
  async function setLeader(adminId: null | number): Promise<boolean> {
    const id = nodeId();
    if (!id) {
      message.error('请先选择节点');
      return false;
    }

    operating.value = true;
    try {
      await setLeaderApi(id, adminId);
      message.success(adminId ? '已设置为负责人' : '已取消负责人');
      // 更新本地列表的 isLeader 状态
      members.value = members.value.map((m) => ({
        ...m,
        isLeader: m.id === adminId,
      }));
      return true;
    } catch (error_) {
      console.error('Failed to set leader:', error_);
      message.error('设置负责人失败');
      return false;
    } finally {
      operating.value = false;
    }
  }

  /**
   * 刷新列表
   */
  async function refresh(): Promise<void> {
    await loadMembers();
  }

  /**
   * 切换页码
   */
  async function changePage(page: number): Promise<void> {
    pagination.value.page = page;
    await loadMembers();
  }

  /**
   * 切换每页数量
   */
  async function changePageSize(pageSize: number): Promise<void> {
    pagination.value.pageSize = pageSize;
    pagination.value.page = 1;
    await loadMembers();
  }

  /**
   * 搜索成员
   */
  async function search(keyword: string): Promise<void> {
    searchKeyword.value = keyword;
    await loadMembers(true);
  }

  /**
   * 切换是否包含子节点成员
   */
  async function toggleIncludeDescendants(value: boolean): Promise<void> {
    includeDescendants.value = value;
    await loadMembers(true);
  }

  // 监听节点 ID 变化，自动加载成员
  watch(
    () => nodeId(),
    (newId) => {
      if (newId) {
        // 切换节点时重置搜索和分页
        searchKeyword.value = '';
        pagination.value.page = 1;
        loadMembers();
      } else {
        members.value = [];
        pagination.value.total = 0;
      }
    },
    { immediate: true },
  );

  return {
    members,
    loading,
    operating,
    error,
    pagination,
    searchKeyword,
    includeDescendants,
    loadMembers,
    addMember,
    addMembers,
    removeMember,
    setLeader,
    refresh,
    changePage,
    changePageSize,
    search,
    toggleIncludeDescendants,
  };
}
