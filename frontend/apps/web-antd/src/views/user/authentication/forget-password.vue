<script lang="ts" setup>
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Form,
  FormItem,
  Input,
  InputPassword,
  notification,
} from 'ant-design-vue';

import { userApi } from '#/api';
import { $t } from '#/locales';

defineOptions({ name: 'UserForgetPassword' });

const router = useRouter();
const loading = ref(false);
const codeSent = ref(false);
const emailValue = ref('');

const formState = reactive({
  code: '',
  confirmPassword: '',
  email: '',
  newPassword: '',
});

function validateConfirmPassword(_rule: unknown, value: string) {
  if (!value) {
    return Promise.reject($t('user.auth.confirmPasswordRequired'));
  }
  if (value !== formState.newPassword) {
    return Promise.reject($t('user.auth.confirmPasswordMismatch'));
  }
  return Promise.resolve();
}

async function handleSubmit() {
  try {
    loading.value = true;

    if (!codeSent.value) {
      await userApi.userForgotPasswordApi({
        email: formState.email,
      });

      emailValue.value = formState.email;
      codeSent.value = true;

      notification.success({
        description: $t('user.auth.codeSentDesc'),
        duration: 5,
        message: $t('user.auth.codeSent'),
      });
    } else {
      await userApi.userResetPasswordApi({
        code: formState.code,
        confirmPassword: formState.confirmPassword,
        email: emailValue.value,
        newPassword: formState.newPassword,
      });

      notification.success({
        description: $t('user.auth.resetSuccessDesc'),
        duration: 3,
        message: $t('user.auth.resetSuccess'),
      });

      await router.push('/auth/login');
    }
  } catch {
    // 错误已由 axios 拦截器处理并显示
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
        {{ $t('user.auth.resetPasswordTitle') }}
      </h1>
      <p class="mt-1 text-sm text-muted-foreground">
        {{ $t('user.auth.resetPasswordDesc') }}
      </p>
    </div>

    <!-- Form -->
    <Form
      :model="formState"
      layout="vertical"
      autocomplete="off"
      @finish="handleSubmit"
    >
      <!-- Step 1: Email -->
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
          :disabled="codeSent"
          class="auth-input"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:mail" class="size-4 text-muted-foreground" />
          </template>
        </Input>
      </FormItem>

      <!-- Step 2: Code + New Password (shown after code sent) -->
      <template v-if="codeSent">
        <FormItem
          name="code"
          :rules="[
            { required: true, message: $t('user.auth.codeRequired') },
            { min: 4, message: $t('user.auth.codeRequired') },
          ]"
        >
          <Input
            v-model:value="formState.code"
            size="large"
            :placeholder="$t('user.auth.codePlaceholder')"
            class="auth-input"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:key-round" class="size-4 text-muted-foreground" />
            </template>
          </Input>
        </FormItem>

        <FormItem
          name="newPassword"
          :rules="[
            { required: true, message: $t('user.auth.passwordRequired') },
            { min: 6, message: $t('user.auth.passwordMinLength') },
          ]"
        >
          <InputPassword
            v-model:value="formState.newPassword"
            size="large"
            :placeholder="$t('user.auth.newPasswordPlaceholder')"
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
      </template>

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
            <IconifyIcon
              :icon="codeSent ? 'lucide:check' : 'lucide:send'"
              class="size-4"
            />
          </template>
          {{ codeSent ? $t('user.auth.resetPassword') : $t('user.auth.sendCode') }}
        </Button>
      </FormItem>
    </Form>

    <!-- Back to login -->
    <div class="mt-4 text-center">
      <button
        type="button"
        class="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        @click="router.push('/auth/login')"
      >
        <IconifyIcon icon="lucide:arrow-left" class="size-3.5" />
        {{ $t('user.auth.backToLogin') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.auth-input :deep(.ant-input),
.auth-input :deep(.ant-input-password) {
  border-radius: 10px !important;
  height: 44px !important;
}

.auth-input :deep(.ant-input-affix-wrapper) {
  border-radius: 10px !important;
  padding: 0 12px !important;
}

.auth-btn {
  height: 44px !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  font-size: 15px !important;
}
</style>
