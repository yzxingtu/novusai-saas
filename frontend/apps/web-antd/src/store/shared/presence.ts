/**
 * Presence store / 在线状态 Store
 *
 * Manages user online status, supports HTTP initial load and Socket.IO real-time updates.
 * Isolates state data by user type and tenant.
 * 管理用户在线状态数据，支持 HTTP 初始加载和 Socket.IO 实时更新。
 */

import { reactive, ref } from 'vue';

import { defineStore } from 'pinia';

import { requestClient } from '#/utils/request';

import { useSocketIOStore } from './socketio';

/** Presence detail / 在线状态详情 */
interface PresenceDetail {
  connections: number;
}

/** HTTP API response format / HTTP API 响应格式 */
interface PresenceResponse {
  online_ids: number[];
  total_online: number;
  tenant_id?: number;
  details: Record<string, PresenceDetail>;
}

export const usePresenceStore = defineStore('presence', () => {
  // ============================================================
  // State / 状态
  // ============================================================

  /** Admin online ID set / 平台管理员在线 ID 集合 */
  const adminOnlineIds = reactive(new Set<number>());

  /** Current tenant admin online ID set / 当前租户管理员在线 ID 集合 */
  const tenantAdminOnlineIds = reactive(new Set<number>());

  /** Current tenant user online ID set / 当前租户业务用户在线 ID 集合 */
  const tenantUserOnlineIds = reactive(new Set<number>());

  /** Tenant admin online map (when admin views tenant detail) / 指定租户的管理员在线 */
  const tenantPresenceMap = reactive(new Map<number, Set<number>>());

  /** Whether initialized / 是否已初始化 */
  const initialized = ref(false);

  /** Fixed handler reference for symmetric unregister / 固定 handler 引用 */
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

    // Determine which set to update based on current namespace / 根据当前 namespace 判断
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
  // Query methods / 查询方法
  // ============================================================

  /**
   * Check if user is online / 判断用户是否在线
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
   * Get online count / 获取在线人数
   *
   * @param userType - User type / 用户类型
   * @param ids - Optional, count only online users among these IDs / 可选，只统计这些 ID
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
   * Get online admin IDs for specified tenant / 获取指定租户的在线管理员 ID 列表
   */
  function getTenantOnlineIds(tenantId: number): number[] {
    const ids = tenantPresenceMap.get(tenantId);
    return ids ? [...ids] : [];
  }

  // ============================================================
  // HTTP loading / HTTP 加载
  // ============================================================

  /**
   * Load admin presence / 加载平台管理员在线状态
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
   * Load tenant admin presence / 加载指定租户的管理员在线状态
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
   * Load current tenant admin presence (tenant-side) / 加载当前租户管理员在线状态
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
   * Load tenant user presence (tenant-side) / 加载当前租户业务用户在线状态
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
  // Socket.IO real-time updates / Socket.IO 实时更新
  // ============================================================

  /**
   * Initialize Socket.IO event listeners / 初始化 Socket.IO 事件监听
   *
   * Registers presence:online / presence:offline / presence:list handlers.
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
  // Reset / 重置
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
      // Silent / 静默
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
