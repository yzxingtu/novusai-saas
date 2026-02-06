<script lang="ts" setup>
/**
 * 图形验证码组件
 * 用于登录页展示后端图形验证码
 */
import type { CaptchaDifficulty } from '#/api/public/captcha';

import { onMounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Input, Spin, Tooltip } from 'ant-design-vue';

import { getCaptchaChallengeApi } from '#/api/public/captcha';
import { $t } from '#/locales';

defineOptions({ name: 'ImageCaptcha' });

const props = withDefaults(defineProps<Props>(), {
  action: 'login',
  difficulty: 'medium',
  disabled: false,
});

const emit = defineEmits<{
  (e: 'change', challengeId: string, solution: string): void;
  (e: 'error', error: Error): void;
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
}

// ============================================================
// State
// ============================================================

/** 挑战 ID */
const challengeId = ref('');
/** 验证码图片 Base64 */
const captchaImage = ref('');
/** 用户输入的答案 */
const solution = ref('');
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
    } else {
      captchaImage.value = '';
      throw new Error('Captcha image data is empty');
    }
    // 清空之前的输入
    solution.value = '';
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
 * 处理输入变化
 */
function handleInputChange() {
  emit('change', challengeId.value, solution.value);
}

/**
 * 获取当前验证码数据（供父组件调用）
 */
function getCaptchaData() {
  return {
    challengeId: challengeId.value,
    solution: solution.value,
  };
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
  getCaptchaData,
  refresh,
});
</script>

<template>
  <div class="captcha-container">
    <!-- 验证码输入行：输入框 + 图片 + 刷新按钮 -->
    <div class="captcha-row">
      <!-- 输入框 -->
      <Input
        v-model:value="solution"
        :disabled="disabled || loading"
        :placeholder="$t('shared.auth.captcha.placeholder')"
        :maxlength="6"
        class="captcha-input"
        size="large"
        @change="handleInputChange"
        @press-enter="handleInputChange"
      >
        <template #prefix>
          <IconifyIcon
            icon="lucide:shield-check"
            class="text-muted-foreground"
          />
        </template>
      </Input>

      <!-- 验证码图片区域 -->
      <Tooltip :title="$t('shared.auth.captcha.clickToRefresh')">
        <div
          class="captcha-image-wrapper"
          :class="{
            'captcha-image-wrapper--disabled': disabled,
            'captcha-image-wrapper--loading': loading,
          }"
          @click="!disabled && !loading && refresh()"
        >
          <Spin :spinning="loading" size="small">
            <img
              v-if="captchaImage && !loading"
              :src="captchaImage"
              alt="captcha"
              class="captcha-image"
            />
            <div v-else-if="!loading && errorMsg" class="captcha-error">
              <IconifyIcon icon="lucide:alert-circle" class="size-5" />
            </div>
            <div v-else-if="!loading" class="captcha-placeholder">
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

    <!-- 错误提示 -->
    <div v-if="errorMsg && !loading" class="captcha-error-msg">
      <IconifyIcon icon="lucide:alert-triangle" class="size-3" />
      <span>{{ errorMsg }}</span>
    </div>
  </div>
</template>

<style scoped>
.captcha-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
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

.captcha-image-wrapper {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 120px;
  height: 40px;
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

.captcha-error {
  display: flex;
  align-items: center;
  justify-content: center;
  color: hsl(var(--destructive));
}

.captcha-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: hsl(var(--muted-foreground));
}

.captcha-refresh-btn {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
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

.captcha-error-msg {
  display: flex;
  gap: 4px;
  align-items: center;
  font-size: 12px;
  color: hsl(var(--destructive));
}
</style>
