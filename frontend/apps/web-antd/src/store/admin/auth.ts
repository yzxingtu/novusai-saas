/**
 * 平台管理端认证 Store
 * 专用于平台管理员的登录、登出、用户信息管理
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

import { TokenStorage } from '../shared/token-storage';

export const useAdminAuthStore = defineStore('admin-auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();

  const loginLoading = ref(false);
  const adminInfo = ref<AdminUserInfo | null>(null);

  /**
   * 平台管理员登录
   * @param params 登录参数
   * @param onSuccess 登录成功回调
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
        // 存储Token到admin端专用存储
        TokenStorage.setToken(EndpointType.ADMIN, accessToken);
        if (refreshToken) {
          TokenStorage.setRefreshToken(EndpointType.ADMIN, refreshToken);
        }

        // 同时设置到accessStore（兼容vben框架）
        accessStore.setAccessToken(accessToken);
        if (refreshToken) {
          accessStore.setRefreshToken(refreshToken);
        }

        // 获取用户信息
        userInfo = await fetchUserInfo();

        // 转换为vben UserInfo格式
        const vbenUserInfo: UserInfo = {
          avatar: userInfo?.avatar || '',
          desc: userInfo?.isSuperAdmin ? '超级管理员' : '普通管理员',
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
      // 错误已由 axios 拦截器处理并显示，此处仅捕获以防止冒泡到 Vue 事件处理器
    } finally {
      loginLoading.value = false;
    }

    return { userInfo };
  }

  /**
   * 平台管理员登出
   * @param redirect 是否重定向到登录页
   */
  async function logout(redirect: boolean = true) {
    try {
      await adminApi.adminLogoutApi();
    } catch {
      // 忽略错误
    }

    // 仅清除admin端Token
    TokenStorage.clearToken(EndpointType.ADMIN);

    // 清除accessStore
    accessStore.setAccessToken(null);
    accessStore.setRefreshToken(null);
    accessStore.setLoginExpired(false);
    accessStore.setAccessMenus([]);
    accessStore.setAccessRoutes([]);
    accessStore.setAccessCodes([]);
    accessStore.setIsAccessChecked(false);

    userStore.setUserInfo(null as unknown as UserInfo);
    adminInfo.value = null;

    await router.replace({
      path: ADMIN_LOGIN_PATH,
      query: redirect
        ? { redirect: encodeURIComponent(router.currentRoute.value.fullPath) }
        : {},
    });
  }

  /**
   * 获取平台管理员信息
   * 注意：权限码从菜单接口获取，不在此处设置
   */
  async function fetchUserInfo() {
    const info = await adminApi.getAdminInfoApi();
    adminInfo.value = info;
    return info;
  }

  /**
   * 检查是否已认证
   */
  function isAuthenticated(): boolean {
    return TokenStorage.hasToken(EndpointType.ADMIN);
  }

  /**
   * 获取当前Token
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
