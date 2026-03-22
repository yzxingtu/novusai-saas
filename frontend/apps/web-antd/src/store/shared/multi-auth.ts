/**
 * Multi-endpoint authentication store / 多端认证 Store
 * Supports admin, tenant, and user authentication modes.
 * 支持平台管理端、企业后台、企业用户端三种认证模式。
 *
 * Token storage strategy / Token 存储策略：
 * - Uses TokenStorage for endpoint-separated storage; tokens don't interfere across endpoints.
 * - Logout only clears the current endpoint's token, not others.
 */
import type { UserInfo } from '@vben/types';

import type { ApiEndpoint, BaseUserInfo, LoginParams } from '#/api';

import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAccessStore, useTabbarStore, useUserStore } from '@vben/stores';

import { notification } from 'ant-design-vue';
import { defineStore } from 'pinia';

import { adminApi, tenantApi, userApi } from '#/api';
import {
  HOME_PATHS,
  LOGIN_PATHS,
  normalizeEndpointNavigationPath,
  resolveHomePathByPath,
  resolveLoginPathByPath,
} from '#/constants/endpoints';
import { $t } from '#/locales';
import { toAvatarDisplayUrl } from '#/utils/image';
import { clearPersistedTabbarStorage } from '#/utils/tabbar-storage';
import { getEndpointFromPath } from '#/utils';

import { TokenStorage } from './token-storage';
import { useUserPreferenceStore } from './user-preference';

export const useMultiAuthStore = defineStore('multi-auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();
  const route = useRoute();

  const loginLoading = ref(false);

  /** Current API endpoint type / 当前 API 端类型 */
  const currentEndpoint = computed<ApiEndpoint>(() => {
    return getEndpointFromPath(route.path) as ApiEndpoint;
  });

  /** Current endpoint login path / 当前端的登录路径 */
  const currentLoginPath = computed(() => {
    return resolveLoginPathByPath(route.path);
  });

  /** Current endpoint default home path / 当前端的默认首页路径 */
  const currentHomePath = computed(() => {
    return resolveHomePathByPath(route.path);
  });

  function resolvePostLoginTarget(endpoint: ApiEndpoint): string {
    const rawRedirect = route.query.redirect;
    const redirect =
      typeof rawRedirect === 'string'
        ? normalizeEndpointNavigationPath(rawRedirect, endpoint)
        : '';
    const fallbackHome = normalizeEndpointNavigationPath(
      HOME_PATHS[endpoint],
      endpoint,
    );

    return redirect || fallbackHome;
  }

  /**
   * Get auth API for the current endpoint / 获取当前端对应的 API
   */
  function getAuthApi(endpoint?: ApiEndpoint) {
    const ep = endpoint || currentEndpoint.value;
    switch (ep) {
      case 'admin': {
        return {
          changePassword: adminApi.adminChangePasswordApi,
          getUserInfo: adminApi.getAdminInfoApi,
          login: adminApi.adminLoginApi,
          logout: adminApi.adminLogoutApi,
          refreshToken: adminApi.adminRefreshTokenApi,
        };
      }
      case 'tenant': {
        return {
          changePassword: tenantApi.tenantChangePasswordApi,
          getUserInfo: tenantApi.getTenantAdminInfoApi,
          login: tenantApi.tenantLoginApi,
          logout: tenantApi.tenantLogoutApi,
          refreshToken: tenantApi.tenantRefreshTokenApi,
        };
      }
      default: {
        return {
          changePassword: userApi.userChangePasswordApi,
          getUserInfo: userApi.getUserInfoApi,
          login: userApi.userLoginApi,
          logout: userApi.userLogoutApi,
          refreshToken: userApi.userRefreshTokenApi,
        };
      }
    }
  }

  /**
   * Login / 登录
   * @param params Login parameters (username, password, optional captcha fields) / 登录参数
   * @param endpoint Endpoint type (optional, defaults to current route) / 指定端类型
   * @param onSuccess Login success callback / 登录成功回调
   * @returns { userInfo, captchaRequired } - null userInfo = login failed / captchaRequired = needs captcha
   */
  async function authLogin(
    params: LoginParams | Record<string, unknown>,
    endpoint?: ApiEndpoint,
    onSuccess?: () => Promise<void> | void,
  ) {
    const ep = endpoint || currentEndpoint.value;
    const api = getAuthApi(ep);
    const homePath = normalizeEndpointNavigationPath(HOME_PATHS[ep], ep);
    const postLoginTarget = resolvePostLoginTarget(ep);

    let userInfo: BaseUserInfo | null = null;
    let captchaRequired = false;

    try {
      loginLoading.value = true;

      const normalizeOptional = (value: unknown): string | undefined => {
        if (value === null || value === undefined) {
          return undefined;
        }
        const normalized = String(value).trim();
        return normalized ? normalized : undefined;
      };
      const username = normalizeOptional(params.username) ?? '';
      const password = normalizeOptional(params.password) ?? '';

      // Pass full login params (including captcha params) / 传递完整的登录参数
      const { accessToken, refreshToken } = await api.login({
        captchaChallengeId: normalizeOptional(params.captchaChallengeId),
        captchaProviderCode: normalizeOptional(params.captchaProviderCode),
        captchaSolution: normalizeOptional(params.captchaSolution),
        captchaType: normalizeOptional(params.captchaType),
        password,
        tenantCode: normalizeOptional(params.tenantCode),
        username,
      });

      if (accessToken) {
        // Store token per endpoint via TokenStorage (multi-endpoint separated) / 按端存储 Token
        TokenStorage.setToken(ep, accessToken);
        if (refreshToken) {
          TokenStorage.setRefreshToken(ep, refreshToken);
        }

        // Also set in accessStore (Vben framework compat) / 同时设置到 accessStore
        accessStore.setAccessToken(accessToken);
        if (refreshToken) {
          accessStore.setRefreshToken(refreshToken);
        }

        // Fetch user info / 获取用户信息
        userInfo = await fetchUserInfo(ep);

        // Load user preferences and sync to UI framework / 加载用户偏好并同步到 UI 框架
        const preferenceStore = useUserPreferenceStore();
        if (ep === 'admin' || ep === 'tenant') {
          preferenceStore.loadPreferences(ep).catch(() => {});
        }

        // Convert to Vben UserInfo format / 转换为 vben UserInfo 格式
        const vbenUserInfo: UserInfo = {
          avatar: toAvatarDisplayUrl(userInfo?.avatar),
          desc: '',
          homePath: normalizeEndpointNavigationPath(userInfo?.homePath, ep),
          realName: userInfo?.realName || '',
          roles: userInfo?.roles || [],
          token: accessToken,
          userId: String(userInfo?.id || ''),
          username: userInfo?.username || '',
        };

        userStore.setUserInfo(vbenUserInfo);

        if (accessStore.loginExpired) {
          accessStore.setLoginExpired(false);
        } else {
          onSuccess
            ? await onSuccess?.()
            : await router.push(postLoginTarget || vbenUserInfo.homePath || homePath);
        }

        if (vbenUserInfo.realName) {
          notification.success({
            description: `${$t('authentication.loginSuccessDesc')}:${vbenUserInfo.realName}`,
            duration: 3,
            message: $t('authentication.loginSuccess'),
          });
        }
      }
    } catch (error: unknown) {
      // Check if error response contains captcha_required field / 检查错误响应中是否包含 captcha_required
      const err = error as {
        response?: {
          data?: {
            data?: {
              captcha_required?: boolean;
            };
          };
        };
      };
      const responseData = err?.response?.data;
      if (responseData?.data?.captcha_required) {
        captchaRequired = true;
      }
      // Error handled by axios interceptor; catch to prevent bubbling / 错误已由拦截器处理
    } finally {
      loginLoading.value = false;
    }

    return { captchaRequired, userInfo };
  }

  /**
   * Logout / 登出
   * @param redirect Whether to redirect to login page / 是否重定向到登录页
   * @param endpoint Endpoint type (optional) / 指定端类型
   */
  async function logout(redirect: boolean = true, endpoint?: ApiEndpoint) {
    const ep = endpoint || currentEndpoint.value;
    const api = getAuthApi(ep);
    const loginPath = LOGIN_PATHS[ep];
    const userHomePath = normalizeEndpointNavigationPath(HOME_PATHS.user, 'user');
    const tabbarStore = useTabbarStore();

    try {
      await api.logout();
    } catch {
      // Ignore errors / 忽略错误
    }

    // Disconnect Socket.IO first (must happen before clearing token) / 先断开 Socket.IO
    try {
      const { useSocketIOStore } = await import('./socketio');
      const { useNotificationStore } = await import('./notification');
      const { usePresenceStore } = await import('./presence');
      const socketIOStore = useSocketIOStore();
      socketIOStore.$reset();
      useNotificationStore().$reset();
      usePresenceStore().$reset();
    } catch {
      // Silent / 静默
    }

    // Clear all tabs (reset to empty) / 清除所有标签页
    tabbarStore.$patch({ tabs: [], cachedTabs: new Set() });
    // Clear all tabbar persisted data from sessionStorage / 清除 tabbar 持久化数据
    clearPersistedTabbarStorage();

    // Clear only current endpoint's token (doesn't affect others) / 仅清除当前端 Token
    TokenStorage.clearToken(ep);

    // Clear accessStore token (current endpoint) / 清除 accessStore Token
    accessStore.setAccessToken(null);
    accessStore.setRefreshToken(null);
    accessStore.setLoginExpired(false);

    // Reset user info and permission state / 重置用户信息和权限状态
    accessStore.setAccessMenus([]);
    accessStore.setAccessRoutes([]);
    accessStore.setAccessCodes([]);
    accessStore.setIsAccessChecked(false);
    userStore.setUserInfo(null);

    // Clear preference cache / 清除偏好缓存
    const preferenceStore = useUserPreferenceStore();
    preferenceStore.clearPreferences();

    if (ep === 'user') {
      await router.replace({
        path: userHomePath,
        query: {},
      });
      return;
    }

    await router.replace({
      path: loginPath,
      query: redirect
        ? {
            redirect: normalizeEndpointNavigationPath(
              router.currentRoute.value.fullPath,
              ep,
            ),
          }
        : {},
    });
  }

  /**
   * Fetch user info / 获取用户信息
   * @param endpoint Endpoint type (optional) / 指定端类型
   */
  async function fetchUserInfo(endpoint?: ApiEndpoint) {
    const ep = endpoint || currentEndpoint.value;
    const api = getAuthApi(ep);
    const userInfo = await api.getUserInfo();
    const endpointHomePath = normalizeEndpointNavigationPath(
      userInfo?.homePath,
      ep,
    );
    const normalizedUserInfo = {
      ...userInfo,
      homePath: endpointHomePath,
    };

    // Tenant: check plan status, warn if no plan / 企业端：检查套餐状态
    if (
      ep === 'tenant' &&
      normalizedUserInfo &&
      'hasPlan' in normalizedUserInfo &&
      !normalizedUserInfo.hasPlan
    ) {
      notification.warning({
        description: $t('tenant.common.noPlanDesc'),
        duration: 0,
        message: $t('tenant.common.noPlan'),
      });
    }

    // Convert to Vben UserInfo format / 转换为 vben UserInfo 格式
    const vbenUserInfo: UserInfo = {
      avatar: toAvatarDisplayUrl(normalizedUserInfo?.avatar),
      desc: '',
      homePath: endpointHomePath,
      realName: normalizedUserInfo?.realName || '',
      roles: normalizedUserInfo?.roles || [],
      token: accessStore.accessToken || '',
      userId: String(normalizedUserInfo?.id || ''),
      username: normalizedUserInfo?.username || '',
    };

    userStore.setUserInfo(vbenUserInfo);

    // Set permission codes in accessStore for button-level access control / 设置权限码
    const permissions = normalizedUserInfo?.permissions || [];
    accessStore.setAccessCodes(permissions);

    return normalizedUserInfo;
  }

  /**
   * Refresh token / 刷新 Token
   * @param endpoint Endpoint type (optional) / 指定端类型
   */
  async function refreshToken(endpoint?: ApiEndpoint) {
    const ep = endpoint || currentEndpoint.value;
    const api = getAuthApi(ep);

    // Get current endpoint's refresh token from TokenStorage / 获取当前端 Refresh Token
    const currentRefreshToken = TokenStorage.getRefreshToken(ep);

    if (!currentRefreshToken) {
      throw new Error('No refresh token available');
    }

    const result = await api.refreshToken(currentRefreshToken);

    // Update TokenStorage / 更新 TokenStorage
    TokenStorage.setToken(ep, result.accessToken);
    if (result.refreshToken) {
      TokenStorage.setRefreshToken(ep, result.refreshToken);
    }

    // Also update accessStore (Vben compat) / 同时更新 accessStore
    accessStore.setAccessToken(result.accessToken);
    if (result.refreshToken) {
      accessStore.setRefreshToken(result.refreshToken);
    }

    return result.accessToken;
  }

  // ============================================================
  // Token state queries (for route guard & impersonate login)
  // Token 状态查询（供路由守卫和一键登录使用）
  // ============================================================

  /**
   * Get access token for specified endpoint / 获取指定端的 Access Token
   * @param endpoint Endpoint type / 端类型
   */
  function getToken(endpoint?: ApiEndpoint): null | string {
    const ep = endpoint || currentEndpoint.value;
    return TokenStorage.getToken(ep);
  }

  /**
   * Check if endpoint is authenticated (has valid token) / 检查指定端是否已认证
   * @param endpoint Endpoint type / 端类型
   */
  function isAuthenticated(endpoint?: ApiEndpoint): boolean {
    const ep = endpoint || currentEndpoint.value;
    return TokenStorage.hasToken(ep);
  }

  /**
   * Get all authenticated endpoints / 获取所有已认证的端
   */
  function getAuthenticatedEndpoints(): ApiEndpoint[] {
    return TokenStorage.getAuthenticatedEndpoints();
  }

  function $reset() {
    loginLoading.value = false;
  }

  return {
    $reset,
    authLogin,
    currentEndpoint,
    currentHomePath,
    currentLoginPath,
    fetchUserInfo,
    getAuthApi,
    getAuthenticatedEndpoints,
    getToken,
    isAuthenticated,
    loginLoading,
    logout,
    refreshToken,
  };
});
