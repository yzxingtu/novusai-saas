/**
 * User endpoint authentication store / 用户端认证 Store
 * Handles tenant user login, logout, and user info management.
 * 专用于企业普通用户的登录、登出、用户信息管理。
 */
import type { UserInfo } from '@vben/types';

import type { LoginParams, TenantUserInfo } from '#/api';

import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { useAccessStore, useUserStore } from '@vben/stores';

import { notification } from 'ant-design-vue';
import { defineStore } from 'pinia';

import { userApi } from '#/api';
import {
  USER_HOME_PATH,
  USER_LOGIN_PATH,
  normalizeEndpointNavigationPath,
} from '#/constants/endpoints';
import { $t } from '#/locales';
import { EndpointType } from '#/types/endpoint';
import { toAvatarDisplayUrl } from '#/utils/image';

import { TokenStorage } from '../shared/token-storage';

export const useUserAuthStore = defineStore('user-auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();

  const loginLoading = ref(false);
  const userInfo = ref<null | TenantUserInfo>(null);

  /**
   * User login / 用户登录
   * @param params Login parameters / 登录参数
   * @param onSuccess Login success callback / 登录成功回调
   */
  async function login(
    params: LoginParams | Record<string, unknown>,
    onSuccess?: () => Promise<void> | void,
  ) {
    let info: null | TenantUserInfo = null;

    try {
      loginLoading.value = true;

      const username = String(params.username ?? '').trim();
      const password = String(params.password ?? '');

      const { accessToken, refreshToken } = await userApi.userLoginApi({
        password,
        username,
      });

      if (accessToken) {
        // Store token in user-specific storage / 存储 Token 到 user 端专用存储
        TokenStorage.setToken(EndpointType.USER, accessToken);
        if (refreshToken) {
          TokenStorage.setRefreshToken(EndpointType.USER, refreshToken);
        }

        // Also set in accessStore (vben framework compat) / 同时设置到 accessStore
        accessStore.setAccessToken(accessToken);
        if (refreshToken) {
          accessStore.setRefreshToken(refreshToken);
        }

        // Fetch user info / 获取用户信息
        info = await fetchUserInfo();

        // Convert to vben UserInfo format / 转换为 vben UserInfo 格式
        const vbenUserInfo: UserInfo = {
          avatar: toAvatarDisplayUrl(info?.avatar),
          desc: '',
          homePath: normalizeEndpointNavigationPath(
            info?.homePath,
            EndpointType.USER,
          ),
          realName: info?.realName || '',
          roles: info?.roles || [],
          token: accessToken,
          userId: String(info?.id || ''),
          username: info?.username || '',
        };

        userStore.setUserInfo(vbenUserInfo);

        if (accessStore.loginExpired) {
          accessStore.setLoginExpired(false);
        } else {
          onSuccess
            ? await onSuccess?.()
            : await router.push(vbenUserInfo.homePath || USER_HOME_PATH);
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
      // Error handled by axios interceptor; catch here to prevent bubbling to Vue event handler / 错误已由拦截器处理
    } finally {
      loginLoading.value = false;
    }

    return { userInfo: info };
  }

  /**
   * User logout / 用户登出
   * @param redirect Whether to redirect to login page / 是否重定向到登录页
   */
  async function logout(redirect: boolean = true) {
    try {
      await userApi.userLogoutApi();
    } catch {
      // Ignore error / 忽略错误
    }

    // Only clear user endpoint token / 仅清除 user 端 Token
    TokenStorage.clearToken(EndpointType.USER);

    // Clear accessStore / 清除 accessStore
    accessStore.setAccessToken(null);
    accessStore.setRefreshToken(null);
    accessStore.setLoginExpired(false);
    accessStore.setAccessMenus([]);
    accessStore.setAccessRoutes([]);
    accessStore.setAccessCodes([]);
    accessStore.setIsAccessChecked(false);

    userStore.setUserInfo(null);
    userInfo.value = null;

    await router.replace({
      path: USER_LOGIN_PATH,
      query: redirect
        ? {
            redirect: normalizeEndpointNavigationPath(
              router.currentRoute.value.fullPath,
              EndpointType.USER,
            ),
          }
        : {},
    });
  }

  /**
   * Fetch user info / 获取用户信息
   */
  async function fetchUserInfo() {
    const info = await userApi.getUserInfoApi();
    const normalizedInfo: TenantUserInfo = {
      ...info,
      homePath: normalizeEndpointNavigationPath(
        info?.homePath,
        EndpointType.USER,
      ),
    };
    userInfo.value = normalizedInfo;

    // Set permission codes / 设置权限码
    const permissions = normalizedInfo.permissions || [];
    accessStore.setAccessCodes(permissions);

    return normalizedInfo;
  }

  /**
   * Check if authenticated / 检查是否已认证
   */
  function isAuthenticated(): boolean {
    return TokenStorage.hasToken(EndpointType.USER);
  }

  /**
   * Get current token / 获取当前 Token
   */
  function getToken(): null | string {
    return TokenStorage.getToken(EndpointType.USER);
  }

  function $reset() {
    loginLoading.value = false;
    userInfo.value = null;
  }

  return {
    $reset,
    fetchUserInfo,
    getToken,
    isAuthenticated,
    login,
    loginLoading,
    logout,
    userInfo,
  };
});
