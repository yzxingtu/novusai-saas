<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import type { CaptchaDifficulty } from '#/api/public/captcha';

import { computed, onMounted, ref } from 'vue';

import { AuthenticationLogin, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { Input } from 'ant-design-vue';

import { CaptchaImage } from '#/components/business/captcha';
import { useMultiAuthStore, usePublicConfigStore } from '#/store';

defineOptions({ name: 'TenantLogin' });

const publicConfigStore = usePublicConfigStore();
const multiAuthStore = useMultiAuthStore();

// 验证码组件引用
const captchaRef = ref<InstanceType<typeof CaptchaImage>>();
// 验证码用户输入
const captchaSolution = ref('');
// 是否需要显示租户编码输入
const showTenantCode = ref(false);
// 租户编码输入值
const tenantCode = ref('');

// 首次访问加载租户公开配置
onMounted(() => {
  publicConfigStore.loadTenantConfig();
});

// 是否需要显示验证码
const showCaptcha = computed(() => publicConfigStore.shouldShowTenantCaptcha);

// 验证码难度
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

// 刷新验证码
function refreshCaptcha() {
  captchaSolution.value = '';
  captchaRef.value?.refresh();
}

async function handleLogin(values: Record<string, any>) {
  // 构建登录参数
  const loginParams: Record<string, any> = {
    password: values.password,
    username: values.username,
  };

  // 如果需要租户编码，添加到参数
  if (showTenantCode.value && tenantCode.value) {
    loginParams.tenantCode = tenantCode.value;
  }

  // 如果需要验证码，添加验证码参数
  if (showCaptcha.value && captchaRef.value) {
    if (!captchaSolution.value) {
      // 验证码未填写，不提交
      return;
    }
    loginParams.captchaChallengeId = captchaRef.value.getChallengeId();
    loginParams.captchaSolution = captchaSolution.value;
    loginParams.captchaType = 'image';
    // 使用缓存的验证码提供方标识，降级为 'image'
    loginParams.captchaProviderCode =
      publicConfigStore.tenantCaptcha?.provider ?? 'image';
  }

  const result = await multiAuthStore.authLogin(loginParams, 'tenant');

  // 登录失败时处理
  if (result.userInfo) {
    // 登录成功重置登录状态
    publicConfigStore.resetTenantLoginState();
  } else {
    publicConfigStore.incrementTenantLoginFail();

    // 如果后端要求显示验证码，设置强制要求状态
    if (result.captchaRequired) {
      publicConfigStore.setTenantCaptchaRequired(true);
    }

    // 如果后端要求指定租户编码
    if (result.tenantCodeRequired) {
      showTenantCode.value = true;
    }

    // 刷新验证码
    refreshCaptcha();
  }
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
      :title="$t('tenant.auth.title')"
      :sub-title="$t('authentication.tenantAdminDesc')"
      @submit="handleLogin"
    >
      <!-- 租户编码 + 验证码插槽 -->
      <template v-if="showTenantCode || showCaptcha" #form-extend>
        <!-- 租户编码输入 -->
        <div v-if="showTenantCode" class="tenant-code-section">
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
        <div v-if="showCaptcha" class="captcha-section">
          <div class="captcha-row">
            <Input
              v-model:value="captchaSolution"
              :placeholder="$t('shared.auth.captcha.placeholder')"
              :maxlength="6"
              size="large"
              class="captcha-input"
            />
            <CaptchaImage
              ref="captchaRef"
              endpoint="tenant"
              :difficulty="captchaDifficulty"
            />
          </div>
        </div>
      </template>
    </AuthenticationLogin>
  </div>
</template>

<style scoped>
.tenant-code-section {
  margin-bottom: 16px;
}

.captcha-section {
  margin-top: 8px;
  margin-bottom: 16px;
}

.captcha-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.captcha-input {
  flex: 1;
  min-width: 0;
}
</style>
