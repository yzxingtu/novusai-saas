<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';
import {
  buildHelpFaqs,
  buildHelpJourneys,
  buildHelpResources,
} from '#/views/user/modules/help-center';

defineOptions({ name: 'UserHelpCenter' });

const router = useRouter();
const activeFaqKey = ref('1');

const journeys = computed(() => buildHelpJourneys($t));
const resources = computed(() => buildHelpResources($t));
const faqs = computed(() => buildHelpFaqs($t));

const bestPractices = computed(() => {
  return [
    {
      icon: 'lucide:target',
      key: 'clear',
      text: $t('user.helpCenter.bestPractices.clear'),
    },
    {
      icon: 'lucide:paperclip',
      key: 'attachment',
      text: $t('user.helpCenter.bestPractices.attachment'),
    },
    {
      icon: 'lucide:history',
      key: 'conversation',
      text: $t('user.helpCenter.bestPractices.conversation'),
    },
    {
      icon: 'lucide:download',
      key: 'export',
      text: $t('user.helpCenter.bestPractices.export'),
    },
  ];
});

function navigateTo(path: string) {
  void router.push(path);
}

function toggleFaq(key: string) {
  activeFaqKey.value = activeFaqKey.value === key ? '' : key;
}
</script>

<template>
  <div class="space-y-6">
    <section
      class="relative overflow-hidden rounded-[32px] border border-border/70 bg-card px-6 py-7 shadow-sm sm:px-8"
    >
      <div
        class="absolute inset-x-10 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent"
      ></div>
      <div
        class="absolute -right-24 top-0 size-72 rounded-full bg-primary/10 blur-3xl"
      ></div>
      <div
        class="absolute left-0 top-1/2 size-56 -translate-y-1/2 rounded-full bg-emerald-500/10 blur-3xl"
      ></div>

      <div
        class="relative grid gap-8 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]"
      >
        <div class="space-y-5">
          <div
            class="bg-primary/8 inline-flex items-center gap-2 rounded-full border border-primary/20 px-3 py-1 text-xs font-medium text-primary"
          >
            <IconifyIcon icon="lucide:life-buoy" class="size-3.5" />
            {{ $t('user.helpCenter.badge') }}
          </div>
          <div>
            <h1
              class="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
            >
              {{ $t('user.helpCenter.title') }}
            </h1>
            <p
              class="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base"
            >
              {{ $t('user.helpCenter.description') }}
            </p>
          </div>
          <div class="flex flex-wrap gap-3">
            <button
              class="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/15 transition-all hover:scale-[1.01] hover:shadow-xl hover:shadow-primary/20"
              type="button"
              @click="navigateTo('/agents')"
            >
              {{ $t('user.helpCenter.primaryCta') }}
              <IconifyIcon icon="lucide:arrow-up-right" class="size-4" />
            </button>
            <button
              class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary"
              type="button"
              @click="navigateTo('/ai-chat')"
            >
              <IconifyIcon icon="lucide:messages-square" class="size-4" />
              {{ $t('user.helpCenter.secondaryCta') }}
            </button>
          </div>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <div
            v-for="resource in resources"
            :key="resource.path"
            class="rounded-[24px] border border-border/60 bg-background/90 p-4 shadow-sm"
          >
            <span
              class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
            >
              <IconifyIcon :icon="resource.icon" class="size-5" />
            </span>
            <h2 class="mt-4 text-base font-semibold text-foreground">
              {{ resource.title }}
            </h2>
            <p class="mt-2 text-sm leading-6 text-muted-foreground">
              {{ resource.description }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <section
      class="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]"
    >
      <div
        class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
      >
        <div class="flex items-center gap-3">
          <span
            class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
          >
            <IconifyIcon icon="lucide:map" class="size-5" />
          </span>
          <div>
            <h2 class="text-xl font-semibold text-foreground">
              {{ $t('user.helpCenter.getStartedTitle') }}
            </h2>
            <p class="mt-1 text-sm text-muted-foreground">
              {{ $t('user.helpCenter.getStartedDesc') }}
            </p>
          </div>
        </div>

        <div class="mt-5 grid gap-3">
          <button
            v-for="(journey, index) in journeys"
            :key="journey.path"
            class="group flex items-start gap-4 rounded-[22px] border border-border/60 bg-background/80 px-4 py-4 text-left transition-all hover:border-primary/25 hover:bg-primary/5"
            type="button"
            @click="navigateTo(journey.path)"
          >
            <span
              class="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
            >
              <IconifyIcon :icon="journey.icon" class="size-4.5" />
            </span>
            <span class="min-w-0 flex-1">
              <span
                class="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground"
              >
                {{ $t('user.portal.stepLabel', { index: index + 1 }) }}
              </span>
              <span class="mt-2 block text-base font-semibold text-foreground">
                {{ journey.title }}
              </span>
              <span class="mt-1 block text-sm leading-6 text-muted-foreground">
                {{ journey.description }}
              </span>
            </span>
            <IconifyIcon
              icon="lucide:arrow-right"
              class="mt-1 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
            />
          </button>
        </div>
      </div>

      <div
        class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
      >
        <div class="flex items-center gap-3">
          <span
            class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
          >
            <IconifyIcon icon="lucide:badge-info" class="size-5" />
          </span>
          <div>
            <h2 class="text-xl font-semibold text-foreground">
              {{ $t('user.helpCenter.bestPracticesTitle') }}
            </h2>
            <p class="mt-1 text-sm text-muted-foreground">
              {{ $t('user.helpCenter.bestPracticesDesc') }}
            </p>
          </div>
        </div>

        <div class="mt-5 space-y-3">
          <div
            v-for="practice in bestPractices"
            :key="practice.key"
            class="flex items-start gap-3 rounded-[22px] border border-border/60 bg-background/80 p-4"
          >
            <span
              class="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
            >
              <IconifyIcon :icon="practice.icon" class="size-4.5" />
            </span>
            <p class="text-sm leading-7 text-muted-foreground">
              {{ practice.text }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <section
      class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="text-xl font-semibold text-foreground">
            {{ $t('user.helpCenter.faqTitle') }}
          </h2>
          <p class="mt-1 text-sm text-muted-foreground">
            {{ $t('user.helpCenter.faqDesc') }}
          </p>
        </div>
        <button
          class="inline-flex items-center gap-2 rounded-full border border-border/70 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary"
          type="button"
          @click="navigateTo('/ai-chat')"
        >
          {{ $t('user.helpCenter.askAiCta') }}
        </button>
      </div>

      <div class="mt-5 space-y-3">
        <div
          v-for="(faq, index) in faqs"
          :key="faq.question"
          class="overflow-hidden rounded-[22px] border border-border/60 bg-background/80"
        >
          <button
            class="flex w-full items-start gap-3 px-4 py-4 text-left"
            type="button"
            @click="toggleFaq(String(index + 1))"
          >
            <span
              class="mt-1 flex size-8 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
            >
              <IconifyIcon :icon="faq.icon" class="size-4" />
            </span>
            <span class="min-w-0 flex-1">
              <span class="text-sm font-semibold text-foreground">
                {{ faq.question }}
              </span>
            </span>
            <IconifyIcon
              :icon="
                activeFaqKey === String(index + 1)
                  ? 'lucide:minus'
                  : 'lucide:plus'
              "
              class="mt-1 size-4 shrink-0 text-muted-foreground"
            />
          </button>
          <div
            v-if="activeFaqKey === String(index + 1)"
            class="border-t border-border/60 px-4 py-4"
          >
            <p class="text-sm leading-7 text-muted-foreground">
              {{ faq.answer }}
            </p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
