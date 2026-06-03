<script lang="ts" setup>
/**
 * Platform admin one-click login page
 * 平台管理员一键登录页面
 * Validates impersonate token and auto-completes login
 * 验证 impersonate token 并自动完成登录
 */
import type { UserInfo } from '@vben/types';

import type { AIAvailabilityInfo, BaseUserInfo } from '#/api';

import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAccessStore, useUserStore } from '@vben/stores';

import { Button, Result, Spin } from 'ant-design-vue';

import { tenantApi } from '#/api';
import { HOME_PATHS } from '#/constants/endpoints';
import { $t } from '#/locales';
import { TokenStorage } from '#/store/shared/token-storage';
import { toAvatarDisplayUrl } from '#/utils/image';

defineOptions({ name: 'TenantImpersonate' });

const route = useRoute();
const router = useRouter();
const accessStore = useAccessStore();
const userStore = useUserStore();

/** Status: loading | success | error / 状态 */
const status = ref<'error' | 'loading' | 'success'>('loading');
/** Error message / 错误信息 */
const errorMessage = ref('');

function getAIAvailabilityInfo(
  userInfo: BaseUserInfo | null | undefined,
): AIAvailabilityInfo {
  return {
    accountAIEnabled: userInfo?.accountAIEnabled,
    aiChatEnabled: userInfo?.aiChatEnabled,
    aiUnavailableReason: userInfo?.aiUnavailableReason,
    tenantPlanAIEnabled: userInfo?.tenantPlanAIEnabled,
  };
}

/** Get token param from URL / 从 URL 获取 token 参数 */
const impersonateToken = computed(() => {
  return (route.query.token as string) || '';
});

/**
 * Execute one-click login flow
 * 执行一键登录流程
 */
async function doImpersonateLogin() {
  const token = impersonateToken.value;

  // Check token param / 检查 token 参数
  if (!token) {
    status.value = 'error';
    errorMessage.value = $t('tenant.impersonate.invalidLink');
    return;
  }

  try {
    // Call API to exchange for official Token / 调用 API 换取正式 Token
    const result = await tenantApi.impersonateLoginApi(token);

    // Store Token to TokenStorage (tenant) / 存储 Token 到 TokenStorage
    TokenStorage.setToken('tenant', result.accessToken);
    if (result.refreshToken) {
      TokenStorage.setRefreshToken('tenant', result.refreshToken);
    }

    // Also set to accessStore (vben framework compatibility) / 同时设置到 accessStore
    accessStore.setAccessToken(result.accessToken);
    if (result.refreshToken) {
      accessStore.setRefreshToken(result.refreshToken);
    }

    // Get user info / 获取用户信息
    const userInfo = await tenantApi.getTenantAdminInfoApi();

    // Convert to vben UserInfo format / 转换为 vben UserInfo 格式
    const vbenUserInfo: AIAvailabilityInfo & UserInfo = {
      avatar: toAvatarDisplayUrl(userInfo?.avatar),
      desc: '',
      homePath: HOME_PATHS.tenant,
      realName: userInfo?.realName || '',
      roles: userInfo?.roles || [],
      token: result.accessToken,
      userId: String(userInfo?.id || ''),
      username: userInfo?.username || '',
      ...getAIAvailabilityInfo(userInfo),
    };

    userStore.setUserInfo(vbenUserInfo);

    // Set permission codes / 设置权限码
    const permissions = userInfo?.permissions || [];
    accessStore.setAccessCodes(permissions);

    status.value = 'success';

    // Delayed redirect to tenant dashboard / 延迟跳转到企业后台首页
    setTimeout(() => {
      router.replace(HOME_PATHS.tenant);
    }, 1000);
  } catch (error: unknown) {
    status.value = 'error';
    // Show different hints based on error type / 根据错误类型显示不同提示
    const err = error as { message?: string; response?: { status?: number } };
    errorMessage.value =
      err?.response?.status === 401 || err?.response?.status === 400
        ? $t('tenant.impersonate.tokenExpired')
        : err?.message || $t('tenant.impersonate.loginFailed');
  }
}

/** Navigate to login page / 跳转到登录页 */
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
      <!-- Loading state / 加载状态 -->
      <div v-if="status === 'loading'" class="text-center">
        <Spin size="large" />
        <div class="mt-4 text-lg text-gray-600 dark:text-gray-300">
          {{ $t('tenant.impersonate.loading') }}
        </div>
        <div class="mt-2 text-sm text-gray-400">
          {{ $t('tenant.impersonate.pleaseWait') }}
        </div>
      </div>

      <!-- Success state / 成功状态 -->
      <Result
        v-else-if="status === 'success'"
        status="success"
        :title="$t('tenant.impersonate.success')"
        :sub-title="$t('tenant.impersonate.redirecting')"
      />

      <!-- Error state / 错误状态 -->
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
