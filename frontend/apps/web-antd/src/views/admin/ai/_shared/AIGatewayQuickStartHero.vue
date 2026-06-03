<script lang="ts" setup>
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

defineOptions({ name: 'AIGatewayQuickStartHero' });

const props = defineProps<{
  currentTitle: string;
}>();

const quickStartSteps = computed(() => [
  {
    key: 'step1',
    title: $t('admin.ai.guide.step1.title'),
    time: $t('admin.ai.guide.step1.time'),
    icon: 'lucide:plug',
    link: '/admin/ai/providers',
    iconWrapClass: 'bg-primary/10 text-primary',
    badgeClass: 'bg-primary text-primary-foreground',
  },
  {
    key: 'step2',
    title: $t('admin.ai.guide.step2.title'),
    time: $t('admin.ai.guide.step2.time'),
    icon: 'lucide:key-round',
    link: '/admin/ai/api-keys',
    iconWrapClass: 'bg-amber-500/10 text-amber-700 dark:text-amber-200',
    badgeClass: 'bg-amber-500 text-white',
  },
  {
    key: 'step3',
    title: $t('admin.ai.guide.step3.title'),
    time: $t('admin.ai.guide.step3.time'),
    icon: 'lucide:brain-circuit',
    link: '/admin/ai/models',
    iconWrapClass: 'bg-violet-500/10 text-violet-700 dark:text-violet-200',
    badgeClass: 'bg-violet-500 text-white',
  },
  {
    key: 'step4',
    title: $t('admin.ai.guide.step4.title'),
    time: $t('admin.ai.guide.step4.time'),
    icon: 'lucide:activity',
    link: '/admin/ai/monitor/health',
    iconWrapClass: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
    badgeClass: 'bg-emerald-500 text-white',
  },
]);

const quickStartChips = computed(() => [
  {
    key: 'current',
    icon: 'lucide:layout-panel-top',
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
    text: `${$t('admin.ai.guide.summary.current')}: ${props.currentTitle}`,
  },
  {
    key: 'flow',
    icon: 'lucide:route',
    className: 'bg-background/90 text-foreground',
    text: `${$t('admin.ai.guide.summary.flow')}: ${quickStartSteps.value.map((step) => step.title).join(' / ')}`,
  },
  {
    key: 'eta',
    icon: 'lucide:timer',
    className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
    text: `${$t('admin.ai.guide.summary.eta')}: ${$t('admin.ai.guide.totalTime')}`,
  },
]);

const quickStartMetrics = computed(() => [
  {
    key: 'steps',
    label: $t('admin.ai.guide.summary.stepsLabel'),
    value: String(quickStartSteps.value.length),
  },
  {
    key: 'duration',
    label: $t('admin.ai.guide.summary.eta'),
    value: $t('admin.ai.guide.totalTime'),
  },
]);
</script>

<template>
  <section
    class="rounded-[20px] border border-border/70 bg-card px-4 py-3 shadow-sm"
  >
    <div
      class="flex flex-col gap-3 2xl:flex-row 2xl:items-start 2xl:justify-between"
    >
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <span
            class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
          >
            <IconifyIcon icon="lucide:compass" class="size-4" />
          </span>
          <h1 class="text-base font-semibold text-foreground">
            {{ $t('admin.ai.guide.title') }}
          </h1>
          <span class="hidden text-xs text-muted-foreground xl:inline">
            {{ $t('admin.ai.guide.subtitle') }}
          </span>
        </div>

        <div class="mt-2 flex flex-wrap gap-2">
          <span
            v-for="chip in quickStartChips"
            :key="chip.key"
            class="inline-flex max-w-full items-center gap-2 rounded-full border border-transparent px-2.5 py-1 text-xs"
            :class="chip.className"
          >
            <IconifyIcon :icon="chip.icon" class="size-3.5 flex-shrink-0" />
            <span class="max-w-[320px] truncate">{{ chip.text }}</span>
          </span>
        </div>
      </div>

      <div class="flex flex-wrap gap-2">
        <span
          v-for="metric in quickStartMetrics"
          :key="metric.key"
          class="rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-xs text-muted-foreground"
        >
          <span class="mr-1 font-semibold text-foreground">
            {{ metric.value }}
          </span>
          {{ metric.label }}
        </span>
      </div>
    </div>

    <div class="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <router-link
        v-for="(step, index) in quickStartSteps"
        :key="step.key"
        :to="step.link"
        class="group rounded-2xl border border-border/60 bg-background/80 px-4 py-3 transition-all hover:border-primary/20 hover:bg-accent/40"
      >
        <div class="flex items-start gap-3">
          <div class="relative">
            <span
              class="flex size-10 items-center justify-center rounded-xl"
              :class="step.iconWrapClass"
            >
              <IconifyIcon :icon="step.icon" class="size-4" />
            </span>
            <span
              class="absolute -right-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full text-[11px] font-semibold"
              :class="step.badgeClass"
            >
              {{ index + 1 }}
            </span>
          </div>

          <div class="min-w-0 flex-1">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <div
                  class="truncate text-sm font-semibold text-foreground transition-colors group-hover:text-primary"
                >
                  {{ step.title }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">
                  {{ step.time }}
                </div>
              </div>

              <IconifyIcon
                icon="lucide:arrow-up-right"
                class="mt-0.5 size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
              />
            </div>
          </div>
        </div>
      </router-link>
    </div>
  </section>
</template>
