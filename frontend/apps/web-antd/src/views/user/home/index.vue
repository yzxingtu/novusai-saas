<script setup lang="ts">
/**
 * 公开首页 — 游客/登录用户均可访问
 * 平台域名：显示平台介绍 + 核心能力
 * 租户域名：显示租户品牌 + 登录/注册入口
 */
import { computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';

import {
  TENANT_LOGIN_PATH,
  USER_LOGIN_PATH,
} from '#/constants/endpoints';
import { $t } from '#/locales';
import { usePublicConfigStore } from '#/store';

defineOptions({ name: 'UserHome' });

const router = useRouter();
const publicConfigStore = usePublicConfigStore();

// 域名感知
const isTenantDomain = computed(() => publicConfigStore.isDomainTenantDomain);

// ── 平台域名品牌 ──────────────────────────────────────────
const platformName = computed(() => {
  return (
    publicConfigStore.platformBrand?.siteName ||
    preferences.app.name ||
    'NovusAI'
  );
});

const platformDescription = computed(() => {
  return publicConfigStore.platformBrand?.siteDescription || '';
});

const platformLogo = computed(() => {
  return (
    publicConfigStore.platformBrand?.logo ||
    preferences.logo.source ||
    ''
  );
});

// ── 租户域名品牌 ──────────────────────────────────────────
const tenantName = computed(() => {
  return (
    publicConfigStore.tenantBrand?.siteName ||
    publicConfigStore.tenantConfig?.tenantName ||
    preferences.app.name ||
    'NovusAI'
  );
});

const tenantDescription = computed(() => {
  return (
    publicConfigStore.tenantBrand?.siteDescription || ''
  );
});

const tenantLogo = computed(() => {
  return (
    publicConfigStore.tenantBrand?.logo ||
    preferences.logo.source ||
    ''
  );
});

// 注册是否可用
const registrationEnabled = computed(() => publicConfigStore.isRegistrationEnabled);

interface FeatureItem {
  color: string;
  desc: string;
  icon: string;
  label: string;
}

const features = computed<FeatureItem[]>(() => [
  {
    color: 'text-primary',
    desc: $t('user.home.featureAIDesc'),
    icon: 'lucide:bot',
    label: $t('user.home.featureAI'),
  },
  {
    color: 'text-success',
    desc: $t('user.home.featureMultiTenantDesc'),
    icon: 'lucide:building-2',
    label: $t('user.home.featureMultiTenant'),
  },
  {
    color: 'text-warning',
    desc: $t('user.home.featureSecurityDesc'),
    icon: 'lucide:lock',
    label: $t('user.home.featureSecurity'),
  },
]);

function navigateTo(path: string) {
  router.push(path);
}

onMounted(() => {
  publicConfigStore.loadPlatformConfig();
  if (publicConfigStore.isDomainTenantDomain) {
    publicConfigStore.loadTenantConfig();
  }
});
</script>

<template>
  <!-- ═══════ 租户域名：租户专属落地页 ═══════ -->
  <div v-if="isTenantDomain" class="flex flex-col items-center gap-10 py-6">
    <!-- Hero -->
    <div
      class="relative w-full overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-primary/10 via-primary/5 to-transparent px-6 py-16 sm:px-10 sm:py-20"
    >
      <div class="relative z-10 flex flex-col items-center text-center">
        <img
          v-if="tenantLogo"
          :src="tenantLogo"
          :alt="tenantName"
          class="mb-5 size-20 rounded-2xl object-contain shadow-md sm:size-24"
        />
        <h1 class="text-3xl font-bold text-foreground sm:text-4xl">
          {{ $t('user.home.welcomeTo', { name: tenantName }) }}
        </h1>
        <p
          v-if="tenantDescription"
          class="mt-3 max-w-lg text-sm text-muted-foreground sm:text-base"
        >
          {{ tenantDescription }}
        </p>
        <p v-else class="mt-3 max-w-lg text-sm text-muted-foreground sm:text-base">
          {{ $t('user.home.tenantDesc') }}
        </p>

        <!-- CTA Buttons -->
        <div class="mt-8 flex flex-wrap items-center justify-center gap-3">
          <button
            class="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground shadow-md transition-all hover:shadow-lg hover:brightness-110"
            @click="navigateTo(USER_LOGIN_PATH)"
          >
            <IconifyIcon icon="lucide:log-in" class="size-4" />
            {{ $t('user.home.signIn') }}
          </button>
          <button
            v-if="registrationEnabled"
            class="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-6 py-2.5 text-sm font-semibold text-foreground shadow-sm transition-all hover:border-primary/30 hover:shadow-md"
            @click="navigateTo('/auth/register')"
          >
            <IconifyIcon icon="lucide:user-plus" class="size-4" />
            {{ $t('user.home.signUp') }}
          </button>
        </div>
      </div>
      <!-- Decorative -->
      <div class="absolute -right-12 -top-12 size-48 rounded-full bg-primary/5" />
      <div class="absolute -bottom-8 -left-8 size-36 rounded-full bg-primary/3" />
    </div>

    <!-- Features -->
    <div class="w-full">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div
          v-for="feature in features"
          :key="feature.label"
          class="rounded-xl border border-border bg-card p-6 transition-shadow hover:shadow-sm"
        >
          <div
            class="mb-3 flex size-10 items-center justify-center rounded-lg bg-accent"
          >
            <IconifyIcon :icon="feature.icon" class="size-5" :class="feature.color" />
          </div>
          <h3 class="text-sm font-semibold text-foreground">{{ feature.label }}</h3>
          <p class="mt-1 text-xs text-muted-foreground">{{ feature.desc }}</p>
        </div>
      </div>
    </div>

    <!-- Tenant Admin Link -->
    <button
      class="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
      @click="navigateTo(TENANT_LOGIN_PATH)"
    >
      <IconifyIcon icon="lucide:shield" class="size-3.5" />
      {{ $t('user.home.tenantAdmin') }}
    </button>
  </div>

  <!-- ═══════ 平台域名：平台介绍页 ═══════ -->
  <div v-else class="space-y-8">
    <!-- Hero Section -->
    <div
      class="relative overflow-hidden rounded-xl border border-border bg-gradient-to-br from-primary/8 via-primary/4 to-transparent px-6 py-10 sm:px-10 sm:py-14"
    >
      <div class="relative z-10 flex flex-col items-center text-center">
        <img
          v-if="platformLogo"
          :src="platformLogo"
          :alt="platformName"
          class="mb-4 size-16 rounded-xl object-contain sm:size-20"
        />
        <h1 class="text-2xl font-bold text-foreground sm:text-3xl">
          {{ platformName }}
        </h1>
        <p
          v-if="platformDescription"
          class="mt-2 max-w-lg text-sm text-muted-foreground sm:text-base"
        >
          {{ platformDescription }}
        </p>
        <p v-else class="mt-2 max-w-lg text-sm text-muted-foreground sm:text-base">
          {{ $t('user.home.heroDesc') }}
        </p>
      </div>
      <!-- Decorative -->
      <div class="absolute -right-10 -top-10 size-40 rounded-full bg-primary/5" />
      <div class="absolute -bottom-6 -left-6 size-28 rounded-full bg-primary/3" />
    </div>

    <!-- Features Section -->
    <div>
      <h2 class="mb-4 text-lg font-semibold text-foreground">
        {{ $t('user.home.features') }}
      </h2>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div
          v-for="feature in features"
          :key="feature.label"
          class="rounded-lg border border-border bg-card p-5"
        >
          <div
            class="mb-3 flex size-10 items-center justify-center rounded-lg bg-accent"
          >
            <IconifyIcon :icon="feature.icon" class="size-5" :class="feature.color" />
          </div>
          <h3 class="text-sm font-semibold text-foreground">{{ feature.label }}</h3>
          <p class="mt-1 text-xs text-muted-foreground">{{ feature.desc }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
