<script lang="ts" setup>
/**
 * 图片验证码表单适配器
 * 组合 CaptchaImage + Input，输出统一 CaptchaResult
 */
import type { CaptchaDifficulty } from '#/api/public/captcha';

import type { CaptchaAdapterExpose, CaptchaEndpoint, CaptchaResult } from './types';

import { ref } from 'vue';

import { Input } from 'ant-design-vue';

import { $t } from '#/locales';

import CaptchaImage from './CaptchaImage.vue';

defineOptions({ name: 'CaptchaImageForm' });

const props = withDefaults(
  defineProps<{
    /** 端点标识 */
    endpoint: CaptchaEndpoint;
    /** 难度等级 */
    difficulty?: CaptchaDifficulty;
    /** 操作类型 */
    action?: string;
    /** 是否禁用 */
    disabled?: boolean;
  }>(),
  {
    action: 'login',
    difficulty: 'medium',
    disabled: false,
  },
);

const emit = defineEmits<{
  (e: 'verified', result: CaptchaResult): void;
  (e: 'error', error: Error): void;
}>();

const captchaRef = ref<InstanceType<typeof CaptchaImage>>();
const captchaCode = ref('');

function refresh() {
  captchaCode.value = '';
  captchaRef.value?.refresh();
}

function getResult(): CaptchaResult | null {
  const challengeId = captchaRef.value?.getChallengeId() || '';
  if (!challengeId) {
    emit('error', new Error('captcha_not_loaded'));
    return null;
  }
  if (!captchaCode.value) {
    emit('error', new Error('captcha_code_empty'));
    return null;
  }
  return {
    captchaCode: captchaCode.value,
    challengeId,
    provider: 'image',
  };
}

function handleCaptchaError(error: Error) {
  emit('error', error);
}

defineExpose<CaptchaAdapterExpose>({
  getResult,
  refresh,
});
</script>

<template>
  <div class="captcha-form">
    <div class="captcha-row">
      <Input
        v-model:value="captchaCode"
        :placeholder="$t('shared.auth.captcha.placeholder')"
        :maxlength="6"
        :disabled="disabled"
        size="large"
        class="captcha-input"
      />
      <CaptchaImage
        ref="captchaRef"
        :endpoint="props.endpoint"
        :difficulty="props.difficulty"
        :action="props.action"
        :disabled="props.disabled"
        @error="handleCaptchaError"
      />
    </div>
  </div>
</template>

<style scoped>
.captcha-form {
  width: 100%;
}

.captcha-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.captcha-input {
  flex: 1;
}
</style>
