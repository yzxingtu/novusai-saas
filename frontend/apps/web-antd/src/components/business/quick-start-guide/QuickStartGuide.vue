<script lang="ts" setup>
/**
 * 快速入门引导组件（共享）
 *
 * 首次访问时显示，可关闭并通过按钮重新打开。
 * 通过 props 注入步骤数据、localStorage key 和 i18n 前缀，适配 admin/tenant 两端。
 */
import { ref, onMounted } from 'vue';

import { IconifyIcon } from '@vben/icons';

// ant-design-vue components removed — using native buttons with Tailwind

import { $t } from '#/locales';

export interface GuideStep {
  key: string;
  icon: string;
  color: string;
  bg: string;
  link: string;
}

const props = defineProps<{
  /** localStorage 持久化 key */
  storageKey: string;
  /** 引导步骤列表 */
  steps: GuideStep[];
  /** i18n 前缀，如 'admin.ai' 或 'tenant.ai' */
  i18nPrefix: string;
}>();

const visible = ref(false);
const dismissed = ref(false);

function dismiss() {
  visible.value = false;
  dismissed.value = true;
  try {
    localStorage.setItem(props.storageKey, '1');
  } catch {
    // storage unavailable
  }
}

function showGuide() {
  visible.value = true;
  dismissed.value = false;
  try {
    localStorage.removeItem(props.storageKey);
  } catch {
    // storage unavailable
  }
}

onMounted(() => {
  try {
    dismissed.value = localStorage.getItem(props.storageKey) === '1';
  } catch {
    dismissed.value = false;
  }
  visible.value = !dismissed.value;
});

defineExpose({ showGuide });
</script>

<template>
  <!-- 引导卡片 -->
  <div
    v-if="visible"
    class="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary/8 via-background to-primary/4 p-6"
  >
    <!-- 装饰元素 -->
    <div class="absolute -right-8 -top-8 size-32 rounded-full bg-primary/5 blur-2xl" />
    <div class="absolute -bottom-6 -left-6 size-24 rounded-full bg-primary/3 blur-xl" />

    <div class="relative z-10">
      <!-- 头部 -->
      <div class="mb-5 flex items-start justify-between">
        <div class="flex items-center gap-3">
          <div class="flex size-10 items-center justify-center rounded-xl bg-primary/10">
            <IconifyIcon icon="lucide:rocket" class="size-5 text-primary" />
          </div>
          <div>
            <h3 class="text-base font-bold text-foreground">
              {{ $t(`${i18nPrefix}.guide.title`) }}
            </h3>
            <div class="mt-0.5 flex items-center gap-2">
              <span class="text-sm text-muted-foreground">{{ $t(`${i18nPrefix}.guide.subtitle`) }}</span>
              <span class="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-medium text-primary">
                <IconifyIcon icon="lucide:timer" class="size-3" />
                {{ $t(`${i18nPrefix}.guide.totalTime`) }}
              </span>
            </div>
          </div>
        </div>
        <button
          class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          @click="dismiss"
        >
          <IconifyIcon icon="lucide:x" class="size-4" />
        </button>
      </div>

      <!-- 步骤卡片 -->
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <router-link
          v-for="(step, idx) in steps"
          :key="step.key"
          :to="step.link"
          class="group relative flex flex-col gap-3 rounded-xl border border-border/50 bg-card/80 p-4 backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5"
        >
          <!-- 步骤编号 + 图标 -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <div
                class="flex size-8 items-center justify-center rounded-lg text-xs font-bold"
                :class="step.bg + ' ' + step.color"
              >
                {{ idx + 1 }}
              </div>
              <IconifyIcon :icon="step.icon" class="size-4" :class="step.color" />
            </div>
            <span class="rounded-md bg-muted/80 px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {{ $t(`${i18nPrefix}.guide.${step.key}.time`) }}
            </span>
          </div>
          <!-- 标题 + 描述 -->
          <div>
            <div class="text-sm font-semibold text-foreground">
              {{ $t(`${i18nPrefix}.guide.${step.key}.title`) }}
            </div>
            <div class="mt-1 text-xs leading-relaxed text-muted-foreground/80">
              {{ $t(`${i18nPrefix}.guide.${step.key}.detail`) }}
            </div>
          </div>
          <!-- hover 箭头 -->
          <div class="flex items-center gap-1 text-xs text-primary opacity-0 transition-all duration-200 group-hover:opacity-100">
            <span>{{ $t('common.viewDetail') }}</span>
            <IconifyIcon icon="lucide:arrow-right" class="size-3" />
          </div>
        </router-link>
      </div>

      <!-- 底部关闭 -->
      <div class="mt-4 flex items-center justify-end">
        <button
          class="flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
          @click="dismiss"
        >
          <IconifyIcon icon="lucide:eye-off" class="size-3" />
          {{ $t(`${i18nPrefix}.guide.dismiss`) }}
        </button>
      </div>
    </div>
  </div>

  <!-- 已关闭时显示重新打开按钮 -->
  <div v-else-if="dismissed" class="flex justify-end">
    <button
      class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-muted-foreground transition-all hover:bg-primary/5 hover:text-primary"
      @click="showGuide"
    >
      <IconifyIcon icon="lucide:compass" class="size-3.5" />
      {{ $t(`${i18nPrefix}.guide.showGuide`) }}
    </button>
  </div>
</template>
