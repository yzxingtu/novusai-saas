<script lang="ts" setup>
import type { MenuRecordRaw } from '@vben/types';

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { VbenAvatar } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { LanguageToggle, ThemeToggle } from '@vben/layouts';
import { preferences } from '@vben/preferences';
import { useAccessStore, useUserStore } from '@vben/stores';

import { Drawer, Dropdown, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';
import { useMultiAuthStore, usePresenceStore, usePublicConfigStore, useSocketIOStore } from '#/store';

defineOptions({ name: 'UserLayout' });

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();
const accessStore = useAccessStore();
const multiAuthStore = useMultiAuthStore();
const publicConfigStore = usePublicConfigStore();
const socketIOStore = useSocketIOStore();
const presenceStore = usePresenceStore();

// 域名感知品牌
const isTenantDomain = computed(() => publicConfigStore.isDomainTenantDomain);

const brandLogo = computed(() => {
  if (isTenantDomain.value) {
    return publicConfigStore.tenantBrand?.logo || preferences.logo.source;
  }
  return preferences.logo.source;
});

const brandName = computed(() => {
  if (isTenantDomain.value) {
    return publicConfigStore.tenantBrand?.siteName || preferences.app.name;
  }
  return preferences.app.name;
});

const mobileMenuOpen = ref(false);

const avatar = computed(() => {
  return userStore.userInfo?.avatar ?? preferences.app.defaultAvatar;
});

const displayName = computed(() => {
  return userStore.userInfo?.realName || userStore.userInfo?.username || '';
});

const navMenus = computed(() => {
  return accessStore.accessMenus;
});

function isMenuActive(menu: MenuRecordRaw): boolean {
  if (!menu.path) return false;
  return route.path === menu.path || route.path.startsWith(`${menu.path}/`);
}

function handleMenuClick(menu: MenuRecordRaw) {
  if (menu.path && menu.path !== route.path) {
    router.push(menu.path);
  }
  mobileMenuOpen.value = false;
}

async function handleLogout() {
  await multiAuthStore.logout(true);
}

function goToProfile() {
  router.push('/profile');
}

const userDropdownItems = computed(() => [
  {
    key: 'profile',
    label: $t('page.auth.profile'),
    icon: 'lucide:user',
  },
  {
    key: 'divider',
    type: 'divider',
  },
  {
    key: 'logout',
    label: $t('authentication.logoutTip'),
    icon: 'lucide:log-out',
    danger: true,
  },
]);

function handleDropdownClick({ key }: { key: string }) {
  if (key === 'profile') {
    goToProfile();
  } else if (key === 'logout') {
    handleLogout();
  }
}

const isLoggedIn = computed(() => !!userStore.userInfo?.username);

const year = computed(() => new Date().getFullYear());

watch(
  () => route.path,
  () => {
    mobileMenuOpen.value = false;
  },
);

onMounted(() => {
  if (userStore.userInfo?.username) {
    socketIOStore.connect('user');
    presenceStore.initSocketHandlers();
  }
});

onBeforeUnmount(() => {
  // Socket.IO disconnect handled by logout flow
});
</script>

<template>
  <div class="flex min-h-screen flex-col bg-background">
    <!-- Top Navigation Bar -->
    <header
      class="sticky top-0 z-50 flex h-14 w-full items-center border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60 lg:px-6"
    >
      <!-- Logo + Brand -->
      <div class="flex shrink-0 items-center gap-2">
        <img
          v-if="brandLogo"
          :src="brandLogo"
          :alt="brandName"
          class="size-7"
        />
        <span class="hidden text-base font-semibold text-foreground sm:inline-block">
          {{ brandName }}
        </span>
      </div>

      <!-- Desktop Nav Links -->
      <nav class="ml-8 hidden items-center gap-1 md:flex">
        <template v-for="menu in navMenus" :key="menu.path">
          <button
            class="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors"
            :class="[
              isMenuActive(menu)
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            ]"
            @click="handleMenuClick(menu)"
          >
            <IconifyIcon
              v-if="menu.icon && typeof menu.icon === 'string'"
              :icon="(menu.icon as string)"
              class="size-4"
            />
            <span>{{ menu.name }}</span>
          </button>
        </template>
      </nav>

      <!-- Right Section -->
      <div class="ml-auto flex items-center gap-1">
        <!-- Theme Toggle -->
        <Tooltip :title="$t('ui.widgets.themeToggle')" placement="bottom">
          <ThemeToggle class="mt-[2px]" />
        </Tooltip>

        <!-- Language Toggle -->
        <Tooltip :title="$t('ui.widgets.languageToggle')" placement="bottom">
          <LanguageToggle />
        </Tooltip>

        <!-- User Dropdown (logged in) -->
        <Dropdown
          v-if="isLoggedIn"
          :trigger="['click']"
          placement="bottomRight"
        >
          <button
            class="ml-1 flex items-center gap-2 rounded-md px-2 py-1 transition-colors hover:bg-accent"
          >
            <VbenAvatar
              :src="avatar"
              :alt="displayName"
              class="size-7"
              dot
            />
            <span class="hidden text-sm font-medium text-foreground sm:inline-block">
              {{ displayName }}
            </span>
            <IconifyIcon
              icon="lucide:chevron-down"
              class="size-3.5 text-muted-foreground"
            />
          </button>
          <template #overlay>
            <div class="min-w-[180px] rounded-md border border-border bg-background p-1 shadow-lg">
              <div class="px-3 py-2">
                <p class="text-sm font-medium text-foreground">
                  {{ displayName }}
                </p>
                <p class="text-xs text-muted-foreground">
                  {{ userStore.userInfo?.username || '' }}
                </p>
              </div>
              <div class="my-1 h-px bg-border" />
              <template v-for="item in userDropdownItems" :key="item.key">
                <div
                  v-if="item.type === 'divider'"
                  class="my-1 h-px bg-border"
                />
                <button
                  v-else
                  class="flex w-full items-center gap-2 rounded-sm px-3 py-1.5 text-sm transition-colors"
                  :class="[
                    item.danger
                      ? 'text-destructive hover:bg-destructive/10'
                      : 'text-foreground hover:bg-accent',
                  ]"
                  @click="handleDropdownClick({ key: item.key })"
                >
                  <IconifyIcon v-if="item.icon" :icon="item.icon" class="size-4" />
                  <span>{{ item.label }}</span>
                </button>
              </template>
            </div>
          </template>
        </Dropdown>

        <!-- Mobile Hamburger -->
        <button
          class="ml-1 flex items-center justify-center rounded-md p-1.5 transition-colors hover:bg-accent md:hidden"
          @click="mobileMenuOpen = true"
        >
          <IconifyIcon icon="lucide:menu" class="size-5" />
        </button>
      </div>
    </header>

    <!-- Mobile Navigation Drawer -->
    <Drawer
      v-model:open="mobileMenuOpen"
      placement="right"
      :width="280"
      :closable="true"
      class="md:hidden"
    >
      <template #title>
        <div class="flex items-center gap-2">
          <img
            v-if="brandLogo"
            :src="brandLogo"
            :alt="brandName"
            class="size-6"
          />
          <span class="font-semibold">{{ brandName }}</span>
        </div>
      </template>
      <nav class="flex flex-col gap-1">
        <template v-for="menu in navMenus" :key="menu.path">
          <button
            class="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors"
            :class="[
              isMenuActive(menu)
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            ]"
            @click="handleMenuClick(menu)"
          >
            <IconifyIcon
              v-if="menu.icon && typeof menu.icon === 'string'"
              :icon="(menu.icon as string)"
              class="size-4"
            />
            <span>{{ menu.name }}</span>
          </button>
        </template>
      </nav>
    </Drawer>

    <!-- Main Content Area -->
    <main class="flex-1">
      <div class="mx-auto w-full max-w-[1100px] px-4 py-6 lg:px-6">
        <RouterView />
      </div>
    </main>

    <!-- Footer -->
    <footer
      class="flex items-center justify-center border-t border-border px-4 py-4 text-xs text-muted-foreground"
    >
      <span>&copy; {{ year }} {{ brandName }}</span>
    </footer>
  </div>
</template>
