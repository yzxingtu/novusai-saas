<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import type { CaptchaDifficulty } from '#/api/public/captcha';

import { computed, onMounted, ref } from 'vue';

import { AuthenticationLogin, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { Input } from 'ant-design-vue';

import { CaptchaImage } from '#/components/business/captcha';
import { useMultiAuthStore, usePublicConfigStore } from '#/store';

defineOptions({ name: 'AdminLogin' });

const publicConfigStore = usePublicConfigStore();
const multiAuthStore = useMultiAuthStore();

// 验证码组件引用
const captchaRef = ref<InstanceType<typeof CaptchaImage>>();
// 验证码用户输入
const captchaSolution = ref('');

// 首次访问加载平台公开配置
onMounted(() => {
  publicConfigStore.loadPlatformConfig();
});

// 是否需要显示验证码
const showCaptcha = computed(() => publicConfigStore.shouldShowPlatformCaptcha);

// 验证码难度
const captchaDifficulty = computed((): CaptchaDifficulty => {
  const difficulty = publicConfigStore.platformCaptcha?.difficulty;
  if (
    difficulty === 'easy' ||
    difficulty === 'medium' ||
    difficulty === 'hard'
  ) {
    return difficulty;
  }
  return 'medium';
});

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

// 刷新验证码
function refreshCaptcha() {
  captchaSolution.value = '';
  captchaRef.value?.refresh();
}

async function handleLogin(values: Record<string, any>) {
  // 构建登录参数
  const loginParams: Record<string, any> = {
    password: values.password,
    username: values.username,
  };

  // 如果需要验证码，添加验证码参数
  if (showCaptcha.value && captchaRef.value) {
    if (!captchaSolution.value) {
      // 验证码未填写，不提交
      return;
    }
    loginParams.captchaChallengeId = captchaRef.value.getChallengeId();
    loginParams.captchaSolution = captchaSolution.value;
    loginParams.captchaType = 'image';
    // 使用缓存的验证码提供方标识，降级为 'image'
    loginParams.captchaProviderCode =
      publicConfigStore.platformCaptcha?.provider ?? 'image';
  }

  const result = await multiAuthStore.authLogin(loginParams, 'admin');

  // 登录失败时处理
  if (result.userInfo) {
    // 登录成功重置登录状态
    publicConfigStore.resetPlatformLoginState();
  } else {
    publicConfigStore.incrementPlatformLoginFail();

    // 如果后端要求显示验证码，设置强制要求状态
    if (result.captchaRequired) {
      publicConfigStore.setPlatformCaptchaRequired(true);
    }

    // 刷新验证码
    refreshCaptcha();
  }
}
</script>

<template>
  <div>
    <!-- 平台管理端标识 -->
    <div class="mb-6 flex items-center justify-center">
      <div class="flex items-center gap-2 rounded-full bg-primary/10 px-4 py-2">
        <span class="i-lucide-shield-check text-xl text-primary"></span>
        <span class="text-sm font-medium text-primary">
          {{ $t('authentication.platformAdmin') }}
        </span>
      </div>
    </div>

    <AuthenticationLogin
      :form-schema="formSchema"
      :loading="multiAuthStore.loginLoading"
      :show-code-login="false"
      :show-forget-password="false"
      :show-qrcode-login="false"
      :show-register="false"
      :show-remember-me="false"
      :show-third-party-login="false"
      :title="$t('admin.auth.title')"
      :sub-title="$t('authentication.platformAdminDesc')"
      @submit="handleLogin"
    >
      <!-- 验证码插槽 - 显示在密码输入框下方 -->
      <template v-if="showCaptcha" #form-extend>
        <div class="captcha-section">
          <div class="captcha-row">
            <Input
              v-model:value="captchaSolution"
              :placeholder="$t('shared.auth.captcha.placeholder')"
              :maxlength="6"
              size="large"
              class="captcha-input"
            />
            <CaptchaImage
              ref="captchaRef"
              endpoint="admin"
              :difficulty="captchaDifficulty"
            />
          </div>
        </div>
      </template>
    </AuthenticationLogin>
  </div>
</template>

<style scoped>
.captcha-section {
  margin-top: 8px;
  margin-bottom: 16px;
}

.captcha-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.captcha-input {
  flex: 1;
  min-width: 0;
}
</style>
