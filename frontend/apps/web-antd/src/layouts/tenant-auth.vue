<script lang="ts" setup>
import { computed, onMounted } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { LanguageToggle, ThemeToggle } from '@vben/layouts';
import {
  preferences,
  updatePreferences,
  usePreferences,
} from '@vben/preferences';

import { $t } from '#/locales';
import { usePublicConfigStore } from '#/store/shared/public-config';
import { resolveCopyrightDisplay } from '#/utils/public-branding';

defineOptions({ name: 'TenantAuthLayout' });

const publicConfigStore = usePublicConfigStore();

onMounted(() => {
  updatePreferences({
    theme: { builtinType: 'violet' },
  });
});

const appName = computed(() => preferences.app.name);
const logo = computed(() => preferences.logo.source);
const logoDark = computed(() => preferences.logo.sourceDark);
const loginBg = computed(() => publicConfigStore.tenantBrand?.loginBg);
const siteDescription = computed(
  () => publicConfigStore.tenantBrand?.siteDescription,
);
const footerBranding = computed(() =>
  resolveCopyrightDisplay(preferences.copyright),
);

const { isDark } = usePreferences();

const logoSrc = computed(() => {
  if (isDark.value && logoDark.value) {
    return logoDark.value;
  }
  return logo.value;
});
</script>

<template>
  <div
    :class="[isDark ? 'dark' : '']"
    class="flex min-h-screen select-none overflow-hidden"
  >
    <!-- Toolbar -->
    <div
      class="absolute right-4 top-4 z-10 flex items-center gap-1 rounded-full bg-accent/80 px-2 py-1 backdrop-blur"
    >
      <LanguageToggle v-if="preferences.widget.languageToggle" />
      <ThemeToggle v-if="preferences.widget.themeToggle" />
    </div>

    <!-- Left: Form Panel -->
    <div
      class="tenant-form-panel relative flex flex-1 flex-col items-center justify-center px-6 lg:px-12"
    >
      <!-- Mobile logo -->
      <div class="mb-8 flex items-center gap-3 lg:hidden">
        <img v-if="logoSrc" :alt="appName" :src="logoSrc" width="36" />
        <span class="text-lg font-medium text-foreground">{{ appName }}</span>
      </div>

      <div class="w-full max-w-md">
        <RouterView />
      </div>

      <!-- Copyright -->
      <div
        v-if="footerBranding.visible"
        class="absolute bottom-4 text-center text-xs text-muted-foreground"
      >
        {{ footerBranding.companyName }}
        <span v-if="footerBranding.meta">{{ footerBranding.meta }}</span>
      </div>
    </div>

    <!-- Right: Illustration Panel -->
    <div
      class="tenant-illustration relative hidden flex-col items-center justify-center overflow-hidden lg:flex lg:w-[45%]"
      :style="
        loginBg
          ? {
              backgroundImage: `url(${loginBg})`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
            }
          : {}
      "
    >
      <!-- Dark overlay when using custom background image -->
      <div v-if="loginBg" class="absolute inset-0 bg-black/60"></div>
      <!-- Decorative circles with floating animation -->
      <div
        class="animate-float-slow absolute -right-20 -top-20 size-80 rounded-full opacity-20"
        style="
          background: radial-gradient(
            circle,
            hsl(var(--primary) / 60%) 0%,
            transparent 70%
          );
        "
      ></div>
      <div
        class="animate-float-slower absolute -bottom-32 -left-32 size-96 rounded-full opacity-15"
        style="
          background: radial-gradient(
            circle,
            hsl(var(--primary) / 80%) 0%,
            transparent 70%
          );
        "
      ></div>
      <div
        class="animate-float-medium absolute left-10 top-1/4 size-40 rounded-full opacity-10"
        style="
          background: radial-gradient(
            circle,
            hsl(var(--primary) / 40%) 0%,
            transparent 70%
          );
        "
      ></div>

      <!-- Logo -->
      <div class="absolute left-8 top-8 flex items-center gap-3">
        <img v-if="logoSrc" :alt="appName" :src="logoSrc" width="36" />
        <span class="text-lg font-medium text-white/90">{{ appName }}</span>
      </div>

      <!-- Center content -->
      <div class="relative z-10 max-w-md px-12 text-center">
        <!-- Building Icon -->
        <div
          class="mx-auto mb-8 flex size-24 items-center justify-center rounded-3xl border border-primary/20 bg-white/10 shadow-2xl backdrop-blur-sm"
        >
          <IconifyIcon icon="lucide:building-2" class="text-5xl text-primary" />
        </div>

        <h2 class="mb-3 text-3xl font-bold text-white">
          {{ $t('authentication.tenantAdmin') }}
        </h2>
        <p class="mb-12 text-base leading-relaxed text-white/60">
          {{ siteDescription || $t('authentication.tenantAdminDesc') }}
        </p>

        <!-- Feature list -->
        <div class="space-y-5 text-left">
          <div class="flex items-start gap-4">
            <div
              class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/20"
            >
              <IconifyIcon icon="lucide:users" class="text-lg text-primary" />
            </div>
            <div>
              <div class="text-sm font-medium text-white/90">
                {{ $t('tenant.auth.featureTeam') }}
              </div>
              <div class="mt-0.5 text-xs text-white/40">
                {{ $t('tenant.auth.featureTeamDesc') }}
              </div>
            </div>
          </div>
          <div class="flex items-start gap-4">
            <div
              class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/20"
            >
              <IconifyIcon icon="lucide:bot" class="text-lg text-primary" />
            </div>
            <div>
              <div class="text-sm font-medium text-white/90">
                {{ $t('tenant.auth.featureAI') }}
              </div>
              <div class="mt-0.5 text-xs text-white/40">
                {{ $t('tenant.auth.featureAIDesc') }}
              </div>
            </div>
          </div>
          <div class="flex items-start gap-4">
            <div
              class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/20"
            >
              <IconifyIcon
                icon="lucide:bar-chart-3"
                class="text-lg text-primary"
              />
            </div>
            <div>
              <div class="text-sm font-medium text-white/90">
                {{ $t('tenant.auth.featureBusiness') }}
              </div>
              <div class="mt-0.5 text-xs text-white/40">
                {{ $t('tenant.auth.featureBusinessDesc') }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom gradient line -->
      <div
        class="absolute bottom-0 left-0 right-0 h-1"
        style="
          background: linear-gradient(
            90deg,
            transparent,
            hsl(var(--primary) / 60%),
            hsl(var(--primary)),
            transparent
          );
        "
      ></div>
    </div>
  </div>
</template>

<style scoped>
.tenant-illustration {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, hsl(var(--primary)), #000 74%) 0%,
    color-mix(in srgb, hsl(var(--primary)), #000 58%) 40%,
    color-mix(in srgb, hsl(var(--primary)), #000 70%) 100%
  );
}

.dark .tenant-illustration {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, hsl(var(--primary)), #000 78%) 0%,
    color-mix(in srgb, hsl(var(--primary)), #000 64%) 40%,
    color-mix(in srgb, hsl(var(--primary)), #000 74%) 100%
  );
}

.tenant-form-panel {
  background: linear-gradient(
    180deg,
    color-mix(in srgb, hsl(var(--primary)), #fff 97%) 0%,
    color-mix(in srgb, hsl(var(--primary)), #fff 94%) 100%
  );
}

.dark .tenant-form-panel {
  background: linear-gradient(
    180deg,
    hsl(var(--background-deep)) 0%,
    hsl(var(--background)) 100%
  );
}

@keyframes float-slow {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }

  50% {
    transform: translate(30px, -40px) scale(1.1);
  }
}

@keyframes float-slower {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }

  50% {
    transform: translate(-40px, 30px) scale(1.15);
  }
}

@keyframes float-medium {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }

  33% {
    transform: translate(20px, -30px) scale(1.08);
  }

  66% {
    transform: translate(-20px, 20px) scale(0.95);
  }
}

.animate-float-slow {
  animation: float-slow 8s ease-in-out infinite;
}

.animate-float-slower {
  animation: float-slower 12s ease-in-out infinite;
}

.animate-float-medium {
  animation: float-medium 10s ease-in-out infinite;
}
</style>
