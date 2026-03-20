<script lang="ts" setup>
import type { CaptchaDifficulty } from '#/api/public/captcha';
import type { CaptchaAdapterExpose } from '#/components/business/captcha';

import { computed, onMounted, reactive, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Checkbox,
  Form,
  FormItem,
  Input,
  InputPassword,
  message,
  notification,
} from 'ant-design-vue';

import { userApi } from '#/api';
import { CaptchaProvider } from '#/components/business/captcha';
import { $t } from '#/locales';
import { usePublicConfigStore } from '#/store';

defineOptions({ name: 'UserRegister' });

const router = useRouter();
const loading = ref(false);
const publicConfigStore = usePublicConfigStore();

const captchaRef = ref<CaptchaAdapterExpose>();
const showCaptcha = ref(false);

const formState = reactive({
  agreePolicy: false,
  confirmPassword: '',
  email: '',
  password: '',
  username: '',
});

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

const showApprovalHint = computed(
  () => publicConfigStore.isRegistrationApprovalRequired,
);

const captchaProvider = computed(() => {
  return publicConfigStore.tenantCaptcha?.provider ?? 'image';
});

const privacyUrl = computed(() => publicConfigStore.tenantConfig?.privacyPolicyUrl);
const termsUrl = computed(() => publicConfigStore.tenantConfig?.termsUrl);
const privacyInternal = computed(
  () => publicConfigStore.tenantConfig?.privacyPolicyInternal === true,
);
const termsInternal = computed(
  () => publicConfigStore.tenantConfig?.termsInternal === true,
);

onMounted(async () => {
  await publicConfigStore.loadTenantConfig();
  if (!publicConfigStore.isRegistrationEnabled) {
    message.warning($t('user.auth.registrationDisabled'));
    router.replace('/auth/login');
    return;
  }
  showCaptcha.value = publicConfigStore.shouldShowTenantCaptcha;
});

function refreshCaptcha() {
  captchaRef.value?.refresh();
}

function validateConfirmPassword(_rule: unknown, value: string) {
  if (!value) {
    return Promise.reject($t('user.auth.confirmPasswordRequired'));
  }
  if (value !== formState.password) {
    return Promise.reject($t('user.auth.confirmPasswordMismatch'));
  }
  return Promise.resolve();
}

function validateAgreePolicy(_rule: unknown, value: boolean) {
  return value
    ? Promise.resolve()
    : Promise.reject($t('user.auth.agreeRequired'));
}

async function handleSubmit() {
  try {
    loading.value = true;

    const params: userApi.RegisterParams = {
      confirmPassword: formState.confirmPassword,
      email: formState.email,
      password: formState.password,
      username: formState.username,
    };

    if (showCaptcha.value && captchaRef.value) {
      const captchaResult = captchaRef.value.getResult();
      if (!captchaResult) return;
      params.captchaChallengeId = captchaResult.challengeId;
      params.captchaSolution = captchaResult.captchaCode;
      params.captchaProviderCode =
        publicConfigStore.tenantCaptcha?.provider ?? 'image';
    }

    const result = await userApi.userRegisterApi(params);
    const isPending = result.approvalStatus === 'pending';

    notification.success({
      description: isPending
        ? $t('user.auth.registerPendingDesc')
        : $t('user.auth.registerSuccessDesc'),
      duration: isPending ? 5 : 3,
      message: $t('user.auth.registerSuccess'),
    });

    await router.push('/auth/login');
  } catch (error: unknown) {
    const err = error as {
      response?: { data?: { code?: number; data?: { captcha_required?: boolean; errors?: Array<{ captcha_required?: boolean }> }; message?: string } };
    };
    const responseData = err?.response?.data;
    const captchaRequired =
      responseData?.data?.captcha_required ||
      responseData?.data?.errors?.[0]?.captcha_required;
    if (captchaRequired) {
      showCaptcha.value = true;
    }
    // Show backend error message / 显示后端返回的错误信息
    if (responseData?.message) {
      message.error(responseData.message);
    }
    refreshCaptcha();
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div>
    <!-- Title -->
    <div class="mb-6 text-center">
      <h1 class="text-xl font-bold text-foreground">
        {{ $t('user.auth.signUp') }}
      </h1>
      <p class="mt-1 text-sm text-muted-foreground">
        {{ $t('user.auth.subtitle') }}
      </p>
    </div>

    <!-- Approval hint -->
    <Alert
      v-if="showApprovalHint"
      type="info"
      :message="$t('user.auth.registrationApprovalHint')"
      show-icon
      class="mb-4"
    />

    <!-- Register Form -->
    <Form
      :model="formState"
      layout="vertical"
      autocomplete="off"
      @finish="handleSubmit"
    >
      <FormItem
        name="username"
        :rules="[
          { required: true, message: $t('user.auth.usernameRequired') },
          { min: 2, message: $t('user.auth.usernameRequired') },
        ]"
      >
        <Input
          v-model:value="formState.username"
          size="large"
          :placeholder="$t('user.auth.usernamePlaceholder')"
          class="auth-input"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:user" class="size-4 text-muted-foreground" />
          </template>
        </Input>
      </FormItem>

      <FormItem
        name="email"
        :rules="[
          { required: true, message: $t('user.auth.emailRequired') },
          { type: 'email', message: $t('user.auth.emailInvalid') },
        ]"
      >
        <Input
          v-model:value="formState.email"
          size="large"
          :placeholder="$t('user.auth.emailPlaceholder')"
          class="auth-input"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:mail" class="size-4 text-muted-foreground" />
          </template>
        </Input>
      </FormItem>

      <FormItem
        name="password"
        :rules="[
          { required: true, message: $t('user.auth.passwordRequired') },
          { min: 6, message: $t('user.auth.passwordMinLength') },
        ]"
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

      <FormItem
        name="confirmPassword"
        :rules="[{ validator: validateConfirmPassword }]"
      >
        <InputPassword
          v-model:value="formState.confirmPassword"
          size="large"
          :placeholder="$t('user.auth.confirmPasswordPlaceholder')"
          class="auth-input"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:lock-keyhole" class="size-4 text-muted-foreground" />
          </template>
        </InputPassword>
      </FormItem>

      <!-- Agree policy -->
      <FormItem
        name="agreePolicy"
        :rules="[{ validator: validateAgreePolicy }]"
      >
        <Checkbox v-model:checked="formState.agreePolicy">
          <span class="text-sm text-muted-foreground">
            {{ $t('user.auth.agreePrefix') }}
            <!-- 外链优先；无外链时再走站内富文本 -->
            <a
              v-if="privacyUrl"
              :href="privacyUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="text-primary hover:text-primary/80"
            >{{ $t('user.auth.privacyPolicy') }}</a>
            <RouterLink
              v-else-if="privacyInternal"
              to="/auth/legal/privacy"
              class="text-primary hover:text-primary/80"
            >{{ $t('user.auth.privacyPolicy') }}</RouterLink>
            <span
              v-else
              class="text-muted-foreground"
            >{{ $t('user.auth.privacyPolicy') }}</span>
            &amp;
            <a
              v-if="termsUrl"
              :href="termsUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="text-primary hover:text-primary/80"
            >{{ $t('user.auth.termsOfService') }}</a>
            <RouterLink
              v-else-if="termsInternal"
              to="/auth/legal/terms"
              class="text-primary hover:text-primary/80"
            >{{ $t('user.auth.termsOfService') }}</RouterLink>
            <span
              v-else
              class="text-muted-foreground"
            >{{ $t('user.auth.termsOfService') }}</span>
          </span>
        </Checkbox>
      </FormItem>

      <!-- Captcha -->
      <div v-if="showCaptcha" class="mb-4">
        <CaptchaProvider
          ref="captchaRef"
          endpoint="user"
          action="register"
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
          :loading="loading"
          class="auth-btn"
        >
          <template #icon>
            <IconifyIcon icon="lucide:user-plus" class="size-4" />
          </template>
          {{ $t('user.auth.signUp') }}
        </Button>
      </FormItem>
    </Form>

    <!-- Login link -->
    <div class="mt-4 text-center text-sm text-muted-foreground">
      {{ $t('user.auth.hasAccount') }}
      <button
        type="button"
        class="font-medium text-primary transition-colors hover:text-primary/80"
        @click="router.push('/auth/login')"
      >
        {{ $t('user.auth.signIn') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
@import './auth-shared.css';
</style>
