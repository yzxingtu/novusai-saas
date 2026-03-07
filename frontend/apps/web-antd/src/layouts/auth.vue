<script lang="ts" setup>
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';

import { usePublicConfigStore } from '#/store';

const publicConfigStore = usePublicConfigStore();

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
    class="relative flex min-h-screen items-center justify-center bg-gradient-to-br from-background via-background to-primary/5 px-4 py-8"
  >
    <!-- Background decorative elements -->
    <div class="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        class="absolute -left-20 -top-20 size-96 rounded-full bg-primary/5 blur-3xl"
      />
      <div
        class="absolute -bottom-20 -right-20 size-80 rounded-full bg-primary/3 blur-3xl"
      />
    </div>

    <!-- Auth card -->
    <div
      class="relative z-10 w-full max-w-[420px] rounded-2xl border border-border/60 bg-card/80 px-8 py-10 shadow-xl backdrop-blur-sm sm:px-10"
    >
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

      <!-- Page content (login / register / forget-password) -->
      <RouterView />
    </div>
  </div>
</template>
