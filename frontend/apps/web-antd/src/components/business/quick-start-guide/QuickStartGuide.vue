<script lang="ts" setup>
/**
 * 快速入门引导组件（共享）
 *
 * 首次访问时显示，可关闭并通过按钮重新打开。
 * 通过 props 注入步骤数据、localStorage key 和 i18n 前缀，适配 admin/tenant 两端。
 */
import { onMounted, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

export interface GuideStep {
  key: string;
  icon: string;
  color: string;
  bg: string;
  link: string;
}

const props = defineProps<{
  /** i18n 前缀，如 'admin.ai' 或 'tenant.ai' */
  i18nPrefix: string;
  /** 引导步骤列表 */
  steps: GuideStep[];
  /** localStorage 持久化 key */
  storageKey: string;
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
    class="relative rounded-xl border border-border/40 bg-card shadow-sm"
  >
    <!-- 顶部渐变条 -->
    <div
      class="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-primary via-primary/60 to-transparent"
    ></div>

    <div class="flex items-center gap-4 px-4 py-3">
      <!-- 左侧：标题区 -->
      <div class="flex shrink-0 items-center gap-2.5">
        <div
          class="flex size-8 items-center justify-center rounded-lg bg-primary/10"
        >
          <IconifyIcon icon="lucide:zap" class="size-4 text-primary" />
        </div>
        <div class="hidden lg:block">
          <div class="text-sm font-semibold text-foreground">
            {{ $t(`${i18nPrefix}.guide.title`) }}
          </div>
          <div class="text-[11px] text-muted-foreground">
            {{ $t(`${i18nPrefix}.guide.subtitle`) }}
          </div>
        </div>
      </div>

      <!-- 分隔线 -->
      <div class="hidden h-8 w-px bg-border/60 lg:block"></div>

      <!-- 中间：步骤流程 -->
      <div class="flex min-w-0 flex-1 items-center gap-1">
        <template v-for="(step, idx) in steps" :key="step.key">
          <!-- 连接线 -->
          <div
            v-if="idx > 0"
            class="hidden h-px w-4 shrink-0 bg-border/60 lg:block xl:w-6"
          ></div>
          <router-link
            :to="step.link"
            class="group flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2.5 py-2 transition-colors hover:bg-primary/5"
          >
            <div
              class="relative flex size-7 shrink-0 items-center justify-center rounded-lg"
              :class="step.bg"
            >
              <IconifyIcon
                :icon="step.icon"
                class="size-3.5"
                :class="step.color"
              />
              <span
                class="absolute -right-1 -top-1 flex size-3.5 items-center justify-center rounded-full text-[8px] font-bold text-white"
                :class="[
                  idx === 0
                    ? 'bg-[hsl(var(--primary))]'
                    : idx === 1
                      ? 'bg-amber-500'
                      : idx === 2
                        ? 'bg-purple-500'
                        : 'bg-[hsl(var(--success))]',
                ]"
              >
                {{ idx + 1 }}
              </span>
            </div>
            <div class="min-w-0 flex-1">
              <div
                class="truncate text-xs font-medium text-foreground group-hover:text-primary"
              >
                {{ $t(`${i18nPrefix}.guide.${step.key}.title`) }}
              </div>
              <div
                class="hidden truncate text-[10px] text-muted-foreground/60 xl:block"
              >
                {{ $t(`${i18nPrefix}.guide.${step.key}.time`) }}
              </div>
            </div>
            <IconifyIcon
              icon="lucide:chevron-right"
              class="size-3 shrink-0 text-muted-foreground/0 transition-colors group-hover:text-primary"
            />
          </router-link>
        </template>
      </div>

      <!-- 右侧：时间 + 关闭 -->
      <div class="flex shrink-0 items-center gap-1.5">
        <span
          class="hidden items-center gap-1 rounded-full bg-primary/[0.06] px-2 py-0.5 text-[10px] font-medium text-primary xl:inline-flex"
        >
          <IconifyIcon icon="lucide:timer" class="size-2.5" />
          {{ $t(`${i18nPrefix}.guide.totalTime`) }}
        </span>
        <button
          class="flex size-6 items-center justify-center rounded-md text-muted-foreground/50 transition-colors hover:bg-muted hover:text-foreground"
          @click="dismiss"
        >
          <IconifyIcon icon="lucide:x" class="size-3.5" />
        </button>
      </div>
    </div>
  </div>

  <!-- 已关闭时显示重新打开按钮 -->
  <div v-else-if="dismissed" class="flex justify-end">
    <button
      class="flex items-center gap-1.5 rounded-lg border border-transparent px-3 py-1.5 text-xs text-muted-foreground transition-all hover:border-primary/15 hover:bg-primary/5 hover:text-primary"
      @click="showGuide"
    >
      <IconifyIcon icon="lucide:compass" class="size-3.5" />
      {{ $t(`${i18nPrefix}.guide.showGuide`) }}
    </button>
  </div>
</template>
