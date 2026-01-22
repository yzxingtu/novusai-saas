<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import { computed } from 'vue';

import { AuthenticationLogin, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { useMultiAuthStore } from '#/store';

defineOptions({ name: 'TenantLogin' });

const multiAuthStore = useMultiAuthStore();

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

async function handleLogin(values: Record<string, any>) {
  await multiAuthStore.authLogin(values, 'tenant');
}
</script>

<template>
  <div>
    <!-- 租户管理端标识 -->
    <div class="mb-6 flex items-center justify-center">
      <div class="flex items-center gap-2 rounded-full bg-primary/10 px-4 py-2">
        <span class="i-lucide-building-2 text-xl text-primary"></span>
        <span class="text-sm font-medium text-primary">
          {{ $t('authentication.tenantAdmin') }}
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
      title="租户管理后台"
      :sub-title="$t('authentication.tenantAdminDesc')"
      @submit="handleLogin"
    />
  </div>
</template>
