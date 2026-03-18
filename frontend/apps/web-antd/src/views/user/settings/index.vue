<script setup lang="ts">
/**
 * 用户设置页面 - 现代化布局 / User settings page - modern layout
 * 左侧导航 + 右侧内容区（移动端为顶部标签）
 */
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

defineOptions({ name: 'UserSettings' });

const router = useRouter();
const route = useRoute();

interface SettingsNavItem {
  icon: string;
  key: string;
  label: () => string;
  path: string;
}

const navItems = computed<SettingsNavItem[]>(() => [
  {
    key: 'profile',
    label: () => $t('user.profile.title'),
    icon: 'lucide:user',
    path: '/settings/profile',
  },
  {
    key: 'security',
    label: () => $t('user.profile.security'),
    icon: 'lucide:shield',
    path: '/settings/password',
  },
]);

function isActive(item: SettingsNavItem): boolean {
  return route.path === item.path;
}

function navigateTo(item: SettingsNavItem) {
  if (route.path !== item.path) {
    router.push(item.path);
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div>
      <h1 class="text-2xl font-bold tracking-tight text-foreground">
        {{ $t('user.settings.title') }}
      </h1>
      <p class="mt-1 text-sm text-muted-foreground">
        {{ $t('user.settings.description') }}
      </p>
    </div>

    <!-- Layout: Sidebar + Content -->
    <div class="flex flex-col gap-6 md:flex-row">
      <!-- Sidebar Navigation (Desktop) -->
      <nav class="hidden w-56 shrink-0 md:block">
        <ul class="space-y-1">
          <li v-for="item in navItems" :key="item.key">
            <button
              class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150"
              :class="[
                isActive(item)
                  ? 'bg-primary/10 text-primary shadow-sm'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground',
              ]"
              @click="navigateTo(item)"
            >
              <IconifyIcon :icon="item.icon" class="size-4 shrink-0" />
              <span>{{ item.label() }}</span>
            </button>
          </li>
        </ul>
      </nav>

      <!-- Mobile Tab Navigation -->
      <nav class="flex gap-1 overflow-x-auto rounded-lg border border-border bg-card p-1 md:hidden">
        <button
          v-for="item in navItems"
          :key="item.key"
          class="flex shrink-0 items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all duration-150"
          :class="[
            isActive(item)
              ? 'bg-primary/10 text-primary shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          ]"
          @click="navigateTo(item)"
        >
          <IconifyIcon :icon="item.icon" class="size-4" />
          <span>{{ item.label() }}</span>
        </button>
      </nav>

      <!-- Content Area -->
      <div class="min-w-0 flex-1">
        <RouterView />
      </div>
    </div>
  </div>
</template>
