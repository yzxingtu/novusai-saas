/**
 * Tenant admin authentication store / 企业管理端认证 Store
 * Handles tenant admin login, logout, and user info management.
 * 专用于企业管理员的登录、登出、用户信息管理。
 */
import type { Recordable, UserInfo } from '@vben/types';

import type { TenantAdminInfo } from '#/api';

import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { useAccessStore, useUserStore } from '@vben/stores';

import { notification } from 'ant-design-vue';
import { defineStore } from 'pinia';

import { tenantApi } from '#/api';
import { TENANT_HOME_PATH, TENANT_LOGIN_PATH } from '#/constants/endpoints';
import { $t } from '#/locales';
import { EndpointType } from '#/types/endpoint';
import { toAvatarDisplayUrl } from '#/utils/image';

import { TokenStorage } from '../shared/token-storage';
import { useUserPreferenceStore } from '../shared/user-preference';

export const useTenantAuthStore = defineStore('tenant-auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();

  const loginLoading = ref(false);
  const tenantAdminInfo = ref<null | TenantAdminInfo>(null);

  /**
   * Tenant admin login / 企业管理员登录
   * @param params Login parameters / 登录参数
   * @param onSuccess Login success callback / 登录成功回调
   */
  async function login(
    params: Recordable<any>,
    onSuccess?: () => Promise<void> | void,
  ) {
    let userInfo: null | TenantAdminInfo = null;

    try {
      loginLoading.value = true;

      const { accessToken, refreshToken } = await tenantApi.tenantLoginApi({
        password: params.password,
        username: params.username,
      });

      if (accessToken) {
        // Store token in tenant-specific storage / 存储 Token 到 tenant 端专用存储
        TokenStorage.setToken(EndpointType.TENANT, accessToken);
        if (refreshToken) {
          TokenStorage.setRefreshToken(EndpointType.TENANT, refreshToken);
        }

        // Also set in accessStore (vben framework compat) / 同时设置到 accessStore
        accessStore.setAccessToken(accessToken);
        if (refreshToken) {
          accessStore.setRefreshToken(refreshToken);
        }

        // Fetch user info / 获取用户信息
        userInfo = await fetchUserInfo();

        // Load user preferences and sync to UI framework / 加载用户偏好并同步到 UI 框架
        const preferenceStore = useUserPreferenceStore();
        preferenceStore.loadPreferences('tenant').catch(() => {});

        // Convert to vben UserInfo format / 转换为 vben UserInfo 格式
        const vbenUserInfo: UserInfo = {
          avatar: toAvatarDisplayUrl(userInfo?.avatar),
          desc: userInfo?.tenantName || $t('tenant.common.tenantAdmin'),
          homePath: userInfo?.homePath || TENANT_HOME_PATH,
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
            : await router.push(vbenUserInfo.homePath || TENANT_HOME_PATH);
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

    return { userInfo };
  }

  /**
   * Tenant admin logout / 企业管理员登出
   * @param redirect Whether to redirect to login page / 是否重定向到登录页
   */
  async function logout(redirect: boolean = true) {
    try {
      await tenantApi.tenantLogoutApi();
    } catch {
      // Ignore error / 忽略错误
    }

    // Only clear tenant endpoint token / 仅清除 tenant 端 Token
    TokenStorage.clearToken(EndpointType.TENANT);

    // Clear accessStore / 清除 accessStore
    accessStore.setAccessToken(null);
    accessStore.setRefreshToken(null);
    accessStore.setLoginExpired(false);
    accessStore.setAccessMenus([]);
    accessStore.setAccessRoutes([]);
    accessStore.setAccessCodes([]);
    accessStore.setIsAccessChecked(false);

    userStore.setUserInfo(null);
    tenantAdminInfo.value = null;

    // Clear preference cache / 清除偏好缓存
    const preferenceStore = useUserPreferenceStore();
    preferenceStore.clearPreferences();

    await router.replace({
      path: TENANT_LOGIN_PATH,
      query: redirect ? { redirect: router.currentRoute.value.fullPath } : {},
    });
  }

  /**
   * Fetch tenant admin info / 获取企业管理员信息
   * Note: Permission codes are fetched from menu API, not set here.
   * 注意：权限码从菜单接口获取。
   */
  async function fetchUserInfo() {
    const info = await tenantApi.getTenantAdminInfoApi();
    tenantAdminInfo.value = info;
    return info;
  }

  /**
   * Check if authenticated / 检查是否已认证
   */
  function isAuthenticated(): boolean {
    return TokenStorage.hasToken(EndpointType.TENANT);
  }

  /**
   * Get current token / 获取当前 Token
   */
  function getToken(): null | string {
    return TokenStorage.getToken(EndpointType.TENANT);
  }

  /**
   * Get current tenant ID / 获取当前企业 ID
   */
  function getTenantId(): null | number | string {
    return tenantAdminInfo.value?.tenantId || null;
  }

  function $reset() {
    loginLoading.value = false;
    tenantAdminInfo.value = null;
  }

  return {
    $reset,
    fetchUserInfo,
    getToken,
    getTenantId,
    isAuthenticated,
    login,
    loginLoading,
    logout,
    tenantAdminInfo,
  };
});
