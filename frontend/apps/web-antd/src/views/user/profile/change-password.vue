<script setup lang="ts">
/**
 * 用户修改密码页面
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
    // Reset form
    formState.oldPassword = '';
    formState.newPassword = '';
    formState.confirmPassword = '';
    formRef.value?.resetFields();
  } catch {
    // Error handled by request interceptor
  } finally {
    saving.value = false;
  }
}

function goBack() {
  router.push('/profile');
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <button
        class="flex size-8 items-center justify-center rounded-md transition-colors hover:bg-accent"
        @click="goBack"
      >
        <IconifyIcon icon="lucide:arrow-left" class="size-4" />
      </button>
      <div>
        <h1 class="text-lg font-semibold text-foreground">
          {{ $t('user.profile.changePassword') }}
        </h1>
        <p class="text-xs text-muted-foreground">
          {{ $t('user.profile.changePasswordDesc') }}
        </p>
      </div>
    </div>

    <!-- Form Card -->
    <div class="rounded-lg border border-border bg-card p-6">
      <Form
        ref="formRef"
        layout="vertical"
        :model="formState"
        :rules="formRules"
        class="mx-auto max-w-md"
      >
        <FormItem
          :label="$t('user.profile.oldPassword')"
          name="oldPassword"
        >
          <Input.Password
            v-model:value="formState.oldPassword"
            :placeholder="$t('user.profile.placeholder.inputOldPassword')"
          />
        </FormItem>

        <FormItem
          :label="$t('user.profile.newPassword')"
          name="newPassword"
        >
          <Input.Password
            v-model:value="formState.newPassword"
            :placeholder="$t('user.profile.placeholder.inputNewPassword')"
          />
        </FormItem>

        <FormItem
          :label="$t('user.profile.confirmPassword')"
          name="confirmPassword"
        >
          <Input.Password
            v-model:value="formState.confirmPassword"
            :placeholder="$t('user.profile.placeholder.inputConfirmPassword')"
          />
        </FormItem>

        <FormItem>
          <div class="flex gap-3">
            <Button
              type="primary"
              :loading="saving"
              @click="handleSubmit"
            >
              {{ $t('common.save') }}
            </Button>
            <Button @click="goBack">
              {{ $t('common.cancel') }}
            </Button>
          </div>
        </FormItem>
      </Form>
    </div>
  </div>
</template>
