/**
 * 用户端认证 Store
 * 专用于租户普通用户的登录、登出、用户信息管理
 */
import type { Recordable, UserInfo } from '@vben/types';

import type { TenantUserInfo } from '#/api';

import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { useAccessStore, useUserStore } from '@vben/stores';

import { notification } from 'ant-design-vue';
import { defineStore } from 'pinia';

import { userApi } from '#/api';
import { USER_HOME_PATH, USER_LOGIN_PATH } from '#/constants/endpoints';
import { $t } from '#/locales';
import { EndpointType } from '#/types/endpoint';

import { TokenStorage } from '../shared/token-storage';

export const useUserAuthStore = defineStore('user-auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();

  const loginLoading = ref(false);
  const userInfo = ref<null | TenantUserInfo>(null);

  /**
   * 用户登录
   * @param params 登录参数
   * @param onSuccess 登录成功回调
   */
  async function login(
    params: Recordable<any>,
    onSuccess?: () => Promise<void> | void,
  ) {
    let info: null | TenantUserInfo = null;

    try {
      loginLoading.value = true;

      const { accessToken, refreshToken } = await userApi.userLoginApi({
        password: params.password,
        username: params.username,
      });

      if (accessToken) {
        // 存储Token到user端专用存储
        TokenStorage.setToken(EndpointType.USER, accessToken);
        if (refreshToken) {
          TokenStorage.setRefreshToken(EndpointType.USER, refreshToken);
        }

        // 同时设置到accessStore（兼容vben框架）
        accessStore.setAccessToken(accessToken);
        if (refreshToken) {
          accessStore.setRefreshToken(refreshToken);
        }

        // 获取用户信息
        info = await fetchUserInfo();

        // 转换为vben UserInfo格式
        const vbenUserInfo: UserInfo = {
          avatar: info?.avatar || '',
          desc: '',
          homePath: info?.homePath || USER_HOME_PATH,
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
      // 错误已由 axios 拦截器处理并显示，此处仅捕获以防止冒泡到 Vue 事件处理器
    } finally {
      loginLoading.value = false;
    }

    return { userInfo: info };
  }

  /**
   * 用户登出
   * @param redirect 是否重定向到登录页
   */
  async function logout(redirect: boolean = true) {
    try {
      await userApi.userLogoutApi();
    } catch {
      // 忽略错误
    }

    // 仅清除user端Token
    TokenStorage.clearToken(EndpointType.USER);

    // 清除accessStore
    accessStore.setAccessToken(null);
    accessStore.setRefreshToken(null);
    accessStore.setLoginExpired(false);
    accessStore.setAccessMenus([]);
    accessStore.setAccessRoutes([]);
    accessStore.setAccessCodes([]);
    accessStore.setIsAccessChecked(false);

    userStore.setUserInfo(null as unknown as UserInfo);
    userInfo.value = null;

    await router.replace({
      path: USER_LOGIN_PATH,
      query: redirect
        ? { redirect: encodeURIComponent(router.currentRoute.value.fullPath) }
        : {},
    });
  }

  /**
   * 获取用户信息
   */
  async function fetchUserInfo() {
    const info = await userApi.getUserInfoApi();
    userInfo.value = info;

    // 设置权限码
    const permissions = info?.permissions || [];
    accessStore.setAccessCodes(permissions);

    return info;
  }

  /**
   * 检查是否已认证
   */
  function isAuthenticated(): boolean {
    return TokenStorage.hasToken(EndpointType.USER);
  }

  /**
   * 获取当前Token
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
