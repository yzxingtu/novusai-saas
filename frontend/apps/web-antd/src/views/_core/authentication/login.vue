<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import { computed, ref } from 'vue';

import { AuthenticationLogin, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { Input } from 'ant-design-vue';

import { useMultiAuthStore } from '#/store';

defineOptions({ name: 'UserLogin' });

const multiAuthStore = useMultiAuthStore();

const showTenantCode = ref(false);
const tenantCode = ref('');

const formSchema = computed((): VbenFormSchema[] => {
  return [
    {
      component: 'VbenInput',
      componentProps: {
        placeholder: $t('user.auth.usernameOrEmailPlaceholder'),
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

async function handleLogin(values: Record<string, unknown>) {
  const loginParams: Record<string, unknown> = {
    password: values.password,
    username: values.username,
  };

  if (showTenantCode.value && tenantCode.value) {
    loginParams.tenantCode = tenantCode.value;
  }

  const result = await multiAuthStore.authLogin(loginParams, 'user');

  if (!result.userInfo && result.tenantCodeRequired) {
    showTenantCode.value = true;
  }
}
</script>

<template>
  <AuthenticationLogin
    :form-schema="formSchema"
    :loading="multiAuthStore.loginLoading"
    @submit="handleLogin"
  >
    <template v-if="showTenantCode" #form-extend>
      <div class="mb-4">
        <Input
          v-model:value="tenantCode"
          :placeholder="$t('user.auth.tenantCodePlaceholder')"
          size="large"
        >
          <template #prefix>
            <span class="i-lucide-building text-muted-foreground" />
          </template>
        </Input>
      </div>
    </template>
  </AuthenticationLogin>
</template>
