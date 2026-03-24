<script lang="ts" setup>
/**
 * Unified captcha container component
 * Dynamically renders the corresponding captcha component based on provider type
 * Defaults to built-in image type, supports plugin-registered new types
 * 统一验证码容器组件
 * 根据 provider 类型动态渲染对应验证码组件
 * 默认使用内置 image 类型，支持插件注册新类型
 */
import type { CaptchaDifficulty } from '#/api/public/captcha';

import type {
  CaptchaAction,
  CaptchaAdapterExpose,
  CaptchaEndpoint,
  CaptchaProviderType,
  CaptchaResult,
} from './types';

import { computed, ref } from 'vue';

import CaptchaImageForm from './CaptchaImageForm.vue';
import { getCaptchaProvider } from './registry';

defineOptions({ name: 'CaptchaProvider' });

const props = withDefaults(
  defineProps<{
    /** Endpoint identifier / 端点标识 */
    endpoint: CaptchaEndpoint;
    /** Captcha provider type (read from config, defaults to 'image') / 验证码提供商类型（从配置读取，默认 'image'） */
    provider?: CaptchaProviderType;
    /** Difficulty level / 难度等级 */
    difficulty?: CaptchaDifficulty;
    /** Action type / 操作类型 */
    action?: CaptchaAction;
    /** Whether disabled / 是否禁用 */
    disabled?: boolean;
  }>(),
  {
    action: 'login',
    difficulty: 'medium',
    disabled: false,
    provider: 'image',
  },
);

const emit = defineEmits<{
  (e: 'verified', result: CaptchaResult): void;
  (e: 'error', error: Error): void;
}>();

const adapterRef = ref<CaptchaAdapterExpose>();

/** Resolve the actual component to render / 解析实际渲染的组件 */
const resolvedComponent = computed(() => {
  if (props.provider === 'image') {
    return CaptchaImageForm;
  }

  const entry = getCaptchaProvider(props.provider);
  if (entry) {
    return entry.component;
  }
  if (props.provider !== 'image') {
    console.warn(`[CaptchaProvider] provider "${props.provider}" not registered, falling back to CaptchaImageForm`);
  }
  // Fallback to image if provider not registered / 未注册插件则回退图片验证码
  return CaptchaImageForm;
});

/** Whether using built-in image adapter (for passing specific props) / 是否使用内置 image 适配器（用于传递特定 props） */
const isImageProvider = computed(() => {
  return resolvedComponent.value === CaptchaImageForm;
});

function refresh() {
  adapterRef.value?.refresh();
}

function getResult(): CaptchaResult | null {
  return adapterRef.value?.getResult() ?? null;
}

function handleVerified(result: CaptchaResult) {
  emit('verified', result);
}

function handleError(error: Error) {
  emit('error', error);
}

defineExpose<CaptchaAdapterExpose>({
  getResult,
  refresh,
});
</script>

<template>
  <component
    :is="resolvedComponent"
    ref="adapterRef"
    :endpoint="props.endpoint"
    :difficulty="isImageProvider ? props.difficulty : undefined"
    :action="props.action"
    :disabled="props.disabled"
    @verified="handleVerified"
    @error="handleError"
  />
</template>
