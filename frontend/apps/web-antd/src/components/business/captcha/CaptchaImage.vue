<script lang="ts" setup>
/**
 * 验证码图片组件
 * 独立的验证码图片展示组件，可配合任意输入框使用
 */
import type { CaptchaDifficulty } from '#/api/public/captcha';

import { onMounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Spin, Tooltip } from 'ant-design-vue';

import { getCaptchaChallengeApi } from '#/api/public/captcha';
import { $t } from '#/locales';

defineOptions({ name: 'CaptchaImage' });

const props = withDefaults(defineProps<Props>(), {
  action: 'login',
  difficulty: 'medium',
  disabled: false,
  height: 40,
  width: 120,
});

const emit = defineEmits<{
  (e: 'change', challengeId: string): void;
  (e: 'error', error: Error): void;
  (e: 'load'): void;
}>();

// ============================================================
// Props & Emits
// ============================================================

interface Props {
  /** 端点标识: admin | tenant */
  endpoint: 'admin' | 'tenant';
  /** 难度等级 */
  difficulty?: CaptchaDifficulty;
  /** 操作类型，默认 login */
  action?: string;
  /** 是否禁用 */
  disabled?: boolean;
  /** 图片宽度 */
  width?: number;
  /** 图片高度 */
  height?: number;
}

// ============================================================
// State
// ============================================================

/** 挑战 ID */
const challengeId = ref('');
/** 验证码图片 Base64 */
const captchaImage = ref('');
/** 加载中状态 */
const loading = ref(false);
/** 错误信息 */
const errorMsg = ref('');

// ============================================================
// Methods
// ============================================================

/**
 * 获取验证码挑战
 */
async function fetchChallenge() {
  if (props.disabled) return;

  loading.value = true;
  errorMsg.value = '';

  try {
    const response = await getCaptchaChallengeApi({
      action: props.action,
      difficulty: props.difficulty,
      endpoint: props.endpoint,
    });

    challengeId.value = response.challengeId;
    // Ensure base64 prefix - handle undefined/empty image
    const base64 = response.image || '';
    if (base64) {
      captchaImage.value = base64.startsWith('data:')
        ? base64
        : `data:image/png;base64,${base64}`;
      emit('change', challengeId.value);
      emit('load');
    } else {
      captchaImage.value = '';
      throw new Error('Captcha image data is empty');
    }
  } catch (error) {
    const err = error instanceof Error ? error : new Error(String(error));
    errorMsg.value = err.message;
    emit('error', err);
  } finally {
    loading.value = false;
  }
}

/**
 * 刷新验证码
 */
function refresh() {
  fetchChallenge();
}

/**
 * 获取当前挑战 ID
 */
function getChallengeId() {
  return challengeId.value;
}

// ============================================================
// Lifecycle
// ============================================================

// 挂载时自动获取验证码
onMounted(() => {
  fetchChallenge();
});

// 监听 endpoint 变化重新获取
watch(
  () => props.endpoint,
  () => {
    fetchChallenge();
  },
);

// 暴露方法给父组件
defineExpose({
  getChallengeId,
  refresh,
});
</script>

<template>
  <div class="captcha-image-container">
    <!-- 验证码图片 -->
    <Tooltip :title="$t('shared.auth.captcha.clickToRefresh')">
      <div
        class="captcha-image-wrapper"
        :class="{
          'captcha-image-wrapper--disabled': disabled,
          'captcha-image-wrapper--loading': loading,
        }"
        :style="{ width: `${width}px`, height: `${height}px` }"
        @click="!disabled && !loading && refresh()"
      >
        <Spin :spinning="loading" size="small">
          <img
            v-if="captchaImage && !loading"
            :src="captchaImage"
            alt="captcha"
            class="captcha-image"
          />
          <div v-else-if="!loading && errorMsg" class="captcha-status error">
            <IconifyIcon icon="lucide:alert-circle" class="size-5" />
          </div>
          <div v-else-if="!loading" class="captcha-status placeholder">
            <IconifyIcon icon="lucide:image" class="size-6" />
          </div>
        </Spin>
      </div>
    </Tooltip>

    <!-- 刷新按钮 -->
    <Tooltip :title="$t('shared.auth.captcha.refresh')">
      <button
        type="button"
        class="captcha-refresh-btn"
        :style="{ height: `${height}px` }"
        :disabled="disabled || loading"
        @click="refresh"
      >
        <IconifyIcon
          icon="lucide:refresh-cw"
          class="size-4"
          :class="{ 'animate-spin': loading }"
        />
      </button>
    </Tooltip>
  </div>
</template>

<style scoped>
.captcha-image-container {
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

.captcha-image-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: pointer;
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  border: 1px solid hsl(var(--border));
  border-radius: 6px;
  transition: all 0.2s ease;
}

.captcha-image-wrapper:hover {
  border-color: hsl(var(--primary));
  box-shadow: 0 0 0 2px hsl(var(--primary) / 10%);
}

.captcha-image-wrapper--disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.captcha-image-wrapper--loading {
  cursor: wait;
}

.captcha-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: crisp-edges;
}

.captcha-status {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.captcha-status.error {
  color: hsl(var(--destructive));
}

.captcha-status.placeholder {
  color: hsl(var(--muted-foreground));
}

.captcha-refresh-btn {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 36px;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  background: hsl(var(--muted));
  border: 1px solid hsl(var(--border));
  border-radius: 6px;
  transition: all 0.2s ease;
}

.captcha-refresh-btn:hover:not(:disabled) {
  color: hsl(var(--primary));
  background: hsl(var(--accent));
  border-color: hsl(var(--primary));
}

.captcha-refresh-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
</style>
