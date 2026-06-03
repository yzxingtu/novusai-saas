<script lang="ts" setup>
/**
 * Captcha Image Component
 * Standalone captcha image display component, can be used with any input field
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
// Props & Emits / 属性与事件
// ============================================================

interface Props {
  /** Endpoint identifier: admin | tenant | user / 端点标识: admin | tenant | user */
  endpoint: 'admin' | 'tenant' | 'user';
  /** Difficulty level / 难度等级 */
  difficulty?: CaptchaDifficulty;
  /** Action type, defaults to login / 操作类型，默认 login */
  action?: string;
  /** Whether disabled / 是否禁用 */
  disabled?: boolean;
  /** Image width / 图片宽度 */
  width?: number;
  /** Image height / 图片高度 */
  height?: number;
}

// ============================================================
// State / 状态
// ============================================================

/** Challenge ID / 挑战 ID */
const challengeId = ref('');
/** Captcha image Base64 / 验证码图片 Base64 */
const captchaImage = ref('');
/** Loading state / 加载中状态 */
const loading = ref(false);
/** Error message / 错误信息 */
const errorMsg = ref('');

// ============================================================
// Methods / 方法
// ============================================================

let _fetchPromise: null | Promise<void> = null;

/**
 * Fetch captcha challenge (with deduplication: rapid consecutive calls reuse the same request)
 * 获取验证码挑战（含去重：快速连续调用复用同一请求）
 */
async function fetchChallenge() {
  if (props.disabled) return;

  // Deduplication: if there's an ongoing request, wait for it to complete before sending a new one / 去重：如果有正在进行的请求，等待其完成后再发新请求
  if (_fetchPromise) {
    await _fetchPromise.catch(() => {});
  }

  _fetchPromise = _doFetchChallenge();
  await _fetchPromise.finally(() => {
    _fetchPromise = null;
  });
}

async function _doFetchChallenge() {
  loading.value = true;
  errorMsg.value = '';

  try {
    const response = await getCaptchaChallengeApi({
      action: props.action,
      difficulty: props.difficulty,
      endpoint: props.endpoint,
    });

    challengeId.value = response.challengeId;
    // Ensure base64 prefix - handle undefined/empty image / 补全 data URL 前缀
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
 * Refresh captcha / 刷新验证码
 */
function refresh() {
  fetchChallenge();
}

/**
 * Get current challenge ID / 获取当前挑战 ID
 */
function getChallengeId() {
  return challengeId.value;
}

// ============================================================
// Lifecycle / 生命周期
// ============================================================

// Auto-fetch captcha on mount / 挂载时自动获取验证码
onMounted(() => {
  fetchChallenge();
});

// Re-fetch on endpoint change / 监听 endpoint 变化重新获取
watch(
  () => props.endpoint,
  () => {
    fetchChallenge();
  },
);

// Expose methods to parent component / 暴露方法给父组件
defineExpose({
  getChallengeId,
  refresh,
});
</script>

<template>
  <div class="captcha-image-container">
    <!-- Captcha image / 验证码图片 -->
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
            :alt="$t('shared.auth.captcha.clickToRefresh')"
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

    <!-- Refresh button / 刷新按钮 -->
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
  background: linear-gradient(
    135deg,
    hsl(var(--muted)) 0%,
    hsl(var(--accent)) 100%
  );
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
