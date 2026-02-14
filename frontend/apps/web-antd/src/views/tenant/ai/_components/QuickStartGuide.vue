<script lang="ts" setup>
/**
 * AI 智能体快速入门引导组件
 *
 * 首次访问时显示，可关闭并通过按钮重新打开
 */
import { ref, onMounted } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Card } from 'ant-design-vue';

import { $t } from '#/locales';

const STORAGE_KEY = 'tenant-ai-guide-dismissed';

const visible = ref(false);
const dismissed = ref(false);

const steps = [
  {
    key: 'step1',
    icon: 'lucide:bot',
    color: 'text-primary',
    bg: 'bg-primary/10',
    link: '/tenant/ai/agents',
  },
  {
    key: 'step2',
    icon: 'lucide:sparkles',
    color: 'text-purple-600',
    bg: 'bg-purple-500/10',
    link: '/tenant/ai/skills',
  },
  {
    key: 'step3',
    icon: 'lucide:rocket',
    color: 'text-amber-600',
    bg: 'bg-amber-500/10',
    link: '/tenant/ai/agents',
  },
  {
    key: 'step4',
    icon: 'lucide:message-circle',
    color: 'text-success',
    bg: 'bg-success/10',
    link: '/tenant/ai/chat',
  },
];

function dismiss() {
  visible.value = false;
  dismissed.value = true;
  try {
    localStorage.setItem(STORAGE_KEY, '1');
  } catch {
    // storage unavailable
  }
}

function showGuide() {
  visible.value = true;
  dismissed.value = false;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // storage unavailable
  }
}

onMounted(() => {
  try {
    dismissed.value = localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    dismissed.value = false;
  }
  visible.value = !dismissed.value;
});

defineExpose({ showGuide });
</script>

<template>
  <!-- 引导卡片 -->
  <Card
    v-if="visible"
    :body-style="{ padding: '20px' }"
    class="border-primary/20 bg-primary/5"
  >
    <div class="mb-3 flex items-center justify-between">
      <div>
        <div class="text-base font-semibold text-foreground">
          {{ $t('tenant.ai.guide.title') }}
        </div>
        <div class="mt-0.5 flex items-center gap-2 text-sm text-muted-foreground">
          <span>{{ $t('tenant.ai.guide.subtitle') }}</span>
          <span class="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
            {{ $t('tenant.ai.guide.totalTime') }}
          </span>
        </div>
      </div>
      <Button size="small" type="text" @click="dismiss">
        <IconifyIcon icon="lucide:x" class="size-4" />
      </Button>
    </div>

    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <router-link
        v-for="(step, idx) in steps"
        :key="step.key"
        :to="step.link"
        class="group flex items-start gap-3 rounded-lg border border-border bg-card p-3 transition-all hover:border-primary/40 hover:shadow-sm"
      >
        <div
          class="flex size-9 shrink-0 items-center justify-center rounded-lg"
          :class="step.bg"
        >
          <span class="text-xs font-bold" :class="step.color">{{ idx + 1 }}</span>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <IconifyIcon :icon="step.icon" class="size-3.5" :class="step.color" />
            <span class="text-sm font-medium text-foreground">
              {{ $t(`tenant.ai.guide.${step.key}.title`) }}
            </span>
            <span class="rounded bg-muted px-1 py-0.5 text-[10px] text-muted-foreground">
              {{ $t(`tenant.ai.guide.${step.key}.time`) }}
            </span>
          </div>
          <div class="mt-0.5 text-xs leading-relaxed text-muted-foreground">
            {{ $t(`tenant.ai.guide.${step.key}.detail`) }}
          </div>
        </div>
        <IconifyIcon
          icon="lucide:chevron-right"
          class="mt-1 size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
        />
      </router-link>
    </div>

    <div class="mt-3 text-right">
      <Button size="small" type="link" @click="dismiss">
        {{ $t('tenant.ai.guide.dismiss') }}
      </Button>
    </div>
  </Card>

  <!-- 已关闭时显示重新打开按钮 -->
  <div v-else-if="dismissed" class="flex justify-end">
    <Button size="small" type="link" @click="showGuide">
      <IconifyIcon icon="lucide:compass" class="mr-1 size-3.5" />
      {{ $t('tenant.ai.guide.showGuide') }}
    </Button>
  </div>
</template>
