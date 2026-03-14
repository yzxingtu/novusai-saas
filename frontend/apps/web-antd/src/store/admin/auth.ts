/**
 * Admin authentication store
 * 平台管理端认证 Store
 *
 * Handles admin login, logout, and user info management.
 * 专用于平台管理员的登录、登出、用户信息管理。
 */
import type { Recordable, UserInfo } from '@vben/types';

import type { AdminUserInfo } from '#/api';

import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { useAccessStore, useUserStore } from '@vben/stores';

import { notification } from 'ant-design-vue';
import { defineStore } from 'pinia';

import { adminApi } from '#/api';
import { ADMIN_HOME_PATH, ADMIN_LOGIN_PATH } from '#/constants/endpoints';
import { $t } from '#/locales';
import { EndpointType } from '#/types/endpoint';
import { toAvatarDisplayUrl } from '#/utils/image';

import { TokenStorage } from '../shared/token-storage';
import { useUserPreferenceStore } from '../shared/user-preference';

export const useAdminAuthStore = defineStore('admin-auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();

  const loginLoading = ref(false);
  const adminInfo = ref<AdminUserInfo | null>(null);

  /**
   * Admin login / 平台管理员登录
   * @param params Login parameters / 登录参数
   * @param onSuccess Login success callback / 登录成功回调
   */
  async function login(
    params: Recordable<any>,
    onSuccess?: () => Promise<void> | void,
  ) {
    let userInfo: AdminUserInfo | null = null;

    try {
      loginLoading.value = true;

      const { accessToken, refreshToken } = await adminApi.adminLoginApi({
        password: params.password,
        username: params.username,
      });

      if (accessToken) {
        // Store token in admin-specific storage / 存储Token到admin端专用存储
        TokenStorage.setToken(EndpointType.ADMIN, accessToken);
        if (refreshToken) {
          TokenStorage.setRefreshToken(EndpointType.ADMIN, refreshToken);
        }

        // Also set in accessStore (Vben framework compatibility) / 同时设置到accessStore
        accessStore.setAccessToken(accessToken);
        if (refreshToken) {
          accessStore.setRefreshToken(refreshToken);
        }

        // Fetch user info / 获取用户信息
        userInfo = await fetchUserInfo();

        // Load user preferences and sync to UI framework / 加载用户偏好并同步到 UI 框架
        const preferenceStore = useUserPreferenceStore();
        preferenceStore.loadPreferences('admin').catch(() => {});

        // Convert to Vben UserInfo format / 转换为vben UserInfo格式
        const vbenUserInfo: UserInfo = {
          avatar: toAvatarDisplayUrl(userInfo?.avatar),
          desc: userInfo?.isSuperAdmin
            ? $t('admin.system.admin.superAdmin')
            : $t('admin.system.admin.normalAdmin'),
          homePath: userInfo?.homePath || ADMIN_HOME_PATH,
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
            : await router.push(vbenUserInfo.homePath || ADMIN_HOME_PATH);
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
      // Error handled by axios interceptor; catch here to prevent bubbling / 错误已由拦截器处理
    } finally {
      loginLoading.value = false;
    }

    return { userInfo };
  }

  /**
   * Admin logout / 平台管理员登出
   * @param redirect Whether to redirect to login page / 是否重定向到登录页
   */
  async function logout(redirect: boolean = true) {
    try {
      await adminApi.adminLogoutApi();
    } catch {
      // Ignore errors / 忽略错误
    }

    // Clear admin-side token only / 仅清除admin端Token
    TokenStorage.clearToken(EndpointType.ADMIN);

    // Clear accessStore / 清除accessStore
    accessStore.setAccessToken(null);
    accessStore.setRefreshToken(null);
    accessStore.setLoginExpired(false);
    accessStore.setAccessMenus([]);
    accessStore.setAccessRoutes([]);
    accessStore.setAccessCodes([]);
    accessStore.setIsAccessChecked(false);

    userStore.setUserInfo(null);
    adminInfo.value = null;

    // Clear preference cache / 清除偏好缓存
    const preferenceStore = useUserPreferenceStore();
    preferenceStore.clearPreferences();

    await router.replace({
      path: ADMIN_LOGIN_PATH,
      query: redirect ? { redirect: router.currentRoute.value.fullPath } : {},
    });
  }

  /**
   * Fetch admin user info / 获取平台管理员信息
   * Note: permission codes are fetched from menu API, not set here.
   * 注意：权限码从菜单接口获取，不在此处设置。
   */
  async function fetchUserInfo() {
    const info = await adminApi.getAdminInfoApi();
    adminInfo.value = info;
    return info;
  }

  /**
   * Check if authenticated / 检查是否已认证
   */
  function isAuthenticated(): boolean {
    return TokenStorage.hasToken(EndpointType.ADMIN);
  }

  /**
   * Get current token / 获取当前Token
   */
  function getToken(): null | string {
    return TokenStorage.getToken(EndpointType.ADMIN);
  }

  function $reset() {
    loginLoading.value = false;
    adminInfo.value = null;
  }

  return {
    $reset,
    adminInfo,
    fetchUserInfo,
    getToken,
    isAuthenticated,
    login,
    loginLoading,
    logout,
  };
});
