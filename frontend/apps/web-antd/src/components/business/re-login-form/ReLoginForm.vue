<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import { computed } from 'vue';
import { useRouter } from 'vue-router';

import { AuthenticationLogin, z } from '@vben/common-ui';
import { useAccessStore } from '@vben/stores';

import { $t } from '#/locales';
import { useMultiAuthStore } from '#/store';
import { getEndpointFromPath, getLoginPath } from '#/utils';

defineOptions({ name: 'ReLoginForm' });

const router = useRouter();
const multiAuthStore = useMultiAuthStore();
const accessStore = useAccessStore();

/**
 * 根据当前路径自动检测端点（admin / tenant / user）
 * Auto-detect endpoint from current path
 */
const endpoint = computed(() =>
  getEndpointFromPath(router.currentRoute.value.path),
);

const formSchema = computed((): VbenFormSchema[] => {
  return [
    {
      component: 'VbenInput',
      componentProps: {
        placeholder: $t('authentication.usernameTip'),
      },
      fieldName: 'username',
      label: $t('authentication.username'),
      rules: z.string().min(1, { message: $t('authentication.usernameTip') }),
    },
    {
      component: 'VbenInputPassword',
      componentProps: {
        placeholder: $t('authentication.password'),
      },
      fieldName: 'password',
      label: $t('authentication.password'),
      rules: z.string().min(1, { message: $t('authentication.passwordTip') }),
    },
  ];
});

async function handleLogin(values: Record<string, unknown>) {
  const loginParams: Record<string, unknown> = {
    password: values.password,
    username: values.username,
  };

  const result = await multiAuthStore.authLogin(loginParams, endpoint.value);

  if (result.userInfo) {
    // 登录成功，authLogin 内部已处理 setLoginExpired(false) / Login OK; expired flag cleared in authLogin
    return;
  }

  // 登录失败：若后端要求验证码，关闭弹窗并跳转完整登录页 / Captcha required → full login page
  if (result.captchaRequired) {
    accessStore.setLoginExpired(false);
    router.push(getLoginPath(endpoint.value));
  }
}
</script>

<template>
  <AuthenticationLogin
    :form-schema="formSchema"
    :loading="multiAuthStore.loginLoading"
    :show-code-login="false"
    :show-forget-password="false"
    :show-qrcode-login="false"
    :show-register="false"
    :show-remember-me="false"
    :show-third-party-login="false"
    :sub-title="$t('shared.auth.reloginSubtitle')"
    :title="$t('shared.auth.reloginTitle')"
    @submit="handleLogin"
  />
</template>
