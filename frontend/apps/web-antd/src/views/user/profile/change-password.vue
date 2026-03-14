<script setup lang="ts">
/**
 * 用户修改密码页面 - 现代化设计
 */
import type { Rule } from 'ant-design-vue/es/form';

import { computed, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Form,
  FormItem,
  Input,
  message,
} from 'ant-design-vue';

import { userChangePasswordApi } from '#/api/user/auth';
import { $t } from '#/locales';

defineOptions({ name: 'UserChangePassword' });

const router = useRouter();
const saving = ref(false);

const formState = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
});

const formRules = computed<Record<string, Rule[]>>(() => ({
  oldPassword: [
    {
      required: true,
      message: $t('user.profile.placeholder.inputOldPassword'),
    },
  ],
  newPassword: [
    {
      required: true,
      message: $t('user.profile.placeholder.inputNewPassword'),
    },
    {
      min: 6,
      message: $t('user.auth.passwordMinLength'),
    },
  ],
  confirmPassword: [
    {
      required: true,
      message: $t('user.profile.placeholder.inputConfirmPassword'),
    },
    {
      validator: (_rule: unknown, value: string) => {
        if (value && value !== formState.newPassword) {
          return Promise.reject(
            new Error($t('authentication.confirmPasswordTip')),
          );
        }
        return Promise.resolve();
      },
    },
  ],
}));

const formRef = ref();

async function handleSubmit() {
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }

  saving.value = true;
  try {
    await userChangePasswordApi({
      oldPassword: formState.oldPassword,
      newPassword: formState.newPassword,
      confirmPassword: formState.confirmPassword,
    });
    message.success($t('user.profile.messages.changePasswordSuccess'));
    formState.oldPassword = '';
    formState.newPassword = '';
    formState.confirmPassword = '';
    formRef.value?.resetFields();
    router.push('/settings/profile');
  } catch {
    // Error handled by request interceptor / 错误由请求拦截器处理
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Security Info Banner -->
    <div
      class="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4"
    >
      <div
        class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10"
      >
        <IconifyIcon icon="lucide:shield-check" class="size-5 text-primary" />
      </div>
      <div>
        <h3 class="text-sm font-medium text-foreground">
          {{ $t('user.profile.changePassword') }}
        </h3>
        <p class="mt-0.5 text-xs text-muted-foreground">
          {{ $t('user.profile.changePasswordDesc') }}
        </p>
      </div>
    </div>

    <!-- Password Form Card -->
    <div class="rounded-xl border border-border bg-card">
      <div class="px-6 py-5">
        <Form
          ref="formRef"
          layout="vertical"
          :model="formState"
          :rules="formRules"
          class="max-w-lg"
        >
          <FormItem
            :label="$t('user.profile.oldPassword')"
            name="oldPassword"
          >
            <Input.Password
              v-model:value="formState.oldPassword"
              :placeholder="$t('user.profile.placeholder.inputOldPassword')"
              size="large"
            />
          </FormItem>

          <div class="my-5 h-px bg-border" />

          <FormItem
            :label="$t('user.profile.newPassword')"
            name="newPassword"
          >
            <Input.Password
              v-model:value="formState.newPassword"
              :placeholder="$t('user.profile.placeholder.inputNewPassword')"
              size="large"
            />
          </FormItem>

          <FormItem
            :label="$t('user.profile.confirmPassword')"
            name="confirmPassword"
          >
            <Input.Password
              v-model:value="formState.confirmPassword"
              :placeholder="$t('user.profile.placeholder.inputConfirmPassword')"
              size="large"
            />
          </FormItem>
        </Form>
      </div>
      <div class="flex items-center justify-end border-t border-border px-6 py-4">
        <Button
          type="primary"
          :loading="saving"
          @click="handleSubmit"
        >
          <span class="flex items-center gap-1.5">
            <IconifyIcon icon="lucide:save" class="size-4" />
            {{ $t('common.save') }}
          </span>
        </Button>
      </div>
    </div>
  </div>
</template>
