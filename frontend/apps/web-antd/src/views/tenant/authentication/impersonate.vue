<script lang="ts" setup>
/**
 * 平台管理员一键登录页面
 * 验证 impersonate token 并自动完成登录
 */
import type { UserInfo } from '@vben/types';

import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAccessStore, useUserStore } from '@vben/stores';

import { Button, Result, Spin } from 'ant-design-vue';

import { tenantApi } from '#/api';
import { $t } from '#/locales';
import { HOME_PATHS } from '#/store/shared/multi-auth';
import { TokenStorage } from '#/store/shared/token-storage';

defineOptions({ name: 'TenantImpersonate' });

const route = useRoute();
const router = useRouter();
const accessStore = useAccessStore();
const userStore = useUserStore();

/** 状态：loading | success | error */
const status = ref<'error' | 'loading' | 'success'>('loading');
/** 错误信息 */
const errorMessage = ref('');

/** 从 URL 获取 token 参数 */
const impersonateToken = computed(() => {
  return (route.query.token as string) || '';
});

/**
 * 执行一键登录流程
 */
async function doImpersonateLogin() {
  const token = impersonateToken.value;

  // 检查 token 参数
  if (!token) {
    status.value = 'error';
    errorMessage.value = $t('tenant.impersonate.invalidLink');
    return;
  }

  try {
    // 调用 API 换取正式 Token
    const result = await tenantApi.impersonateLoginApi(token);

    // 存储 Token 到 TokenStorage（租户端）
    TokenStorage.setToken('tenant', result.accessToken);
    if (result.refreshToken) {
      TokenStorage.setRefreshToken('tenant', result.refreshToken);
    }

    // 同时设置到 accessStore（兼容 vben 框架组件）
    accessStore.setAccessToken(result.accessToken);
    if (result.refreshToken) {
      accessStore.setRefreshToken(result.refreshToken);
    }

    // 获取用户信息
    const userInfo = await tenantApi.getTenantAdminInfoApi();

    // 转换为 vben 需要的 UserInfo 格式
    const vbenUserInfo: UserInfo = {
      avatar: userInfo?.avatar || '',
      desc: '',
      homePath: HOME_PATHS.tenant,
      realName: userInfo?.realName || '',
      roles: userInfo?.roles || [],
      token: result.accessToken,
      userId: String(userInfo?.id || ''),
      username: userInfo?.username || '',
    };

    userStore.setUserInfo(vbenUserInfo);

    // 设置权限码
    const permissions = userInfo?.permissions || [];
    accessStore.setAccessCodes(permissions);

    status.value = 'success';

    // 延迟跳转到租户后台首页
    setTimeout(() => {
      router.replace(HOME_PATHS.tenant);
    }, 1000);
  } catch (error: any) {
    status.value = 'error';
    // 根据错误类型显示不同提示
    errorMessage.value =
      error?.response?.status === 401 || error?.response?.status === 400
        ? $t('tenant.impersonate.tokenExpired')
        : error?.message || $t('tenant.impersonate.loginFailed');
  }
}

/** 跳转到登录页 */
function goToLogin() {
  router.replace('/tenant/login');
}

onMounted(() => {
  doImpersonateLogin();
});
</script>

<template>
  <div
    class="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900"
  >
    <div
      class="w-full max-w-md rounded-lg bg-white p-8 shadow-lg dark:bg-gray-800"
    >
      <!-- 加载状态 -->
      <div v-if="status === 'loading'" class="text-center">
        <Spin size="large" />
        <div class="mt-4 text-lg text-gray-600 dark:text-gray-300">
          {{ $t('tenant.impersonate.loading') }}
        </div>
        <div class="mt-2 text-sm text-gray-400">
          {{ $t('tenant.impersonate.pleaseWait') }}
        </div>
      </div>

      <!-- 成功状态 -->
      <Result
        v-else-if="status === 'success'"
        status="success"
        :title="$t('tenant.impersonate.success')"
        :sub-title="$t('tenant.impersonate.redirecting')"
      />

      <!-- 错误状态 -->
      <Result
        v-else
        status="error"
        :title="$t('tenant.impersonate.failed')"
        :sub-title="errorMessage"
      >
        <template #extra>
          <Button type="primary" @click="goToLogin">
            {{ $t('tenant.impersonate.backToLogin') }}
          </Button>
        </template>
      </Result>
    </div>
  </div>
</template>
