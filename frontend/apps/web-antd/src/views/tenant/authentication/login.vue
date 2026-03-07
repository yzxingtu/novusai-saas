<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import type { CaptchaDifficulty } from '#/api/public/captcha';

import { computed, onMounted, ref } from 'vue';

import { AuthenticationLogin, z } from '@vben/common-ui';
import { $t } from '@vben/locales';
import { Input } from 'ant-design-vue';

import { CaptchaImage } from '#/components/business/captcha';
import { useMultiAuthStore, usePublicConfigStore } from '#/store';

defineOptions({ name: 'TenantLogin' });

const publicConfigStore = usePublicConfigStore();
const multiAuthStore = useMultiAuthStore();

// 验证码组件引用
const captchaRef = ref<InstanceType<typeof CaptchaImage>>();
// 验证码用户输入
const captchaSolution = ref('');

// 首次访问加载租户公开配置
onMounted(() => {
  publicConfigStore.loadTenantConfig();
});

// 是否需要显示验证码
const showCaptcha = computed(() => publicConfigStore.shouldShowTenantCaptcha);

// 验证码难度
const captchaDifficulty = computed((): CaptchaDifficulty => {
  const difficulty = publicConfigStore.tenantCaptcha?.difficulty;
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
  const schema: VbenFormSchema[] = [
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
  return schema;
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
      publicConfigStore.tenantCaptcha?.provider ?? 'image';
  }

  const result = await multiAuthStore.authLogin(loginParams, 'tenant');

  // 登录失败时处理
  if (result.userInfo) {
    // 登录成功重置登录状态
    publicConfigStore.resetTenantLoginState();
  } else {
    publicConfigStore.incrementTenantLoginFail();

    // 如果后端要求显示验证码，设置强制要求状态
    if (result.captchaRequired) {
      publicConfigStore.setTenantCaptchaRequired(true);
    }

    // 刷新验证码
    refreshCaptcha();
  }
}
</script>

<template>
  <div>
    <AuthenticationLogin
      :form-schema="formSchema"
      :loading="multiAuthStore.loginLoading"
      :show-code-login="false"
      :show-forget-password="false"
      :show-qrcode-login="false"
      :show-register="false"
      :show-remember-me="false"
      :show-third-party-login="false"
      :title="$t('tenant.auth.welcomeBack')"
      :sub-title="$t('tenant.auth.subtitle')"
      @submit="handleLogin"
    >
      <!-- 验证码插槽 -->
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
              endpoint="tenant"
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

:deep(.flex-auto.overflow-hidden) {
  overflow: visible !important;
}

:deep(input) {
  border-radius: 10px !important;
  height: 44px !important;
  font-size: 14px !important;
  transition: border-color 0.3s ease, box-shadow 0.3s ease, background-color 0.3s ease !important;
}

:deep(input:hover) {
  border-color: hsl(var(--primary) / 0.5) !important;
  background-color: hsl(var(--primary) / 0.05) !important;
}

:deep(input:focus),
:deep(input:focus-visible) {
  border-color: hsl(var(--primary)) !important;
  box-shadow: 0 0 0 3px hsl(var(--primary) / 0.25), 0 4px 16px hsl(var(--primary) / 0.15) !important;
  outline: none !important;
  --tw-ring-shadow: none !important;
  --tw-ring-color: transparent !important;
  background-color: hsl(var(--primary) / 0.04) !important;
}

:deep(button[aria-label="login"]) {
  position: relative;
  height: 44px !important;
  border-radius: 10px !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  background: linear-gradient(135deg, hsl(var(--primary)) 0%, color-mix(in srgb, hsl(var(--primary)), #000 15%) 50%, color-mix(in srgb, hsl(var(--primary)), #000 30%) 100%) !important;
  border: none !important;
  box-shadow: 0 4px 14px hsl(var(--primary) / 0.3) !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
  overflow: hidden !important;
}

:deep(button[aria-label="login"])::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgb(255 255 255 / 20%),
    transparent
  );
  transition: left 0.5s ease;
}

:deep(button[aria-label="login"]:hover) {
  box-shadow: 0 6px 24px hsl(var(--primary) / 0.45) !important;
  transform: translateY(-2px) scale(1.01);
}

:deep(button[aria-label="login"]:hover)::before {
  left: 100%;
}

:deep(button[aria-label="login"]:active) {
  transform: translateY(0) scale(0.98) !important;
  box-shadow: 0 2px 8px hsl(var(--primary) / 0.3) !important;
}
</style>
