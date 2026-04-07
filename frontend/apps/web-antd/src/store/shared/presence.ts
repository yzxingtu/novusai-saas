/**
 * Presence store / 在线状态 Store
 *
 * Manages user online status, supports HTTP initial load and Socket.IO real-time updates.
 * Isolates state data by user type and tenant.
 * 管理用户在线状态数据，支持 HTTP 初始加载和 Socket.IO 实时更新。
 */

import { reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAccessStore, useTabbarStore, useUserStore } from '@vben/stores';

import { Modal } from 'ant-design-vue';
import { defineStore } from 'pinia';

import {
  HOME_PATHS,
  LOGIN_PATHS,
  normalizeEndpointNavigationPath,
  resolveEndpointByPath,
} from '#/constants/endpoints';
import { $t } from '#/locales';
import { requestClient } from '#/utils/request';
import { clearPersistedTabbarStorage } from '#/utils/tabbar-storage';

import { useNotificationStore } from './notification';
import { useSocketIOStore } from './socketio';
import { TokenStorage } from './token-storage';
import { useUserPreferenceStore } from './user-preference';

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

type PresenceLoadScope = 'admin' | 'tenant';

interface PresenceLoadTarget {
  key: string;
  load: () => Promise<boolean>;
}

function createPresenceLoadKey(
  scope: PresenceLoadScope,
  userType: string,
  tenantId?: number,
): string {
  return typeof tenantId === 'number'
    ? `${scope}:${userType}:${tenantId}`
    : `${scope}:${userType}`;
}

export const usePresenceStore = defineStore('presence', () => {
  const accessStore = useAccessStore();
  const tabbarStore = useTabbarStore();
  const userStore = useUserStore();
  const router = useRouter();
  const route = useRoute();

  // ============================================================
  // State / 状态
  // ============================================================

  /** Admin online ID set / 平台管理员在线 ID 集合 */
  const adminOnlineIds = reactive(new Set<number>());

  /** Current tenant admin online ID set / 当前企业管理员在线 ID 集合 */
  const tenantAdminOnlineIds = reactive(new Set<number>());

  /** Current tenant user online ID set / 当前企业业务用户在线 ID 集合 */
  const tenantUserOnlineIds = reactive(new Set<number>());

  /** Tenant admin online map (when admin views tenant detail) / 指定企业的管理员在线 */
  const tenantPresenceMap = reactive(new Map<number, Set<number>>());

  /** Tenant user online map (when admin views tenant detail) / 指定企业的业务用户在线 */
  const tenantUserPresenceMap = reactive(new Map<number, Set<number>>());

  /** Whether initialized / 是否已初始化 */
  const initialized = ref(false);

  /** Loaded presence targets / 已完成初始化加载的 presence 目标 */
  const loadedPresenceKeys = reactive(new Set<string>());

  /** In-flight presence requests / 进行中的 presence 请求 */
  const pendingPresenceLoads = new Map<string, Promise<boolean>>();

  /** Fixed handler reference for symmetric unregister / 固定 handler 引用 */
  const handlePresenceOnline = (data: unknown) => {
    const { user_id, user_type, tenant_id } = data as {
      tenant_id?: number;
      user_id: number;
      user_type: string;
    };
    switch (user_type) {
      case 'admin': {
        adminOnlineIds.add(user_id);

        break;
      }
      case 'tenant_admin': {
        tenantAdminOnlineIds.add(user_id);
        if (tenant_id !== undefined) {
          const ids = tenantPresenceMap.get(tenant_id);
          if (ids) ids.add(user_id);
        }

        break;
      }
      case 'tenant_user': {
        tenantUserOnlineIds.add(user_id);

        break;
      }
      // No default
    }
  };

  const handlePresenceOffline = (data: unknown) => {
    const { user_id, user_type, tenant_id } = data as {
      tenant_id?: number;
      user_id: number;
      user_type: string;
    };
    switch (user_type) {
      case 'admin': {
        adminOnlineIds.delete(user_id);

        break;
      }
      case 'tenant_admin': {
        tenantAdminOnlineIds.delete(user_id);
        if (tenant_id !== undefined) {
          const ids = tenantPresenceMap.get(tenant_id);
          if (ids) ids.delete(user_id);
        }

        break;
      }
      case 'tenant_user': {
        tenantUserOnlineIds.delete(user_id);

        break;
      }
      // No default
    }
  };

  const handleForceLogout = () => {
    Modal.warning({
      content: `${$t('common.auth.forceLogoutMessage')} ${$t('common.auth.forceLogoutUnsavedHint')}`,
      okText: $t('common.confirm'),
      onOk: async () => {
        const endpoint = resolveEndpointByPath(
          route.path,
          window.location.hostname,
        );
        const loginPath = LOGIN_PATHS[endpoint];
        const userHomePath = normalizeEndpointNavigationPath(
          HOME_PATHS.user,
          'user',
        );

        useSocketIOStore().$reset();
        useNotificationStore().$reset();
        $reset();

        TokenStorage.clearToken(endpoint);
        accessStore.setAccessToken(null);
        accessStore.setRefreshToken(null);
        accessStore.setLoginExpired(false);
        accessStore.setAccessMenus([]);
        accessStore.setAccessRoutes([]);
        accessStore.setAccessCodes([]);
        accessStore.setIsAccessChecked(false);
        userStore.setUserInfo(null);
        tabbarStore.$patch({ tabs: [], cachedTabs: new Set() });
        clearPersistedTabbarStorage();
        useUserPreferenceStore().clearPreferences();

        if (endpoint === 'user') {
          await router.replace({
            path: userHomePath,
            query: {},
          });
          return;
        }

        await router.replace({
          path: loginPath,
          query: {
            redirect: normalizeEndpointNavigationPath(
              router.currentRoute.value.fullPath,
              endpoint,
            ),
          },
        });
      },
    });
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
    switch (endpoint) {
      case 'admin': {
        adminOnlineIds.clear();
        for (const id of online_ids) {
          adminOnlineIds.add(id);
        }
        loadedPresenceKeys.add(createPresenceLoadKey('admin', 'admin'));

        break;
      }
      case 'tenant': {
        tenantAdminOnlineIds.clear();
        for (const id of online_ids) {
          tenantAdminOnlineIds.add(id);
        }
        loadedPresenceKeys.add(createPresenceLoadKey('tenant', 'tenant_admin'));

        break;
      }
      case 'user': {
        tenantUserOnlineIds.clear();
        for (const id of online_ids) {
          tenantUserOnlineIds.add(id);
        }
        loadedPresenceKeys.add(createPresenceLoadKey('tenant', 'tenant_user'));

        break;
      }
      // No default
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
      if (tenantId !== undefined) {
        const ids = tenantUserPresenceMap.get(tenantId);
        return ids ? ids.has(userId) : false;
      }
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
   * Get online admin IDs for specified tenant / 获取指定企业的在线管理员 ID 列表
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
  async function loadAdminPresence(): Promise<boolean> {
    try {
      const data =
        await requestClient.get<PresenceResponse>('/admin/ws/presence');
      adminOnlineIds.clear();
      for (const id of data?.online_ids ?? []) {
        adminOnlineIds.add(id);
      }
      loadedPresenceKeys.add(createPresenceLoadKey('admin', 'admin'));
      return true;
    } catch {
      console.error('[Presence] Failed to load admin presence');
      return false;
    }
  }

  /**
   * Load tenant admin presence / 加载指定企业的管理员在线状态
   */
  async function loadTenantPresence(tenantId: number): Promise<boolean> {
    try {
      const data = await requestClient.get<PresenceResponse>(
        `/admin/ws/presence/tenant/${tenantId}`,
      );
      const ids = new Set<number>();
      for (const id of data?.online_ids ?? []) {
        ids.add(id);
      }
      tenantPresenceMap.set(tenantId, ids);
      loadedPresenceKeys.add(
        createPresenceLoadKey('admin', 'tenant_admin', tenantId),
      );
      return true;
    } catch {
      console.error(`[Presence] Failed to load tenant ${tenantId} presence`);
      return false;
    }
  }

  /**
   * Load current tenant admin presence (tenant-side) / 加载当前企业管理员在线状态
   */
  async function loadCurrentTenantPresence(): Promise<boolean> {
    try {
      const data = await requestClient.get<PresenceResponse>(
        '/tenant/ws/presence',
      );
      tenantAdminOnlineIds.clear();
      for (const id of data?.online_ids ?? []) {
        tenantAdminOnlineIds.add(id);
      }
      loadedPresenceKeys.add(createPresenceLoadKey('tenant', 'tenant_admin'));
      return true;
    } catch {
      console.error('[Presence] Failed to load current tenant presence');
      return false;
    }
  }

  /**
   * Load tenant user presence (tenant-side) / 加载当前企业业务用户在线状态
   */
  async function loadTenantUserPresence(): Promise<boolean> {
    try {
      const data = await requestClient.get<PresenceResponse>(
        '/tenant/ws/presence/users',
      );
      tenantUserOnlineIds.clear();
      for (const id of data?.online_ids ?? []) {
        tenantUserOnlineIds.add(id);
      }
      loadedPresenceKeys.add(createPresenceLoadKey('tenant', 'tenant_user'));
      return true;
    } catch {
      console.error('[Presence] Failed to load tenant user presence');
      return false;
    }
  }

  function resolvePresenceLoadTarget(
    userType: string,
    scope: PresenceLoadScope,
    tenantId?: number,
  ): null | PresenceLoadTarget {
    if (scope === 'admin') {
      if (userType === 'admin') {
        return {
          key: createPresenceLoadKey(scope, userType),
          load: loadAdminPresence,
        };
      }
      if (userType === 'tenant_user' && typeof tenantId === 'number') {
        return {
          key: createPresenceLoadKey(scope, userType, tenantId),
          load: async () => {
            try {
              const data = await requestClient.get<PresenceResponse>(
                `/admin/ws/presence/tenant/${tenantId}/users`,
              );
              const ids = new Set<number>();
              for (const id of data?.online_ids ?? []) {
                ids.add(id);
              }
              tenantUserPresenceMap.set(tenantId, ids);
              loadedPresenceKeys.add(
                createPresenceLoadKey('admin', 'tenant_user', tenantId),
              );
              return true;
            } catch {
              console.error(
                `[Presence] Failed to load tenant ${tenantId} user presence`,
              );
              return false;
            }
          },
        };
      }
      if (userType === 'tenant_admin' && typeof tenantId === 'number') {
        return {
          key: createPresenceLoadKey(scope, userType, tenantId),
          load: () => loadTenantPresence(tenantId),
        };
      }
      return null;
    }

    if (userType === 'tenant_admin') {
      return {
        key: createPresenceLoadKey(scope, userType),
        load: loadCurrentTenantPresence,
      };
    }
    if (userType === 'tenant_user') {
      return {
        key: createPresenceLoadKey(scope, userType),
        load: loadTenantUserPresence,
      };
    }
    return null;
  }

  async function ensurePresenceLoaded(
    userType: string,
    scope: PresenceLoadScope,
    tenantId?: number,
  ): Promise<boolean> {
    const target = resolvePresenceLoadTarget(userType, scope, tenantId);
    if (!target) {
      return false;
    }
    if (loadedPresenceKeys.has(target.key)) {
      return true;
    }

    const pending = pendingPresenceLoads.get(target.key);
    if (pending) {
      return pending;
    }

    const request = target
      .load()
      .finally(() => pendingPresenceLoads.delete(target.key));
    pendingPresenceLoads.set(target.key, request);
    return request;
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
    sioStore.unregisterHandler('force_logout', handleForceLogout);

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
    sioStore.registerHandler('user_presence:online', handleUserPresenceOnline);
    sioStore.registerHandler(
      'user_presence:offline',
      handleUserPresenceOffline,
    );
    sioStore.registerHandler('presence:list', handlePresenceList);
    sioStore.registerHandler('force_logout', handleForceLogout);
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
      sioStore.unregisterHandler('force_logout', handleForceLogout);
    } catch {
      // Silent / 静默
    }
    adminOnlineIds.clear();
    tenantAdminOnlineIds.clear();
    tenantUserOnlineIds.clear();
    tenantPresenceMap.clear();
    tenantUserPresenceMap.clear();
    loadedPresenceKeys.clear();
    pendingPresenceLoads.clear();
    initialized.value = false;
  }

  return {
    adminOnlineIds,
    tenantAdminOnlineIds,
    tenantUserOnlineIds,
    tenantPresenceMap,
    tenantUserPresenceMap,
    isOnline,
    getOnlineCount,
    getTenantOnlineIds,
    loadAdminPresence,
    loadTenantPresence,
    loadCurrentTenantPresence,
    loadTenantUserPresence,
    ensurePresenceLoaded,
    initSocketHandlers,
    $reset,
  };
});
