<script lang="ts" setup>
/**
 * User Auth Layout — 暖彩花园风 / Warm Garden Style
 *
 * 暖米色底 + 3 个暖色块漂浮 + 白卡片顶部彩条
 * Warm beige + 3 warm blobs + white card with top gradient accent
 */
import { computed, onMounted } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { LanguageToggle, ThemeToggle } from '@vben/layouts';
import { preferences } from '@vben/preferences';
import { usePreferences } from '@vben/preferences';

import { usePublicConfigStore } from '#/store';

const publicConfigStore = usePublicConfigStore();
const { isDark } = usePreferences();

onMounted(() => {
  publicConfigStore.loadPlatformConfig();
  if (publicConfigStore.isDomainTenantDomain) {
    publicConfigStore.loadTenantConfig();
  }
});

const isTenantDomain = computed(() => publicConfigStore.isDomainTenantDomain);

const siteLogo = computed(() => {
  if (isTenantDomain.value) {
    return (
      publicConfigStore.tenantBrand?.logo ||
      preferences.logo.source ||
      ''
    );
  }
  return preferences.logo.source || '';
});

const siteName = computed(() => {
  if (isTenantDomain.value) {
    return (
      publicConfigStore.tenantBrand?.siteName ||
      preferences.app.name ||
      'NovusAI'
    );
  }
  return preferences.app.name || 'NovusAI';
});
</script>

<template>
  <div
    :class="[isDark ? 'dark' : '']"
    class="user-auth-root relative flex min-h-screen items-center justify-center overflow-y-auto px-4 py-8"
  >
    <!-- Toolbar -->
    <div
      class="bg-accent/80 absolute right-4 top-4 z-20 flex items-center gap-1 rounded-full px-2 py-1 backdrop-blur"
    >
      <LanguageToggle v-if="preferences.widget.languageToggle" />
      <ThemeToggle v-if="preferences.widget.themeToggle" />
    </div>

    <!-- 3 warm blobs / 3 个大暖色块 -->
    <div class="user-blob user-blob-1 pointer-events-none fixed" />
    <div class="user-blob user-blob-2 pointer-events-none fixed" />
    <div class="user-blob user-blob-3 pointer-events-none fixed" />

    <!-- Card with top accent bar / 带顶部彩条的卡片 -->
    <div
      class="user-auth-card relative z-10 flex w-full max-w-[420px] min-h-0 flex-col overflow-hidden rounded-3xl border border-black/[0.06] bg-white px-8 py-10 shadow-[0_20px_60px_rgba(0,0,0,0.08),0_1px_3px_rgba(0,0,0,0.04)] sm:px-10"
    >
      <!-- Top gradient accent / 顶部 4px 彩条 -->
      <div
        class="user-card-accent absolute left-0 right-0 top-0 h-1 shrink-0"
      />

      <!-- Branding -->
      <div class="mb-8 flex flex-col items-center">
        <img
          v-if="siteLogo"
          :src="siteLogo"
          :alt="siteName"
          class="mb-3 size-12 rounded-xl object-contain"
        />
        <div
          v-else
          class="mb-3 flex size-12 items-center justify-center rounded-xl bg-primary/10"
        >
          <IconifyIcon icon="lucide:zap" class="size-6 text-primary" />
        </div>
        <span class="text-lg font-bold text-foreground">{{ siteName }}</span>
      </div>

      <!-- Page content -->
      <RouterView />
    </div>

    <!-- Copyright -->
    <div
      v-if="preferences.copyright.enable"
      class="text-muted-foreground absolute bottom-4 left-0 right-0 text-center text-xs"
    >
      {{ preferences.copyright.companyName }}
      {{ preferences.copyright.companySiteLink }}
    </div>
  </div>
</template>

<style scoped>
.user-auth-root {
  background-color: #fff8f0;
}

.dark .user-auth-root {
  background-color: hsl(var(--background));
}

.user-blob {
  border-radius: 50%;
  will-change: transform;
}

.user-blob-1 {
  width: 500px;
  height: 500px;
  top: -10%;
  right: 10%;
  background: radial-gradient(
    circle,
    rgba(251, 146, 60, 0.25) 0%,
    transparent 70%
  );
  animation: float-a 16s ease-in-out infinite;
}

.dark .user-blob-1 {
  background: radial-gradient(
    circle,
    rgba(251, 146, 60, 0.12) 0%,
    transparent 70%
  );
}

.user-blob-2 {
  width: 450px;
  height: 450px;
  top: 20%;
  left: -5%;
  background: radial-gradient(
    circle,
    rgba(167, 139, 250, 0.2) 0%,
    transparent 70%
  );
  animation: float-b 20s ease-in-out infinite;
}

.dark .user-blob-2 {
  background: radial-gradient(
    circle,
    rgba(167, 139, 250, 0.1) 0%,
    transparent 70%
  );
}

.user-blob-3 {
  width: 350px;
  height: 350px;
  bottom: -5%;
  right: 30%;
  background: radial-gradient(
    circle,
    rgba(251, 191, 36, 0.15) 0%,
    transparent 70%
  );
  animation: float-c 14s ease-in-out infinite;
}

.dark .user-blob-3 {
  background: radial-gradient(
    circle,
    rgba(251, 191, 36, 0.08) 0%,
    transparent 70%
  );
}

@keyframes float-a {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(40px, -50px) scale(1.08);
  }
}

@keyframes float-b {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(-60px, 30px) scale(1.05);
  }
}

@keyframes float-c {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(30px, -40px) scale(1.06);
  }
}

.user-card-accent {
  background: linear-gradient(90deg, #f97316, #ec4899, #8b5cf6);
}

.dark .user-card-accent {
  opacity: 0.9;
}

.user-auth-card {
  animation: card-pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

.dark .user-auth-card {
  background: hsl(var(--card) / 0.95);
  border-color: hsl(var(--border) / 0.5);
  box-shadow:
    0 20px 60px rgba(0, 0, 0, 0.15),
    0 1px 3px rgba(0, 0, 0, 0.08);
}

@keyframes card-pop {
  from {
    opacity: 0;
    transform: scale(0.92) translateY(10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
