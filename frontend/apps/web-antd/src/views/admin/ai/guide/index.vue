<script lang="ts" setup>
defineOptions({ name: 'AdminAIGuide' });

import { IconifyIcon } from '@vben/icons';

import { Card, Collapse, CollapsePanel } from 'ant-design-vue';

import { $t } from '#/locales';

const setupSteps = [
  { key: 'step1', icon: 'lucide:plug', link: '/admin/ai/providers' },
  { key: 'step2', icon: 'lucide:brain', link: '/admin/ai/models' },
  { key: 'step3', icon: 'lucide:key', link: '/admin/ai/api-keys' },
  { key: 'step4', icon: 'lucide:activity', link: '/admin/ai/health' },
];

const sections = [
  {
    key: 'monitoring',
    icon: 'lucide:bar-chart-3',
    color: 'text-primary',
    bg: 'bg-primary/10',
    link: '/admin/ai/usage',
  },
  {
    key: 'security',
    icon: 'lucide:shield',
    color: 'text-amber-600',
    bg: 'bg-amber-500/10',
    link: '/admin/ai/action-logs',
  },
  {
    key: 'infra',
    icon: 'lucide:server',
    color: 'text-purple-600',
    bg: 'bg-purple-500/10',
    link: '/admin/ai/health',
  },
];

const faqKeys = ['faq1', 'faq2', 'faq3', 'faq4'];
</script>

<template>
  <div class="mx-auto max-w-4xl space-y-6 p-6">
    <!-- Header -->
    <div class="text-center">
      <h1 class="text-2xl font-bold text-foreground">
        {{ $t('admin.ai.guidePage.title') }}
      </h1>
      <p class="mt-2 text-muted-foreground">
        {{ $t('admin.ai.guidePage.subtitle') }}
      </p>
    </div>

    <!-- Platform Setup -->
    <Card :title="$t('admin.ai.guidePage.setupTitle')">
      <div class="space-y-4">
        <router-link
          v-for="(step, idx) in setupSteps"
          :key="step.key"
          :to="step.link"
          class="group flex items-start gap-4 rounded-lg border border-border p-4 transition-all hover:border-primary/40 hover:bg-primary/5"
        >
          <div class="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
            {{ idx + 1 }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <IconifyIcon :icon="step.icon" class="size-4 text-primary" />
              <span class="font-medium text-foreground">
                {{ $t(`admin.ai.guidePage.setup.${step.key}.title`) }}
              </span>
            </div>
            <p class="mt-1 text-xs text-muted-foreground">
              {{ $t(`admin.ai.guidePage.setup.${step.key}.desc`) }}
            </p>
          </div>
          <IconifyIcon
            icon="lucide:chevron-right"
            class="mt-2 size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
          />
        </router-link>
      </div>
    </Card>

    <!-- Management Sections -->
    <div>
      <h2 class="mb-4 text-lg font-semibold text-foreground">
        {{ $t('admin.ai.guidePage.sectionsTitle') }}
      </h2>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <router-link
          v-for="section in sections"
          :key="section.key"
          :to="section.link"
          class="group rounded-xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md"
        >
          <div
            class="mb-3 flex size-10 items-center justify-center rounded-lg"
            :class="section.bg"
          >
            <IconifyIcon :icon="section.icon" class="size-5" :class="section.color" />
          </div>
          <h3 class="text-sm font-semibold text-foreground">
            {{ $t(`admin.ai.guidePage.sections.${section.key}.title`) }}
          </h3>
          <p class="mt-1 text-xs leading-relaxed text-muted-foreground">
            {{ $t(`admin.ai.guidePage.sections.${section.key}.desc`) }}
          </p>
        </router-link>
      </div>
    </div>

    <!-- FAQ -->
    <Card :title="$t('admin.ai.guidePage.faqTitle')">
      <Collapse :bordered="false" class="bg-transparent">
        <CollapsePanel
          v-for="key in faqKeys"
          :key="key"
          :header="$t(`admin.ai.guidePage.faq.${key}.q`)"
        >
          <p class="text-sm text-muted-foreground">
            {{ $t(`admin.ai.guidePage.faq.${key}.a`) }}
          </p>
        </CollapsePanel>
      </Collapse>
    </Card>
  </div>
</template>
