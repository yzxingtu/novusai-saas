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

  /** 指定租户的管理员在线（管理端查看租户详情时） */
  const tenantPresenceMap = reactive(new Map<number, Set<number>>());

  /** 是否已初始化 */
  const initialized = ref(false);

  // ============================================================
  // 查询方法
  // ============================================================

  /**
   * 判断用户是否在线
   */
  function isOnline(userType: string, userId: number, tenantId?: number): boolean {
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
    return false;
  }

  /**
   * 获取在线人数
   *
   * @param userType - 用户类型
   * @param ids - 可选，只统计这些 ID 中在线的数量
   */
  function getOnlineCount(userType: string, ids?: number[]): number {
    const onlineSet = userType === 'admin' ? adminOnlineIds : tenantAdminOnlineIds;
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
      const data = await requestClient.get<PresenceResponse>('/admin/ws/presence');
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
      const data = await requestClient.get<PresenceResponse>('/tenant/ws/presence');
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

    // 用户上线
    sioStore.registerHandler('presence:online', (data: unknown) => {
      const { user_id, user_type, tenant_id } = data as {
        user_id: number;
        user_type: string;
        tenant_id?: number;
      };
      if (user_type === 'admin') {
        adminOnlineIds.add(user_id);
      } else if (user_type === 'tenant_admin') {
        tenantAdminOnlineIds.add(user_id);
        if (tenant_id !== undefined) {
          const ids = tenantPresenceMap.get(tenant_id);
          if (ids) ids.add(user_id);
        }
      }
    });

    // 用户下线
    sioStore.registerHandler('presence:offline', (data: unknown) => {
      const { user_id, user_type, tenant_id } = data as {
        user_id: number;
        user_type: string;
        tenant_id?: number;
      };
      if (user_type === 'admin') {
        adminOnlineIds.delete(user_id);
      } else if (user_type === 'tenant_admin') {
        tenantAdminOnlineIds.delete(user_id);
        if (tenant_id !== undefined) {
          const ids = tenantPresenceMap.get(tenant_id);
          if (ids) ids.delete(user_id);
        }
      }
    });

    // 跨 namespace 租户管理员上线（平台管理员收到）
    sioStore.registerHandler('tenant_presence:online', (data: unknown) => {
      const { user_id, tenant_id } = data as {
        user_id: number;
        tenant_id: number;
      };
      if (tenant_id !== undefined) {
        let ids = tenantPresenceMap.get(tenant_id);
        if (!ids) {
          ids = new Set<number>();
          tenantPresenceMap.set(tenant_id, ids);
        }
        ids.add(user_id);
      }
    });

    // 跨 namespace 租户管理员下线（平台管理员收到）
    sioStore.registerHandler('tenant_presence:offline', (data: unknown) => {
      const { user_id, tenant_id } = data as {
        user_id: number;
        tenant_id: number;
      };
      if (tenant_id !== undefined) {
        const ids = tenantPresenceMap.get(tenant_id);
        if (ids) ids.delete(user_id);
      }
    });

    // 初始在线列表（连接时服务端推送）
    sioStore.registerHandler('presence:list', (data: unknown) => {
      const { online_ids } = data as { online_ids: number[] };
      if (!online_ids) return;

      // 根据当前 namespace 判断更新哪个集合
      const endpoint = sioStore.currentEndpoint;
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
      }
    });
  }

  // ============================================================
  // 重置
  // ============================================================

  function $reset() {
    adminOnlineIds.clear();
    tenantAdminOnlineIds.clear();
    tenantPresenceMap.clear();
    initialized.value = false;
  }

  return {
    adminOnlineIds,
    tenantAdminOnlineIds,
    tenantPresenceMap,
    isOnline,
    getOnlineCount,
    getTenantOnlineIds,
    loadAdminPresence,
    loadTenantPresence,
    loadCurrentTenantPresence,
    initSocketHandlers,
    $reset,
  };
});
