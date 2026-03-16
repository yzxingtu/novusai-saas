<script setup lang="ts">
/**
 * 公开首页 — 游客/登录用户均可访问 / Public home — guests and logged-in users
 * 游客：显示平台/企业品牌 + 登录/注册入口
 * 已登录：显示工作台仪表板（欢迎信息 + 快捷操作）
 */
import { computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { VbenAvatar } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';
import { useUserStore } from '@vben/stores';

import {
  TENANT_LOGIN_PATH,
  USER_LOGIN_PATH,
} from '#/constants/endpoints';
import { $t } from '#/locales';
import { usePublicConfigStore } from '#/store';
import { TokenStorage } from '#/store/shared/token-storage';

defineOptions({ name: 'UserHome' });

const router = useRouter();
const publicConfigStore = usePublicConfigStore();
const userStore = useUserStore();

const isLoggedIn = computed(() => TokenStorage.hasToken('user'));

const currentUser = computed(() => userStore.userInfo);

const userAvatar = computed(() => {
  return currentUser.value?.avatar || preferences.app.defaultAvatar;
});

const userName = computed(() => {
  return currentUser.value?.realName || currentUser.value?.username || '';
});

interface QuickAction {
  color: string;
  desc: () => string;
  icon: string;
  label: () => string;
  path: string;
}

const quickActions = computed<QuickAction[]>(() => [
  {
    color: 'text-primary',
    desc: () => $t('user.dashboard.aiChatDesc'),
    icon: 'lucide:bot',
    label: () => $t('user.dashboard.aiChat'),
    path: '/ai-chat',
  },
  {
    color: 'text-primary',
    desc: () => $t('user.dashboard.myProfileDesc'),
    icon: 'lucide:user',
    label: () => $t('user.dashboard.myProfile'),
    path: '/settings/profile',
  },
  {
    color: 'text-warning',
    desc: () => $t('user.dashboard.changePasswordDesc'),
    icon: 'lucide:key-round',
    label: () => $t('user.dashboard.changePassword'),
    path: '/settings/password',
  },
]);

// Domain detection / 域名感知
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

// ── 企业域名品牌 ──────────────────────────────────────────
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

// Registration enabled / 注册是否可用
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
  {
    color: 'text-primary',
    desc: $t('user.home.featureRAGDesc'),
    icon: 'lucide:book-open',
    label: $t('user.home.featureRAG'),
  },
  {
    color: 'text-success',
    desc: $t('user.home.featurePluginDesc'),
    icon: 'lucide:puzzle',
    label: $t('user.home.featurePlugin'),
  },
  {
    color: 'text-warning',
    desc: $t('user.home.featureDomainDesc'),
    icon: 'lucide:globe',
    label: $t('user.home.featureDomain'),
  },
]);

/** Platform landing: first 3 as large cards, last 3 as compact rows / 平台落地页：前 3 大卡片，后 3 紧凑行 */
const featuresPrimary = computed(() => features.value.slice(0, 3));
const featuresSecondary = computed(() => features.value.slice(3, 6));

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
  <!-- ═══════ 已登录：工作台仪表板 ═══════ -->
  <div v-if="isLoggedIn" class="space-y-6">
    <!-- Welcome Hero -->
    <div
      class="relative overflow-hidden rounded-xl border border-border bg-card p-6 sm:p-8"
    >
      <div
        class="absolute inset-0 bg-gradient-to-br from-primary/6 via-transparent to-primary/3"
      />
      <div class="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-6">
        <VbenAvatar
          :src="userAvatar"
          :alt="userName"
          class="size-16 shrink-0 rounded-full ring-2 ring-background shadow-lg sm:size-20"
        />
        <div class="flex-1">
          <h1 class="text-xl font-bold text-foreground sm:text-2xl">
            {{ $t('user.dashboard.greeting', { name: userName }) }}
          </h1>
          <p class="mt-1 text-sm text-muted-foreground">
            {{ $t('user.dashboard.greetingDesc') }}
          </p>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div>
      <h2 class="mb-3 text-base font-semibold text-foreground">
        {{ $t('user.dashboard.quickActions') }}
      </h2>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <button
          v-for="action in quickActions"
          :key="action.path"
          class="flex items-start gap-4 rounded-xl border border-border bg-card p-5 text-left transition-all duration-150 hover:border-primary/30 hover:shadow-sm"
          @click="navigateTo(action.path)"
        >
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent"
          >
            <IconifyIcon :icon="action.icon" class="size-5" :class="action.color" />
          </div>
          <div>
            <h3 class="text-sm font-semibold text-foreground">
              {{ action.label() }}
            </h3>
            <p class="mt-0.5 text-xs text-muted-foreground">
              {{ action.desc() }}
            </p>
          </div>
        </button>
      </div>
    </div>
  </div>

  <!-- ═══════ 企业域名：企业专属落地页 ═══════ -->
  <div v-else-if="isTenantDomain" class="flex flex-col items-center gap-12 py-6">
    <!-- Hero：更大品牌空间、柔和渐变 -->
    <div
      class="relative w-full overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-primary/8 via-primary/3 to-transparent px-6 py-20 sm:px-12 sm:py-24"
    >
      <div class="relative z-10 flex flex-col items-center text-center">
        <img
          v-if="tenantLogo"
          :src="tenantLogo"
          :alt="tenantName"
          class="mb-6 size-24 rounded-2xl object-contain shadow-lg sm:size-28"
        />
        <h1 class="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          {{ $t('user.home.welcomeTo', { name: tenantName }) }}
        </h1>
        <p
          v-if="tenantDescription"
          class="mt-4 max-w-xl text-base text-muted-foreground sm:text-lg"
        >
          {{ tenantDescription }}
        </p>
        <p v-else class="mt-4 max-w-xl text-base text-muted-foreground sm:text-lg">
          {{ $t('user.home.tenantDesc') }}
        </p>

        <!-- CTA Buttons -->
        <div class="mt-10 flex flex-wrap items-center justify-center gap-3">
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
      <div class="absolute -right-16 -top-16 size-64 rounded-full bg-primary/5" />
      <div class="absolute -bottom-12 -left-12 size-48 rounded-full bg-primary/3" />
    </div>

    <!-- Features：两列、图标更精致、hover 效果 -->
    <div class="w-full">
      <h2 class="mb-6 text-center text-lg font-semibold text-foreground">
        {{ $t('user.home.features') }}
      </h2>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="feature in features"
          :key="feature.label"
          class="group flex items-start gap-4 rounded-xl border border-border bg-card p-6 transition-all duration-200 hover:border-primary/20 hover:shadow-md"
        >
          <div
            class="flex size-12 shrink-0 items-center justify-center rounded-xl bg-accent transition-colors group-hover:bg-primary/10"
          >
            <IconifyIcon :icon="feature.icon" class="size-6" :class="feature.color" />
          </div>
          <div class="min-w-0 flex-1">
            <h3 class="font-semibold text-foreground">{{ feature.label }}</h3>
            <p class="mt-1 text-sm text-muted-foreground">{{ feature.desc }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Tenant Admin：底部居中、分割线 -->
    <div class="flex w-full flex-col items-center gap-4 border-t border-border pt-8">
      <button
        class="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        @click="navigateTo(TENANT_LOGIN_PATH)"
      >
        <IconifyIcon icon="lucide:shield" class="size-4" />
        {{ $t('user.home.tenantAdmin') }}
      </button>
    </div>
  </div>

  <!-- ═══════ 平台域名：平台介绍页（简约专业，无登录按钮）═══════ -->
  <div v-else class="flex flex-col gap-12">
    <!-- Hero：渐变 + 装饰 + 动效 -->
    <div
      class="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-primary/15 via-primary/6 to-primary/2 px-6 py-14 sm:px-12 sm:py-20"
    >
      <!-- 装饰网格 -->
      <div
        class="pointer-events-none absolute inset-0 opacity-[0.03]"
        style="background-image: radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0); background-size: 24px 24px;"
      />
      <div class="relative z-10 flex flex-col items-center text-center">
        <img
          v-if="platformLogo"
          :src="platformLogo"
          :alt="platformName"
          class="mb-5 size-20 rounded-2xl object-contain shadow-lg transition-transform duration-300 hover:scale-105 sm:size-24"
        />
        <h1 class="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          {{ platformName }}
        </h1>
        <p class="mt-4 max-w-xl text-base text-muted-foreground sm:text-lg">
          {{ platformDescription || $t('user.home.heroDesc') }}
        </p>
        <p class="mt-3 max-w-lg text-sm leading-relaxed text-muted-foreground/90">
          {{ $t('user.home.heroDescExtended') }}
        </p>
      </div>
      <!-- 渐变装饰圆 -->
      <div class="absolute -right-16 -top-16 size-56 animate-pulse rounded-full bg-gradient-to-br from-primary/20 to-primary/5 opacity-80" />
      <div class="absolute -bottom-10 -left-10 size-40 animate-pulse rounded-full bg-gradient-to-tr from-primary/15 to-primary/4 opacity-80" style="animation-delay: 500ms; animation-duration: 3s;" />
      <div class="absolute right-1/3 top-1/4 size-20 rounded-full bg-primary/5" />
      <div class="absolute bottom-1/4 left-1/3 size-16 rounded-full bg-primary/4" />
    </div>

    <!-- Features: 前 3 大卡片 + 后 3 紧凑行 -->
    <div class="space-y-8">
      <h2 class="text-lg font-semibold text-foreground">
        {{ $t('user.home.features') }}
      </h2>

      <!-- Primary: 3 large cards — 渐变 + 动效 -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div
          v-for="feature in featuresPrimary"
          :key="feature.label"
          class="group relative overflow-hidden rounded-xl border border-border bg-gradient-to-br from-card to-card/80 p-6 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-lg hover:shadow-primary/5"
        >
          <div
            class="absolute -right-6 -top-6 size-24 rounded-full bg-gradient-to-br from-primary/10 to-transparent opacity-60 transition-opacity group-hover:opacity-100"
          />
          <div
            class="relative mb-4 flex size-12 items-center justify-center rounded-xl bg-gradient-to-br from-primary/10 to-primary/5 transition-transform duration-300 group-hover:scale-110"
          >
            <IconifyIcon :icon="feature.icon" class="size-6" :class="feature.color" />
          </div>
          <h3 class="relative text-base font-semibold text-foreground">{{ feature.label }}</h3>
          <p class="relative mt-2 text-sm leading-relaxed text-muted-foreground">
            {{ feature.desc }}
          </p>
        </div>
      </div>

      <!-- Secondary: 3 compact rows — 左侧渐变条 + hover -->
      <div class="space-y-2">
        <div
          v-for="feature in featuresSecondary"
          :key="feature.label"
          class="group relative flex items-center gap-4 rounded-lg border border-border bg-gradient-to-r from-card/80 to-card px-4 py-3 transition-all duration-200 hover:border-primary/20 hover:shadow-md"
        >
          <div
            class="absolute left-0 top-0 h-full w-1 rounded-l-lg bg-gradient-to-b from-primary/20 to-primary/5 opacity-0 transition-opacity group-hover:opacity-100"
          />
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent transition-colors duration-200 group-hover:bg-primary/10"
          >
            <IconifyIcon :icon="feature.icon" class="size-5" :class="feature.color" />
          </div>
          <div class="min-w-0 flex-1">
            <span class="font-medium text-foreground">{{ feature.label }}</span>
            <span class="text-muted-foreground"> — {{ feature.desc }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 版权由 user.vue layout 统一提供，此处不再重复 -->
  </div>
</template>
