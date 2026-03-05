<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import { computed, ref } from 'vue';

import { AuthenticationLogin, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { Input } from 'ant-design-vue';

import { useMultiAuthStore } from '#/store';

defineOptions({ name: 'UserLogin' });

const multiAuthStore = useMultiAuthStore();

// 是否需要显示租户编码输入
const showTenantCode = ref(false);
// 租户编码输入值
const tenantCode = ref('');

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
  // 构建登录参数
  const loginParams: Record<string, unknown> = {
    password: values.password,
    username: values.username,
  };

  // 如果需要租户编码，添加到参数
  if (showTenantCode.value && tenantCode.value) {
    loginParams.tenantCode = tenantCode.value;
  }

  const result = await multiAuthStore.authLogin(loginParams, 'user');

  // 如果后端要求指定租户编码
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
    <!-- 租户编码插槽 -->
    <template v-if="showTenantCode" #form-extend>
      <div class="tenant-code-section">
        <Input
          v-model:value="tenantCode"
          :placeholder="$t('tenant.auth.tenantCodePlaceholder')"
          size="large"
        >
          <template #prefix>
            <span class="i-lucide-building text-muted-foreground"></span>
          </template>
        </Input>
      </div>
    </template>
  </AuthenticationLogin>
</template>

<style scoped>
.tenant-code-section {
  margin-bottom: 16px;
}
</style>
