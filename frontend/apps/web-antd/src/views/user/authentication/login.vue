<script lang="ts" setup>
import type { CaptchaDifficulty } from '#/api/public/captcha';
import type { CaptchaAdapterExpose } from '#/components/business/captcha';

import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Button, Form, FormItem, Input, InputPassword } from 'ant-design-vue';

import { CaptchaProvider } from '#/components/business/captcha';
import { $t } from '#/locales';
import { useMultiAuthStore, usePublicConfigStore } from '#/store';

defineOptions({ name: 'UserLogin' });

const router = useRouter();
const publicConfigStore = usePublicConfigStore();
const multiAuthStore = useMultiAuthStore();

const captchaRef = ref<CaptchaAdapterExpose>();

const formState = reactive({
  password: '',
  username: '',
});

onMounted(() => {
  publicConfigStore.loadTenantConfig();
});

const showCaptcha = computed(() => publicConfigStore.shouldShowUserCaptcha);
const registrationEnabled = computed(() => publicConfigStore.isRegistrationEnabled);

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

function refreshCaptcha() {
  captchaRef.value?.refresh();
}

async function handleLogin() {
  const loginParams: Record<string, unknown> = {
    password: formState.password,
    username: formState.username,
  };

  if (showCaptcha.value && captchaRef.value) {
    const result = captchaRef.value.getResult();
    if (!result) return;
    loginParams.captchaChallengeId = result.challengeId;
    loginParams.captchaSolution = result.captchaCode;
    loginParams.captchaType = result.provider;
    loginParams.captchaProviderCode =
      publicConfigStore.tenantCaptcha?.provider ?? 'image';
  }

  const result = await multiAuthStore.authLogin(loginParams, 'user');

  if (result.userInfo) {
    publicConfigStore.resetUserLoginState();
  } else {
    publicConfigStore.incrementUserLoginFail();
    if (result.captchaRequired) {
      publicConfigStore.setUserCaptchaRequired(true);
    }
    refreshCaptcha();
  }
}
</script>

<template>
  <div>
    <!-- Title -->
    <div class="mb-6 text-center">
      <h1 class="text-xl font-bold text-foreground">
        {{ $t('user.auth.welcomeBack') }}
      </h1>
      <p class="mt-1 text-sm text-muted-foreground">
        {{ $t('user.auth.subtitle') }}
      </p>
    </div>

    <!-- Login Form -->
    <Form
      :model="formState"
      layout="vertical"
      autocomplete="off"
      @finish="handleLogin"
    >
      <FormItem
        name="username"
        :rules="[{ required: true, message: $t('user.auth.usernameRequired') }]"
      >
        <Input
          v-model:value="formState.username"
          size="large"
          :placeholder="$t('user.auth.usernameOrEmailPlaceholder')"
          class="auth-input"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:user" class="size-4 text-muted-foreground" />
          </template>
        </Input>
      </FormItem>

      <FormItem
        name="password"
        :rules="[{ required: true, message: $t('user.auth.passwordRequired') }]"
      >
        <InputPassword
          v-model:value="formState.password"
          size="large"
          :placeholder="$t('user.auth.passwordPlaceholder')"
          class="auth-input"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:lock" class="size-4 text-muted-foreground" />
          </template>
        </InputPassword>
      </FormItem>

      <!-- Forgot password link -->
      <div class="-mt-2 mb-4 flex justify-end">
        <button
          type="button"
          class="text-xs text-muted-foreground transition-colors hover:text-primary"
          @click="router.push('/auth/forget-password')"
        >
          {{ $t('user.auth.forgotPassword') }}
        </button>
      </div>

      <!-- Captcha -->
      <div v-if="showCaptcha" class="mb-4">
        <CaptchaProvider
          ref="captchaRef"
          endpoint="user"
          action="login"
          :provider="captchaProvider"
          :difficulty="captchaDifficulty"
        />
      </div>

      <!-- Submit -->
      <FormItem>
        <Button
          type="primary"
          html-type="submit"
          size="large"
          block
          :loading="multiAuthStore.loginLoading"
          class="auth-btn"
        >
          <template #icon>
            <IconifyIcon icon="lucide:log-in" class="size-4" />
          </template>
          {{ $t('user.auth.signIn') }}
        </Button>
      </FormItem>
    </Form>

    <!-- Register link -->
    <div v-if="registrationEnabled" class="mt-4 text-center text-sm text-muted-foreground">
      {{ $t('user.auth.noAccount') }}
      <button
        type="button"
        class="font-medium text-primary transition-colors hover:text-primary/80"
        @click="router.push('/auth/register')"
      >
        {{ $t('user.auth.signUp') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
@import './auth-shared.css';
</style>
