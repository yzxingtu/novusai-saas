/**
 * 在线状态 Store
 *
 * 管理用户在线状态数据，支持 HTTP 初始加载和 Socket.IO 实时更新。
 * 按用户类型和租户隔离状态数据。
 */

import { reactive, ref } from 'vue';

import { defineStore } from 'pinia';

import { requestClient } from '#/utils/request';

import { useSocketIOStore } from './socketio';

/** 在线状态详情 */
interface PresenceDetail {
  connections: number;
}

/** HTTP API 响应格式 */
interface PresenceResponse {
  online_ids: number[];
  total_online: number;
  tenant_id?: number;
  details: Record<string, PresenceDetail>;
}

export const usePresenceStore = defineStore('presence', () => {
  // ============================================================
  // 状态
  // ============================================================

  /** 平台管理员在线 ID 集合 */
  const adminOnlineIds = reactive(new Set<number>());

  /** 当前租户管理员在线 ID 集合 */
  const tenantAdminOnlineIds = reactive(new Set<number>());

  /** 当前租户业务用户在线 ID 集合 */
  const tenantUserOnlineIds = reactive(new Set<number>());

  /** 指定租户的管理员在线（管理端查看租户详情时） */
  const tenantPresenceMap = reactive(new Map<number, Set<number>>());

  /** 是否已初始化 */
  const initialized = ref(false);

  /** 固定 handler 引用，确保可对称 unregister */
  const handlePresenceOnline = (data: unknown) => {
    const { user_id, user_type, tenant_id } = data as {
      tenant_id?: number;
      user_id: number;
      user_type: string;
    };
    if (user_type === 'admin') {
      adminOnlineIds.add(user_id);
    } else if (user_type === 'tenant_admin') {
      tenantAdminOnlineIds.add(user_id);
      if (tenant_id !== undefined) {
        const ids = tenantPresenceMap.get(tenant_id);
        if (ids) ids.add(user_id);
      }
    } else if (user_type === 'tenant_user') {
      tenantUserOnlineIds.add(user_id);
    }
  };

  const handlePresenceOffline = (data: unknown) => {
    const { user_id, user_type, tenant_id } = data as {
      tenant_id?: number;
      user_id: number;
      user_type: string;
    };
    if (user_type === 'admin') {
      adminOnlineIds.delete(user_id);
    } else if (user_type === 'tenant_admin') {
      tenantAdminOnlineIds.delete(user_id);
      if (tenant_id !== undefined) {
        const ids = tenantPresenceMap.get(tenant_id);
        if (ids) ids.delete(user_id);
      }
    } else if (user_type === 'tenant_user') {
      tenantUserOnlineIds.delete(user_id);
    }
  };

  const handleTenantPresenceOnline = (data: unknown) => {
    const { user_id, tenant_id } = data as {
      tenant_id: number;
      user_id: number;
    };
    if (tenant_id !== undefined) {
      let ids = tenantPresenceMap.get(tenant_id);
      if (!ids) {
        ids = new Set<number>();
        tenantPresenceMap.set(tenant_id, ids);
      }
      ids.add(user_id);
    }
  };

  const handleTenantPresenceOffline = (data: unknown) => {
    const { user_id, tenant_id } = data as {
      tenant_id: number;
      user_id: number;
    };
    if (tenant_id !== undefined) {
      const ids = tenantPresenceMap.get(tenant_id);
      if (ids) ids.delete(user_id);
    }
  };

  const handleUserPresenceOnline = (data: unknown) => {
    const { user_id } = data as { user_id: number };
    tenantUserOnlineIds.add(user_id);
  };

  const handleUserPresenceOffline = (data: unknown) => {
    const { user_id } = data as { user_id: number };
    tenantUserOnlineIds.delete(user_id);
  };

  const handlePresenceList = (data: unknown) => {
    const { online_ids } = data as { online_ids: number[] };
    if (!online_ids) return;

    // 根据当前 namespace 判断更新哪个集合
    const endpoint = useSocketIOStore().currentEndpoint;
    if (endpoint === 'admin') {
      adminOnlineIds.clear();
      for (const id of online_ids) {
        adminOnlineIds.add(id);
      }
    } else if (endpoint === 'tenant') {
      tenantAdminOnlineIds.clear();
      for (const id of online_ids) {
        tenantAdminOnlineIds.add(id);
      }
    } else if (endpoint === 'user') {
      tenantUserOnlineIds.clear();
      for (const id of online_ids) {
        tenantUserOnlineIds.add(id);
      }
    }
  };

  // ============================================================
  // 查询方法
  // ============================================================

  /**
   * 判断用户是否在线
   */
  function isOnline(
    userType: string,
    userId: number,
    tenantId?: number,
  ): boolean {
    if (userType === 'admin') {
      return adminOnlineIds.has(userId);
    }
    if (userType === 'tenant_admin') {
      if (tenantId !== undefined) {
        const ids = tenantPresenceMap.get(tenantId);
        return ids ? ids.has(userId) : false;
      }
      return tenantAdminOnlineIds.has(userId);
    }
    if (userType === 'tenant_user') {
      return tenantUserOnlineIds.has(userId);
    }
    return false;
  }

  /**
   * 获取在线人数
   *
   * @param userType - 用户类型
   * @param ids - 可选，只统计这些 ID 中在线的数量
   */
  function getOnlineCount(userType: string, ids?: number[]): number {
    let onlineSet: Set<number>;
    if (userType === 'admin') {
      onlineSet = adminOnlineIds;
    } else if (userType === 'tenant_user') {
      onlineSet = tenantUserOnlineIds;
    } else {
      onlineSet = tenantAdminOnlineIds;
    }
    if (!ids) return onlineSet.size;
    return ids.filter((id) => onlineSet.has(id)).length;
  }

  /**
   * 获取指定租户的在线管理员 ID 列表
   */
  function getTenantOnlineIds(tenantId: number): number[] {
    const ids = tenantPresenceMap.get(tenantId);
    return ids ? [...ids] : [];
  }

  // ============================================================
  // HTTP 加载
  // ============================================================

  /**
   * 加载平台管理员在线状态
   */
  async function loadAdminPresence(): Promise<void> {
    try {
      const data =
        await requestClient.get<PresenceResponse>('/admin/ws/presence');
      if (data?.online_ids) {
        adminOnlineIds.clear();
        for (const id of data.online_ids) {
          adminOnlineIds.add(id);
        }
      }
    } catch {
      console.error('[Presence] Failed to load admin presence');
    }
  }

  /**
   * 加载指定租户的管理员在线状态
   */
  async function loadTenantPresence(tenantId: number): Promise<void> {
    try {
      const data = await requestClient.get<PresenceResponse>(
        `/admin/ws/presence/tenant/${tenantId}`,
      );
      if (data?.online_ids) {
        const ids = new Set<number>();
        for (const id of data.online_ids) {
          ids.add(id);
        }
        tenantPresenceMap.set(tenantId, ids);
      }
    } catch {
      console.error(`[Presence] Failed to load tenant ${tenantId} presence`);
    }
  }

  /**
   * 加载当前租户管理员在线状态（租户端使用）
   */
  async function loadCurrentTenantPresence(): Promise<void> {
    try {
      const data = await requestClient.get<PresenceResponse>(
        '/tenant/ws/presence',
      );
      if (data?.online_ids) {
        tenantAdminOnlineIds.clear();
        for (const id of data.online_ids) {
          tenantAdminOnlineIds.add(id);
        }
      }
    } catch {
      console.error('[Presence] Failed to load current tenant presence');
    }
  }

  /**
   * 加载当前租户业务用户在线状态（租户端使用）
   */
  async function loadTenantUserPresence(): Promise<void> {
    try {
      const data = await requestClient.get<PresenceResponse>(
        '/tenant/ws/presence/users',
      );
      if (data?.online_ids) {
        tenantUserOnlineIds.clear();
        for (const id of data.online_ids) {
          tenantUserOnlineIds.add(id);
        }
      }
    } catch {
      console.error('[Presence] Failed to load tenant user presence');
    }
  }

  // ============================================================
  // Socket.IO 实时更新
  // ============================================================

  /**
   * 初始化 Socket.IO 事件监听
   *
   * 注册 presence:online / presence:offline / presence:list handler
   */
  function initSocketHandlers(): void {
    if (initialized.value) return;
    initialized.value = true;

    const sioStore = useSocketIOStore();
    sioStore.unregisterHandler('presence:online', handlePresenceOnline);
    sioStore.unregisterHandler('presence:offline', handlePresenceOffline);
    sioStore.unregisterHandler(
      'tenant_presence:online',
      handleTenantPresenceOnline,
    );
    sioStore.unregisterHandler(
      'tenant_presence:offline',
      handleTenantPresenceOffline,
    );
    sioStore.unregisterHandler(
      'user_presence:online',
      handleUserPresenceOnline,
    );
    sioStore.unregisterHandler(
      'user_presence:offline',
      handleUserPresenceOffline,
    );
    sioStore.unregisterHandler('presence:list', handlePresenceList);

    sioStore.registerHandler('presence:online', handlePresenceOnline);
    sioStore.registerHandler('presence:offline', handlePresenceOffline);
    sioStore.registerHandler(
      'tenant_presence:online',
      handleTenantPresenceOnline,
    );
    sioStore.registerHandler(
      'tenant_presence:offline',
      handleTenantPresenceOffline,
    );
    sioStore.registerHandler(
      'user_presence:online',
      handleUserPresenceOnline,
    );
    sioStore.registerHandler(
      'user_presence:offline',
      handleUserPresenceOffline,
    );
    sioStore.registerHandler('presence:list', handlePresenceList);
  }

  // ============================================================
  // 重置
  // ============================================================

  function $reset() {
    try {
      const sioStore = useSocketIOStore();
      sioStore.unregisterHandler('presence:online', handlePresenceOnline);
      sioStore.unregisterHandler('presence:offline', handlePresenceOffline);
      sioStore.unregisterHandler(
        'tenant_presence:online',
        handleTenantPresenceOnline,
      );
      sioStore.unregisterHandler(
        'tenant_presence:offline',
        handleTenantPresenceOffline,
      );
      sioStore.unregisterHandler(
        'user_presence:online',
        handleUserPresenceOnline,
      );
      sioStore.unregisterHandler(
        'user_presence:offline',
        handleUserPresenceOffline,
      );
      sioStore.unregisterHandler('presence:list', handlePresenceList);
    } catch {
      // 静默
    }
    adminOnlineIds.clear();
    tenantAdminOnlineIds.clear();
    tenantUserOnlineIds.clear();
    tenantPresenceMap.clear();
    initialized.value = false;
  }

  return {
    adminOnlineIds,
    tenantAdminOnlineIds,
    tenantUserOnlineIds,
    tenantPresenceMap,
    isOnline,
    getOnlineCount,
    getTenantOnlineIds,
    loadAdminPresence,
    loadTenantPresence,
    loadCurrentTenantPresence,
    loadTenantUserPresence,
    initSocketHandlers,
    $reset,
  };
});
