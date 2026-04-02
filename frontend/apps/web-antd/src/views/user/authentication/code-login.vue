<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';
import type { Recordable } from '@vben/types';

import type { CaptchaDifficulty } from '#/api/public/captcha';
import type { CaptchaAdapterExpose } from '#/components/business/captcha';

import { computed, onMounted, ref, useTemplateRef } from 'vue';
import { useRouter } from 'vue-router';

import { AuthenticationCodeLogin, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { message } from 'ant-design-vue';

import { userSendLoginCodeApi } from '#/api/user/auth';
import { CaptchaProvider } from '#/components/business/captcha';
import { useMultiAuthStore, usePublicConfigStore } from '#/store';
import { shouldRequestTenantPublicConfig } from '#/utils/public-config-domain';

defineOptions({ name: 'CodeLogin' });

const router = useRouter();
const publicConfigStore = usePublicConfigStore();
const multiAuthStore = useMultiAuthStore();

const CODE_LENGTH = 6;
const loginRef =
  useTemplateRef<InstanceType<typeof AuthenticationCodeLogin>>('loginRef');
const captchaRef = ref<CaptchaAdapterExpose>();
const loading = ref(false);
const pendingCaptchaAction = ref<'login' | 'sendCode' | null>(null);
const pendingLoginValues = ref<null | Recordable<unknown>>(null);
const pendingSendEmail = ref<null | string>(null);

onMounted(async () => {
  await publicConfigStore.detectDomainType().catch(() => {});
  await (shouldRequestTenantPublicConfig(
    publicConfigStore.isDomainDetected,
    publicConfigStore.isDomainTenantDomain,
  )
    ? publicConfigStore.loadTenantConfig()
    : publicConfigStore.loadPlatformConfig());

  if (!showEmailCodeLogin.value) {
    await router.replace('/auth/login');
  }
});

const showEmailCodeLogin = computed(() => {
  return Boolean(
    publicConfigStore.tenantConfig?.login.allowedMethods.includes('email'),
  );
});

const showCaptcha = computed(() => publicConfigStore.shouldShowUserCaptcha);

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

const captchaProvider = computed(() => {
  return publicConfigStore.tenantCaptcha?.provider ?? 'image';
});

const loginSubtitle = computed(() => {
  return (
    publicConfigStore.tenantBrand?.siteDescription ||
    $t('user.auth.codeLoginDesc')
  );
});

function refreshCaptcha() {
  captchaRef.value?.refresh();
}

function getCaptchaPayload() {
  if (!showCaptcha.value || !captchaRef.value) {
    return null;
  }

  const result = captchaRef.value.getResult();
  if (!result) {
    return null;
  }

  return {
    captchaChallengeId: result.challengeId,
    captchaProviderCode: publicConfigStore.tenantCaptcha?.provider ?? 'image',
    captchaSolution: result.captchaCode,
  };
}

async function handleCaptchaVerified() {
  const action = pendingCaptchaAction.value;
  pendingCaptchaAction.value = null;

  if (action === 'sendCode' && pendingSendEmail.value) {
    const email = pendingSendEmail.value;
    pendingSendEmail.value = null;
    await sendCode(email);
    return;
  }

  if (action === 'login' && pendingLoginValues.value) {
    const values = pendingLoginValues.value;
    pendingLoginValues.value = null;
    await handleLogin(values);
  }
}

async function sendCode(email: string) {
  const captchaPayload = getCaptchaPayload();
  if (showCaptcha.value && !captchaPayload) {
    pendingCaptchaAction.value = 'sendCode';
    pendingSendEmail.value = email;
    throw new Error('captcha_required');
  }

  loading.value = true;
  try {
    await userSendLoginCodeApi({
      channel: 'email',
      email,
      ...captchaPayload,
    });
    message.success({
      content: $t('user.auth.codeSentDesc'),
      duration: 3,
    });
  } finally {
    loading.value = false;
    if (showCaptcha.value) {
      refreshCaptcha();
    }
  }
}

const formSchema = computed((): VbenFormSchema[] => {
  return [
    {
      component: 'VbenInput',
      componentProps: {
        placeholder: $t('user.auth.emailPlaceholder'),
      },
      fieldName: 'email',
      label: $t('user.auth.email'),
      rules: z
        .string()
        .min(1, { message: $t('user.auth.emailRequired') })
        .email({ message: $t('user.auth.emailInvalid') }),
    },
    {
      component: 'VbenPinInput',
      componentProps: {
        codeLength: CODE_LENGTH,
        createText: (countdown: number) => {
          return countdown > 0
            ? $t('authentication.sendText', [countdown])
            : $t('user.auth.sendCode');
        },
        handleSendCode: async () => {
          const formApi = loginRef.value?.getFormApi();
          if (!formApi) {
            throw new Error('formApi is not ready');
          }
          await formApi.validateField('email');
          const isEmailReady = await formApi.isFieldValid('email');
          if (!isEmailReady) {
            throw new Error('Email is not ready');
          }
          const { email } = await formApi.getValues();
          await sendCode(String(email ?? '').trim());
        },
        placeholder: $t('user.auth.codePlaceholder'),
      },
      fieldName: 'code',
      label: $t('user.auth.verificationCode'),
      rules: z.string().length(CODE_LENGTH, {
        message: $t('user.auth.codeRequired'),
      }),
    },
  ];
});

async function handleLogin(values: Recordable<unknown>) {
  const email = String(values.email ?? '').trim();
  const code = String(values.code ?? '').trim();

  const result = await multiAuthStore.authCodeLogin(
    {
      channel: 'email',
      code,
      email,
    },
    'user',
  );

  if (result.userInfo) {
    publicConfigStore.resetUserLoginState();
    return;
  }

  publicConfigStore.incrementUserLoginFail();
  if (result.captchaRequired) {
    publicConfigStore.setUserCaptchaRequired(true);
  }
  refreshCaptcha();
}
</script>

<template>
  <AuthenticationCodeLogin
    ref="loginRef"
    :form-schema="formSchema"
    :loading="loading || multiAuthStore.loginLoading"
    :title="$t('user.auth.codeLoginTitle')"
    :sub-title="loginSubtitle"
    :submit-button-text="$t('user.auth.signInWithCode')"
    @submit="handleLogin"
  >
    <template v-if="showCaptcha" #form-extend>
      <div class="mb-4">
        <CaptchaProvider
          ref="captchaRef"
          endpoint="user"
          action="login"
          :provider="captchaProvider"
          :difficulty="captchaDifficulty"
          @verified="handleCaptchaVerified"
        />
      </div>
    </template>
  </AuthenticationCodeLogin>
</template>
