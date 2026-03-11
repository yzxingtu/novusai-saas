import type { UseMemberPanelOptions, UseMemberPanelReturn } from './types';

/**
 * Member Panel Business Logic Composable
 * 成员面板业务逻辑 composable
 */
import type { MemberListParams, OrgMember } from '#/api/admin/organization';
import type { TenantMemberListParams } from '#/api/tenant/organization';

import { ref, watch } from 'vue';

import { message } from 'ant-design-vue';

// Admin API / 管理端 API
import {
  addMemberToNodeApi as adminAddMemberApi,
  getNodeMembersApi as adminGetMembersApi,
  removeMemberFromNodeApi as adminRemoveMemberApi,
  setNodeLeaderApi as adminSetLeaderApi,
} from '#/api/admin/organization';
// Tenant API / 租户端 API
import {
  addTenantMemberToNodeApi as tenantAddMemberApi,
  getTenantNodeMembersApi as tenantGetMembersApi,
  removeTenantMemberFromNodeApi as tenantRemoveMemberApi,
  setTenantNodeLeaderApi as tenantSetLeaderApi,
} from '#/api/tenant/organization';
import { $t } from '#/locales';

/** Default page size / 默认每页数量 */
const DEFAULT_PAGE_SIZE = 20;

/**
 * Member panel management hook
 * Supports both admin and tenant API prefixes
 * 成员面板管理 hook
 * 支持 admin 和 tenant 两种 API 前缀
 */
export function useMemberPanel(
  options: UseMemberPanelOptions,
): UseMemberPanelReturn {
  const { nodeId, apiPrefix = 'admin' } = options;

  // State / 状态
  const members = ref<OrgMember[]>([]);
  const loading = ref(false);
  const operating = ref(false);
  const error = ref<null | string>(null);

  // Pagination state / 分页状态
  const pagination = ref({
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    total: 0,
  });

  // Search keyword / 搜索关键词
  const searchKeyword = ref('');

  // Whether to include descendant node members (recursive query) / 是否包含子节点成员（递归查询）
  const includeDescendants = ref(true);

  // Select API based on prefix / 根据前缀选择 API
  const getMembersApi =
    apiPrefix === 'tenant' ? tenantGetMembersApi : adminGetMembersApi;
  const addMemberApi =
    apiPrefix === 'tenant' ? tenantAddMemberApi : adminAddMemberApi;
  const removeMemberApi =
    apiPrefix === 'tenant' ? tenantRemoveMemberApi : adminRemoveMemberApi;
  const setLeaderApi =
    apiPrefix === 'tenant' ? tenantSetLeaderApi : adminSetLeaderApi;

  /**
   * Load member list
   * 加载成员列表
   * @param resetPage - Whether to reset to first page / 是否重置到第一页
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
      error.value = $t('shared.memberPanel.loadFailed');
      members.value = [];
      pagination.value.total = 0;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Add a single member
   * 添加单个成员
   */
  async function addMember(adminId: number): Promise<boolean> {
    const id = nodeId();
    if (!id) {
      message.error($t('shared.memberPanel.selectNodeFirst'));
      return false;
    }

    operating.value = true;
    try {
      await addMemberApi(id, adminId);
      message.success($t('shared.memberPanel.addSuccess'));
      await loadMembers();
      return true;
    } catch (error_) {
      console.error('Failed to add member:', error_);
      message.error($t('shared.memberPanel.addFailed'));
      return false;
    } finally {
      operating.value = false;
    }
  }

  /**
   * Batch add members
   * 批量添加成员
   */
  async function addMembers(adminIds: number[]): Promise<boolean> {
    const id = nodeId();
    if (!id) {
      message.error($t('shared.memberPanel.selectNodeFirst'));
      return false;
    }

    if (adminIds.length === 0) {
      return true;
    }

    operating.value = true;
    try {
      // Add sequentially to avoid concurrency issues / 串行添加，避免并发问题
      for (const adminId of adminIds) {
        await addMemberApi(id, adminId);
      }
      message.success(
        $t('shared.memberPanel.batchAddSuccess', { count: adminIds.length }),
      );
      await loadMembers();
      return true;
    } catch (error_) {
      console.error('Failed to add members:', error_);
      message.error($t('shared.memberPanel.batchAddFailed'));
      // Refresh list even if partially failed / 即使部分失败也刷新列表
      await loadMembers();
      return false;
    } finally {
      operating.value = false;
    }
  }

  /**
   * Remove a member
   * 移除成员
   */
  async function removeMember(
    adminId: number,
    targetRoleId?: number,
  ): Promise<boolean> {
    // Prefer passed roleId, otherwise use currently selected node / 优先使用传入的 roleId，否则使用当前选中节点
    const id = targetRoleId ?? nodeId();
    if (!id) {
      message.error($t('shared.memberPanel.selectNodeFirst'));
      return false;
    }

    operating.value = true;
    try {
      await removeMemberApi(id, adminId);
      message.success($t('shared.memberPanel.removeSuccess'));
      // Remove from local list / 从本地列表移除
      members.value = members.value.filter((m) => m.id !== adminId);
      return true;
    } catch (error_) {
      console.error('Failed to remove member:', error_);
      message.error($t('shared.memberPanel.removeFailed'));
      return false;
    } finally {
      operating.value = false;
    }
  }

  /**
   * Set leader
   * 设置负责人
   * @param adminId - Leader ID, pass null to cancel leader / 负责人 ID，传 null 取消负责人
   * @param targetRoleId - Target node ID (optional, for cross-node leader setting) / 目标节点 ID（可选，用于跨节点设置负责人）
   */
  async function setLeader(
    adminId: null | number,
    targetRoleId?: number,
  ): Promise<boolean> {
    // Use targetRoleId if specified, otherwise use currently selected node / 如果指定了 targetRoleId 则使用它，否则使用当前选中的节点
    const id = targetRoleId ?? nodeId();
    if (!id) {
      message.error($t('shared.memberPanel.selectNodeFirst'));
      return false;
    }

    operating.value = true;
    try {
      await setLeaderApi(id, adminId);
      message.success(
        adminId
          ? $t('shared.memberPanel.setLeaderSuccess')
          : $t('shared.memberPanel.cancelLeaderSuccess'),
      );
      // Reload list to get latest isLeader status / 重新加载列表以获取最新的 isLeader 状态
      await loadMembers();
      return true;
    } catch (error_) {
      console.error('Failed to set leader:', error_);
      message.error($t('shared.memberPanel.setLeaderFailed'));
      return false;
    } finally {
      operating.value = false;
    }
  }

  /**
   * Refresh list
   * 刷新列表
   */
  async function refresh(): Promise<void> {
    await loadMembers();
  }

  /**
   * Change page
   * 切换页码
   */
  async function changePage(page: number): Promise<void> {
    pagination.value.page = page;
    await loadMembers();
  }

  /**
   * Change page size
   * 切换每页数量
   */
  async function changePageSize(pageSize: number): Promise<void> {
    pagination.value.pageSize = pageSize;
    pagination.value.page = 1;
    await loadMembers();
  }

  /**
   * Search members
   * 搜索成员
   */
  async function search(keyword: string): Promise<void> {
    searchKeyword.value = keyword;
    await loadMembers(true);
  }

  /**
   * Toggle include descendant members
   * 切换是否包含子节点成员
   */
  async function toggleIncludeDescendants(value: boolean): Promise<void> {
    includeDescendants.value = value;
    await loadMembers(true);
  }

  // Watch node ID changes, auto-load members / 监听节点 ID 变化，自动加载成员
  watch(
    () => nodeId(),
    (newId) => {
      if (newId) {
        // Reset search and pagination when switching nodes / 切换节点时重置搜索和分页
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
    setLeader: (adminId: null | number, targetRoleId?: number) =>
      setLeader(adminId, targetRoleId),
    refresh,
    changePage,
    changePageSize,
    search,
    toggleIncludeDescendants,
  };
}
