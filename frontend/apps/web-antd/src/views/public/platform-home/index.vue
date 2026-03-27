<script setup lang="ts">
import { computed, onMounted } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { LanguageToggle, ThemeToggle } from '@vben/layouts';
import { preferences } from '@vben/preferences';

import { $t } from '#/locales';
import { usePublicConfigStore } from '#/store';
import { resolveCopyrightDisplay } from '#/utils/public-branding';

defineOptions({ name: 'PlatformPublicHome' });

const publicConfigStore = usePublicConfigStore();

const brandName = computed(() => {
  return publicConfigStore.platformBrand?.siteName || preferences.app.name;
});

const brandDescription = computed(() => {
  return (
    publicConfigStore.platformBrand?.siteDescription ||
    $t('public.platformHome.fallbackDescription')
  );
});

const brandLogo = computed(() => {
  return publicConfigStore.platformBrand?.logo || preferences.logo.source;
});

const footerBranding = computed(() =>
  resolveCopyrightDisplay(preferences.copyright),
);

const capabilityCards = computed(() => {
  return [
    {
      description: $t('public.platformHome.capabilities.tenancy.description'),
      icon: 'lucide:building-2',
      title: $t('public.platformHome.capabilities.tenancy.title'),
    },
    {
      description: $t('public.platformHome.capabilities.ai.description'),
      icon: 'lucide:brain-circuit',
      title: $t('public.platformHome.capabilities.ai.title'),
    },
    {
      description: $t('public.platformHome.capabilities.security.description'),
      icon: 'lucide:shield-check',
      title: $t('public.platformHome.capabilities.security.title'),
    },
    {
      description: $t('public.platformHome.capabilities.extension.description'),
      icon: 'lucide:puzzle',
      title: $t('public.platformHome.capabilities.extension.title'),
    },
  ];
});

const architectureCards = computed(() => {
  return [
    {
      description: $t('public.platformHome.architecture.platform.description'),
      icon: 'lucide:layout-dashboard',
      title: $t('public.platformHome.architecture.platform.title'),
    },
    {
      description: $t('public.platformHome.architecture.tenant.description'),
      icon: 'lucide:briefcase-business',
      title: $t('public.platformHome.architecture.tenant.title'),
    },
    {
      description: $t('public.platformHome.architecture.user.description'),
      icon: 'lucide:sparkles',
      title: $t('public.platformHome.architecture.user.title'),
    },
  ];
});

const highlights = computed(() => {
  return [
    $t('public.platformHome.highlights.branding'),
    $t('public.platformHome.highlights.rbac'),
    $t('public.platformHome.highlights.rag'),
    $t('public.platformHome.highlights.workflow'),
  ];
});

function scrollToSection(id: string) {
  document.querySelector<HTMLElement>(`#${id}`)?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  });
}

onMounted(async () => {
  await publicConfigStore.loadPlatformConfig().catch(() => {});
});
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <header
      class="sticky top-0 z-40 border-b border-border/70 bg-background/92 backdrop-blur"
    >
      <div
        class="mx-auto flex w-full max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8"
      >
        <div class="flex min-w-0 items-center gap-3">
          <img
            v-if="brandLogo"
            :src="brandLogo"
            :alt="brandName"
            class="size-10 rounded-2xl object-contain shadow-sm"
          />
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-foreground">
              {{ brandName }}
            </p>
            <p class="truncate text-xs text-muted-foreground">
              {{ $t('public.platformHome.headerEyebrow') }}
            </p>
          </div>
        </div>

        <div class="ml-auto flex items-center gap-1">
          <ThemeToggle class="mt-[2px]" />
          <LanguageToggle />
        </div>
      </div>
    </header>

    <main class="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8">
      <section
        class="relative overflow-hidden rounded-[36px] border border-border/70 bg-card px-6 py-8 shadow-sm sm:px-8 lg:px-10"
      >
        <div class="absolute -right-24 top-0 size-80 rounded-full bg-primary/10 blur-3xl"></div>
        <div class="absolute left-0 top-1/2 size-64 -translate-y-1/2 rounded-full bg-sky-500/10 blur-3xl"></div>

        <div class="relative grid gap-8 lg:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
          <div class="space-y-5">
            <div
              class="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/8 px-3 py-1 text-xs font-medium text-primary"
            >
              <IconifyIcon icon="lucide:orbit" class="size-3.5" />
              {{ $t('public.platformHome.badge') }}
            </div>

            <div class="space-y-3">
              <h1 class="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">
                {{ $t('public.platformHome.heroTitle', { brand: brandName }) }}
              </h1>
              <p class="max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
                {{ brandDescription }}
              </p>
              <p class="max-w-2xl text-sm leading-7 text-muted-foreground">
                {{ $t('public.platformHome.heroDescription') }}
              </p>
            </div>

            <div class="flex flex-wrap gap-3">
              <button
                class="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/15 transition-all hover:scale-[1.01] hover:shadow-xl hover:shadow-primary/20"
                type="button"
                @click="scrollToSection('platform-architecture')"
              >
                <IconifyIcon icon="lucide:layers-3" class="size-4" />
                {{ $t('public.platformHome.cta.architecture') }}
              </button>
              <button
                class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary"
                type="button"
                @click="scrollToSection('platform-next-steps')"
              >
                <IconifyIcon icon="lucide:waypoints" class="size-4" />
                {{ $t('public.platformHome.cta.demoFlow') }}
              </button>
            </div>
          </div>

          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <div
              class="rounded-[24px] border border-border/60 bg-background/90 p-5 shadow-sm"
            >
              <span
                class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
              >
                <IconifyIcon icon="lucide:building" class="size-5" />
              </span>
              <h2 class="mt-4 text-base font-semibold text-foreground">
                {{ $t('public.platformHome.tenantAccessTitle') }}
              </h2>
              <p class="mt-2 text-sm leading-6 text-muted-foreground">
                {{ $t('public.platformHome.tenantAccessDescription') }}
              </p>
            </div>

            <div
              class="rounded-[24px] border border-border/60 bg-background/90 p-5 shadow-sm"
            >
              <span
                class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
              >
                <IconifyIcon icon="lucide:check-check" class="size-5" />
              </span>
              <h2 class="mt-4 text-base font-semibold text-foreground">
                {{ $t('public.platformHome.highlightTitle') }}
              </h2>
              <ul class="mt-3 space-y-2 text-sm leading-6 text-muted-foreground">
                <li
                  v-for="item in highlights"
                  :key="item"
                  class="flex items-start gap-2"
                >
                  <IconifyIcon
                    icon="lucide:arrow-right"
                    class="mt-1 size-3.5 shrink-0 text-primary"
                  />
                  <span>{{ item }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section class="grid gap-4 lg:grid-cols-4">
        <article
          v-for="card in capabilityCards"
          :key="card.title"
          class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm"
        >
          <span
            class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
          >
            <IconifyIcon :icon="card.icon" class="size-5" />
          </span>
          <h2 class="mt-4 text-base font-semibold text-foreground">
            {{ card.title }}
          </h2>
          <p class="mt-2 text-sm leading-6 text-muted-foreground">
            {{ card.description }}
          </p>
        </article>
      </section>

      <section
        id="platform-architecture"
        class="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]"
      >
        <div
          id="platform-next-steps"
          class="rounded-[32px] border border-border/70 bg-card p-6 shadow-sm"
        >
          <div class="flex items-start gap-3">
            <span
              class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:layers-3" class="size-5" />
            </span>
            <div>
              <h2 class="text-xl font-semibold text-foreground">
                {{ $t('public.platformHome.architectureTitle') }}
              </h2>
              <p class="mt-1 text-sm text-muted-foreground">
                {{ $t('public.platformHome.architectureDescription') }}
              </p>
            </div>
          </div>

          <div class="mt-5 grid gap-3">
            <div
              v-for="card in architectureCards"
              :key="card.title"
              class="rounded-[22px] border border-border/60 bg-background/80 p-4"
            >
              <div class="flex items-start gap-3">
                <span
                  class="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
                >
                  <IconifyIcon :icon="card.icon" class="size-4.5" />
                </span>
                <div class="min-w-0">
                  <h3 class="text-sm font-semibold text-foreground">
                    {{ card.title }}
                  </h3>
                  <p class="mt-2 text-sm leading-6 text-muted-foreground">
                    {{ card.description }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-[32px] border border-border/70 bg-card p-6 shadow-sm">
          <div class="flex items-start gap-3">
            <span
              class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:waypoints" class="size-5" />
            </span>
            <div>
              <h2 class="text-xl font-semibold text-foreground">
                {{ $t('public.platformHome.nextStepsTitle') }}
              </h2>
              <p class="mt-1 text-sm text-muted-foreground">
                {{ $t('public.platformHome.nextStepsDescription') }}
              </p>
            </div>
          </div>

          <div class="mt-5 space-y-3">
            <div class="rounded-[22px] border border-border/60 bg-background/80 p-4">
              <h3 class="text-sm font-semibold text-foreground">
                {{ $t('public.platformHome.nextSteps.platformTitle') }}
              </h3>
              <p class="mt-2 text-sm leading-6 text-muted-foreground">
                {{ $t('public.platformHome.nextSteps.platformDescription') }}
              </p>
            </div>
            <div class="rounded-[22px] border border-border/60 bg-background/80 p-4">
              <h3 class="text-sm font-semibold text-foreground">
                {{ $t('public.platformHome.nextSteps.tenantTitle') }}
              </h3>
              <p class="mt-2 text-sm leading-6 text-muted-foreground">
                {{ $t('public.platformHome.nextSteps.tenantDescription') }}
              </p>
            </div>
            <div class="rounded-[22px] border border-border/60 bg-background/80 p-4">
              <h3 class="text-sm font-semibold text-foreground">
                {{ $t('public.platformHome.nextSteps.userTitle') }}
              </h3>
              <p class="mt-2 text-sm leading-6 text-muted-foreground">
                {{ $t('public.platformHome.nextSteps.userDescription') }}
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>

    <footer
      v-if="footerBranding.visible"
      class="border-t border-border/70 px-4 py-4 text-center text-xs text-muted-foreground sm:px-6 lg:px-8"
    >
      {{ footerBranding.companyName }}
      <span v-if="footerBranding.meta">{{ footerBranding.meta }}</span>
    </footer>
  </div>
</template>
