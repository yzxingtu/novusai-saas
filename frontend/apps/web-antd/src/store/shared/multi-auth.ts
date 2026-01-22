/**
 * 多端认证 Store
 * 支持平台管理端、租户后台、租户用户端三种认证模式
 *
 * Token 存储策略：
 * - 使用 TokenStorage 按端分离存储，各端 Token 互不干扰
 * - 登出仅清除当前端的 Token，不影响其他端
 */
import type { Recordable, UserInfo } from '@vben/types';

import type { ApiEndpoint, BaseUserInfo } from '#/api';

import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAccessStore, useTabbarStore, useUserStore } from '@vben/stores';

import { notification } from 'ant-design-vue';
import { defineStore } from 'pinia';

import { adminApi, getApiEndpoint, tenantApi, userApi } from '#/api';
import { $t } from '#/locales';

import { TokenStorage } from './token-storage';

/** 各端登录路径 */
export const LOGIN_PATHS: Record<ApiEndpoint, string> = {
  admin: '/admin/login',
  tenant: '/tenant/login',
  user: '/login',
};

/** 各端默认首页路径 */
export const HOME_PATHS: Record<ApiEndpoint, string> = {
  admin: '/admin/dashboard',
  tenant: '/tenant/dashboard',
  user: '/dashboard',
};

export const useMultiAuthStore = defineStore('multi-auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();
  const route = useRoute();

  const loginLoading = ref(false);

  /** 当前 API 端类型 */
  const currentEndpoint = computed<ApiEndpoint>(() => {
    return getApiEndpoint(route.path);
  });

  /** 当前端的登录路径 */
  const currentLoginPath = computed(() => {
    return LOGIN_PATHS[currentEndpoint.value];
  });

  /** 当前端的默认首页路径 */
  const currentHomePath = computed(() => {
    return HOME_PATHS[currentEndpoint.value];
  });

  /**
   * 获取当前端对应的 API
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
   * 登录
   * @param params 登录参数
   * @param endpoint 指定端类型（可选，默认根据当前路由判断）
   * @param onSuccess 登录成功回调
   */
  async function authLogin(
    params: Recordable<any>,
    endpoint?: ApiEndpoint,
    onSuccess?: () => Promise<void> | void,
  ) {
    const ep = endpoint || currentEndpoint.value;
    const api = getAuthApi(ep);
    const homePath = HOME_PATHS[ep];

    let userInfo: BaseUserInfo | null = null;

    try {
      loginLoading.value = true;

      const { accessToken, refreshToken } = await api.login({
        password: params.password,
        username: params.username,
      });

      if (accessToken) {
        // 使用 TokenStorage 按端存储 Token（多端分离存储）
        TokenStorage.setToken(ep, accessToken);
        if (refreshToken) {
          TokenStorage.setRefreshToken(ep, refreshToken);
        }

        // 同时设置到 accessStore（兼容 vben 框架组件）
        accessStore.setAccessToken(accessToken);
        if (refreshToken) {
          accessStore.setRefreshToken(refreshToken);
        }

        // 获取用户信息
        userInfo = await fetchUserInfo(ep);

        // 转换为 vben 需要的 UserInfo 格式
        const vbenUserInfo: UserInfo = {
          avatar: userInfo?.avatar || '',
          desc: '',
          homePath: userInfo?.homePath || homePath,
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
            : await router.push(vbenUserInfo.homePath || homePath);
        }

        if (vbenUserInfo.realName) {
          notification.success({
            description: `${$t('authentication.loginSuccessDesc')}:${vbenUserInfo.realName}`,
            duration: 3,
            message: $t('authentication.loginSuccess'),
          });
        }
      }
    } catch {
      // 错误已由 axios 拦截器处理并显示，此处仅捕获以防止冒泡到 Vue 事件处理器
    } finally {
      loginLoading.value = false;
    }

    return { userInfo };
  }

  /**
   * 登出
   * @param redirect 是否重定向到登录页
   * @param endpoint 指定端类型（可选）
   */
  async function logout(redirect: boolean = true, endpoint?: ApiEndpoint) {
    const ep = endpoint || currentEndpoint.value;
    const api = getAuthApi(ep);
    const loginPath = LOGIN_PATHS[ep];
    const tabbarStore = useTabbarStore();

    try {
      await api.logout();
    } catch {
      // 忽略错误
    }

    // 清除所有标签页（重置为空数组）
    tabbarStore.$patch({ tabs: [], cachedTabs: new Set() });
    // 清除 sessionStorage 中的标签页持久化数据
    sessionStorage.removeItem('core-tabbar');

    // 仅清除当前端的 Token（不影响其他端的登录状态）
    TokenStorage.clearToken(ep);

    // 清除 accessStore 中的 Token（当前端）
    accessStore.setAccessToken(null);
    accessStore.setRefreshToken(null);
    accessStore.setLoginExpired(false);

    // 重置用户信息和权限相关状态
    accessStore.setAccessMenus([]);
    accessStore.setAccessRoutes([]);
    accessStore.setAccessCodes([]);
    accessStore.setIsAccessChecked(false);
    userStore.setUserInfo(null as unknown as UserInfo);

    await router.replace({
      path: loginPath,
      query: redirect
        ? {
            redirect: encodeURIComponent(router.currentRoute.value.fullPath),
          }
        : {},
    });
  }

  /**
   * 获取用户信息
   * @param endpoint 指定端类型（可选）
   */
  async function fetchUserInfo(endpoint?: ApiEndpoint) {
    const api = getAuthApi(endpoint);
    const userInfo = await api.getUserInfo();

    // 转换为 vben 需要的 UserInfo 格式
    const vbenUserInfo: UserInfo = {
      avatar: userInfo?.avatar || '',
      desc: '',
      homePath: userInfo?.homePath || currentHomePath.value,
      realName: userInfo?.realName || '',
      roles: userInfo?.roles || [],
      token: accessStore.accessToken || '',
      userId: String(userInfo?.id || ''),
      username: userInfo?.username || '',
    };

    userStore.setUserInfo(vbenUserInfo);

    // 设置权限码到 accessStore，用于按钮级权限控制
    const permissions = userInfo?.permissions || [];
    accessStore.setAccessCodes(permissions);

    return userInfo;
  }

  /**
   * 刷新 Token
   * @param endpoint 指定端类型（可选）
   */
  async function refreshToken(endpoint?: ApiEndpoint) {
    const ep = endpoint || currentEndpoint.value;
    const api = getAuthApi(ep);

    // 从 TokenStorage 获取当前端的 Refresh Token
    const currentRefreshToken = TokenStorage.getRefreshToken(ep);

    if (!currentRefreshToken) {
      throw new Error('No refresh token available');
    }

    const result = await api.refreshToken(currentRefreshToken);

    // 更新 TokenStorage
    TokenStorage.setToken(ep, result.accessToken);
    if (result.refreshToken) {
      TokenStorage.setRefreshToken(ep, result.refreshToken);
    }

    // 同时更新 accessStore（兼容 vben 框架）
    accessStore.setAccessToken(result.accessToken);
    if (result.refreshToken) {
      accessStore.setRefreshToken(result.refreshToken);
    }

    return result.accessToken;
  }

  // ============================================================
  // Token 状态查询（供路由守卫和一键登录使用）
  // ============================================================

  /**
   * 获取指定端的 Access Token
   * @param endpoint 端类型
   */
  function getToken(endpoint?: ApiEndpoint): null | string {
    const ep = endpoint || currentEndpoint.value;
    return TokenStorage.getToken(ep);
  }

  /**
   * 检查指定端是否已认证（有有效 Token）
   * @param endpoint 端类型
   */
  function isAuthenticated(endpoint?: ApiEndpoint): boolean {
    const ep = endpoint || currentEndpoint.value;
    return TokenStorage.hasToken(ep);
  }

  /**
   * 获取所有已认证的端
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
