<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import type { CaptchaDifficulty } from '#/api/public/captcha';
import type { CaptchaAdapterExpose } from '#/components/business/captcha';

import { computed, onMounted, ref } from 'vue';

import { AuthenticationLogin, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { CaptchaProvider } from '#/components/business/captcha';
import { useMultiAuthStore, usePublicConfigStore } from '#/store';
import { shouldRequestTenantPublicConfig } from '#/utils/public-config-domain';

defineOptions({ name: 'TenantLogin' });

const publicConfigStore = usePublicConfigStore();
const multiAuthStore = useMultiAuthStore();

// Captcha component ref / 验证码组件引用
const captchaRef = ref<CaptchaAdapterExpose>();
const pendingLoginValues = ref<null | Record<string, unknown>>(null);

// Load tenant public config only on tenant-domain style entry / 仅在企业域入口加载企业公开配置
onMounted(async () => {
  await publicConfigStore.detectDomainType().catch(() => {});
  if (
    shouldRequestTenantPublicConfig(
      publicConfigStore.isDomainDetected,
      publicConfigStore.isDomainTenantDomain,
    )
  ) {
    await publicConfigStore.loadTenantConfig();
  }
});

// Whether to show captcha / 是否需要显示验证码
const showCaptcha = computed(() => publicConfigStore.shouldShowTenantCaptcha);

// Captcha difficulty / 验证码难度
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

// Captcha provider type / 验证码提供商类型
const captchaProvider = computed(() => {
  return publicConfigStore.tenantCaptcha?.provider ?? 'image';
});

const loginSubtitle = computed(() => {
  return (
    publicConfigStore.tenantBrand?.siteDescription || $t('tenant.auth.subtitle')
  );
});

// Refresh captcha / 刷新验证码
function refreshCaptcha() {
  captchaRef.value?.refresh();
}

function handleCaptchaVerified() {
  if (!pendingLoginValues.value || multiAuthStore.loginLoading) {
    return;
  }
  const nextValues = pendingLoginValues.value;
  pendingLoginValues.value = null;
  void handleLogin(nextValues);
}

async function handleLogin(values: Record<string, unknown>) {
  // Build login params / 构建登录参数
  const loginParams: Record<string, unknown> = {
    password: values.password,
    username: values.username,
  };

  // If captcha required, get unified result from CaptchaProvider / 如果需要验证码
  if (showCaptcha.value && captchaRef.value) {
    const result = captchaRef.value.getResult();
    if (!result) {
      pendingLoginValues.value = { ...values };
      return;
    }
    pendingLoginValues.value = null;
    loginParams.captchaChallengeId = result.challengeId;
    loginParams.captchaSolution = result.captchaCode;
    loginParams.captchaType = result.provider;
    loginParams.captchaProviderCode =
      publicConfigStore.tenantCaptcha?.provider ?? 'image';
  }

  const result = await multiAuthStore.authLogin(loginParams, 'tenant');

  // Handle login failure / 登录失败时处理
  if (result.userInfo) {
    // Reset login state on success / 登录成功重置登录状态
    publicConfigStore.resetTenantLoginState();
  } else {
    publicConfigStore.incrementTenantLoginFail();

    // If backend requires captcha, set forced requirement / 如果后端要求显示验证码
    if (result.captchaRequired) {
      publicConfigStore.setTenantCaptchaRequired(true);
    }

    // Refresh captcha / 刷新验证码
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
      :sub-title="loginSubtitle"
      @submit="handleLogin"
    >
      <!-- Captcha slot / 验证码插槽 -->
      <template v-if="showCaptcha" #form-extend>
        <div class="captcha-section">
          <CaptchaProvider
            ref="captchaRef"
            endpoint="tenant"
            action="login"
            :provider="captchaProvider"
            :difficulty="captchaDifficulty"
            @verified="handleCaptchaVerified"
          />
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

:deep(.flex-auto.overflow-hidden) {
  overflow: visible !important;
}

:deep(input) {
  height: 44px !important;
  font-size: 14px !important;
  border-radius: 10px !important;
  transition:
    border-color 0.3s ease,
    box-shadow 0.3s ease,
    background-color 0.3s ease !important;
}

:deep(input:hover) {
  background-color: hsl(var(--primary) / 5%) !important;
  border-color: hsl(var(--primary) / 50%) !important;
}

:deep(input:focus),
:deep(input:focus-visible) {
  --tw-ring-shadow: none !important;
  --tw-ring-color: transparent !important;

  outline: none !important;
  background-color: hsl(var(--primary) / 4%) !important;
  border-color: hsl(var(--primary)) !important;
  box-shadow:
    0 0 0 3px hsl(var(--primary) / 25%),
    0 4px 16px hsl(var(--primary) / 15%) !important;
}

:deep(button[aria-label='login']) {
  position: relative;
  height: 44px !important;
  overflow: hidden !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  background: linear-gradient(
    135deg,
    hsl(var(--primary)) 0%,
    color-mix(in srgb, hsl(var(--primary)), #000 15%) 50%,
    color-mix(in srgb, hsl(var(--primary)), #000 30%) 100%
  ) !important;
  border: none !important;
  border-radius: 10px !important;
  box-shadow: 0 4px 14px hsl(var(--primary) / 30%) !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

:deep(button[aria-label='login'])::before {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  content: '';
  background: linear-gradient(
    90deg,
    transparent,
    rgb(255 255 255 / 20%),
    transparent
  );
  transition: left 0.5s ease;
}

:deep(button[aria-label='login']:hover) {
  box-shadow: 0 6px 24px hsl(var(--primary) / 45%) !important;
  transform: translateY(-2px) scale(1.01);
}

:deep(button[aria-label='login']:hover)::before {
  left: 100%;
}

:deep(button[aria-label='login']:active) {
  box-shadow: 0 2px 8px hsl(var(--primary) / 30%) !important;
  transform: translateY(0) scale(0.98) !important;
}
</style>
