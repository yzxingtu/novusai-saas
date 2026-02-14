<script lang="ts" setup>
defineOptions({ name: 'TenantAIGuide' });

import { IconifyIcon } from '@vben/icons';

import { Card, Collapse, CollapsePanel } from 'ant-design-vue';

import { $t } from '#/locales';

const features = [
  {
    key: 'chat',
    icon: 'lucide:message-circle',
    color: 'text-primary',
    bg: 'bg-primary/10',
    link: '/tenant/ai/chat',
  },
  {
    key: 'sql',
    icon: 'lucide:database',
    color: 'text-purple-600',
    bg: 'bg-purple-500/10',
    link: '/tenant/ai/agents',
  },
  {
    key: 'rag',
    icon: 'lucide:book-open',
    color: 'text-amber-600',
    bg: 'bg-amber-500/10',
    link: '/tenant/ai/knowledge-bases',
  },
];

const quickSteps = [
  { key: 'step1', icon: 'lucide:bot', link: '/tenant/ai/agents' },
  { key: 'step2', icon: 'lucide:sparkles', link: '/tenant/ai/skills' },
  { key: 'step3', icon: 'lucide:book-open', link: '/tenant/ai/knowledge-bases' },
  { key: 'step4', icon: 'lucide:rocket', link: '/tenant/ai/agents' },
  { key: 'step5', icon: 'lucide:message-circle', link: '/tenant/ai/chat' },
];

const faqKeys = ['faq1', 'faq2', 'faq3', 'faq4', 'faq5'];
</script>

<template>
  <div class="mx-auto max-w-4xl space-y-6 p-6">
    <!-- Header -->
    <div class="text-center">
      <h1 class="text-2xl font-bold text-foreground">
        {{ $t('tenant.ai.guidePage.title') }}
      </h1>
      <p class="mt-2 text-muted-foreground">
        {{ $t('tenant.ai.guidePage.subtitle') }}
      </p>
    </div>

    <!-- Feature Cards -->
    <div>
      <h2 class="mb-4 text-lg font-semibold text-foreground">
        {{ $t('tenant.ai.guidePage.featuresTitle') }}
      </h2>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <router-link
          v-for="feature in features"
          :key="feature.key"
          :to="feature.link"
          class="group rounded-xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md"
        >
          <div
            class="mb-3 flex size-10 items-center justify-center rounded-lg"
            :class="feature.bg"
          >
            <IconifyIcon :icon="feature.icon" class="size-5" :class="feature.color" />
          </div>
          <h3 class="text-sm font-semibold text-foreground">
            {{ $t(`tenant.ai.guidePage.features.${feature.key}.title`) }}
          </h3>
          <p class="mt-1 text-xs leading-relaxed text-muted-foreground">
            {{ $t(`tenant.ai.guidePage.features.${feature.key}.desc`) }}
          </p>
        </router-link>
      </div>
    </div>

    <!-- Quick Start -->
    <Card :title="$t('tenant.ai.guidePage.quickStartTitle')">
      <div class="space-y-4">
        <router-link
          v-for="(step, idx) in quickSteps"
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
                {{ $t(`tenant.ai.guidePage.quickStart.${step.key}.title`) }}
              </span>
            </div>
            <p class="mt-1 text-xs text-muted-foreground">
              {{ $t(`tenant.ai.guidePage.quickStart.${step.key}.desc`) }}
            </p>
          </div>
          <IconifyIcon
            icon="lucide:chevron-right"
            class="mt-2 size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
          />
        </router-link>
      </div>
    </Card>

    <!-- FAQ -->
    <Card :title="$t('tenant.ai.guidePage.faqTitle')">
      <Collapse :bordered="false" class="bg-transparent">
        <CollapsePanel
          v-for="key in faqKeys"
          :key="key"
          :header="$t(`tenant.ai.guidePage.faq.${key}.q`)"
        >
          <p class="text-sm text-muted-foreground">
            {{ $t(`tenant.ai.guidePage.faq.${key}.a`) }}
          </p>
        </CollapsePanel>
      </Collapse>
    </Card>
  </div>
</template>
