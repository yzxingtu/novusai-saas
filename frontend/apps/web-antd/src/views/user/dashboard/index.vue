<script setup lang="ts">
/**
 * 用户端首页
 */
import type { UserProfileInfo } from '#/api/user/auth';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { VbenAvatar } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';
import { useUserStore } from '@vben/stores';

import { Spin } from 'ant-design-vue';

import { getUserProfileApi } from '#/api/user/auth';
import { $t } from '#/locales';

defineOptions({ name: 'UserDashboard' });

const router = useRouter();
const userStore = useUserStore();

const loading = ref(false);
const profile = ref<UserProfileInfo | null>(null);

const displayName = computed(() => {
  return (
    profile.value?.nickname ||
    profile.value?.username ||
    userStore.userInfo?.realName ||
    ''
  );
});

const avatar = computed(() => {
  return (
    profile.value?.avatar ||
    userStore.userInfo?.avatar ||
    preferences.app.defaultAvatar
  );
});

const formattedLastLogin = computed(() => {
  if (!profile.value?.lastLoginAt) {
    return $t('user.dashboard.neverLoggedIn');
  }
  return new Date(profile.value.lastLoginAt).toLocaleString();
});

const formattedMemberSince = computed(() => {
  if (!profile.value?.createdAt) return '-';
  return new Date(profile.value.createdAt).toLocaleDateString();
});

interface QuickAction {
  color: string;
  desc: string;
  icon: string;
  label: string;
  path: string;
}

const quickActions = computed<QuickAction[]>(() => [
  {
    color: 'text-primary',
    desc: $t('user.dashboard.aiChatDesc'),
    icon: 'lucide:message-square',
    label: $t('user.dashboard.aiChat'),
    path: '/chat',
  },
  {
    color: 'text-success',
    desc: $t('user.dashboard.myProfileDesc'),
    icon: 'lucide:user-circle',
    label: $t('user.dashboard.myProfile'),
    path: '/profile',
  },
  {
    color: 'text-warning',
    desc: $t('user.dashboard.changePasswordDesc'),
    icon: 'lucide:key-round',
    label: $t('user.dashboard.changePassword'),
    path: '/profile/change-password',
  },
]);

function handleActionClick(action: QuickAction) {
  router.push(action.path);
}

async function loadProfile() {
  loading.value = true;
  try {
    profile.value = await getUserProfileApi();
  } catch {
    // fallback to store data
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadProfile();
});
</script>

<template>
  <Spin :spinning="loading">
    <div class="space-y-6">
      <!-- Welcome Hero -->
      <div
        class="relative overflow-hidden rounded-xl border border-border bg-gradient-to-r from-primary/8 via-primary/4 to-transparent p-6 sm:p-8"
      >
        <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
          <VbenAvatar
            :src="avatar"
            :alt="displayName"
            class="size-16 shrink-0 rounded-full ring-2 ring-primary/20 sm:size-20"
          />
          <div class="flex-1">
            <h1 class="text-xl font-bold text-foreground sm:text-2xl">
              {{ $t('user.dashboard.greeting', { name: displayName }) }}
            </h1>
            <p class="mt-1 text-sm text-muted-foreground">
              {{ $t('user.dashboard.greetingDesc') }}
            </p>
          </div>
        </div>
        <!-- Decorative circles -->
        <div
          class="absolute -right-8 -top-8 size-32 rounded-full bg-primary/5"
        />
        <div
          class="absolute -bottom-4 -right-4 size-20 rounded-full bg-primary/3"
        />
      </div>

      <!-- Info Cards Row -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <!-- Last Login -->
        <div
          class="flex items-center gap-3 rounded-lg border border-border bg-card p-4"
        >
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10"
          >
            <IconifyIcon icon="lucide:clock" class="size-5 text-primary" />
          </div>
          <div class="min-w-0">
            <p class="text-xs text-muted-foreground">
              {{ $t('user.dashboard.lastLoginAt') }}
            </p>
            <p class="truncate text-sm font-medium text-foreground">
              {{ formattedLastLogin }}
            </p>
          </div>
        </div>

        <!-- Role -->
        <div
          class="flex items-center gap-3 rounded-lg border border-border bg-card p-4"
        >
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-success/10"
          >
            <IconifyIcon icon="lucide:shield" class="size-5 text-success" />
          </div>
          <div class="min-w-0">
            <p class="text-xs text-muted-foreground">
              {{ $t('user.dashboard.role') }}
            </p>
            <p class="truncate text-sm font-medium text-foreground">
              {{ profile?.roleName || $t('user.dashboard.noRole') }}
            </p>
          </div>
        </div>

        <!-- Member Since -->
        <div
          class="flex items-center gap-3 rounded-lg border border-border bg-card p-4"
        >
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-warning/10"
          >
            <IconifyIcon icon="lucide:calendar" class="size-5 text-warning" />
          </div>
          <div class="min-w-0">
            <p class="text-xs text-muted-foreground">
              {{ $t('user.dashboard.memberSince') }}
            </p>
            <p class="truncate text-sm font-medium text-foreground">
              {{ formattedMemberSince }}
            </p>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div>
        <h2 class="mb-4 text-lg font-semibold text-foreground">
          {{ $t('user.dashboard.quickActions') }}
        </h2>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <button
            v-for="action in quickActions"
            :key="action.path"
            class="group flex items-start gap-4 rounded-lg border border-border bg-card p-5 text-left transition-all hover:border-primary/30 hover:shadow-sm"
            @click="handleActionClick(action)"
          >
            <div
              class="flex size-11 shrink-0 items-center justify-center rounded-lg bg-accent transition-colors group-hover:bg-primary/10"
            >
              <IconifyIcon
                :icon="action.icon"
                class="size-5"
                :class="action.color"
              />
            </div>
            <div>
              <h3
                class="text-sm font-semibold text-foreground group-hover:text-primary"
              >
                {{ action.label }}
              </h3>
              <p class="mt-0.5 text-xs text-muted-foreground">
                {{ action.desc }}
              </p>
            </div>
          </button>
        </div>
      </div>
    </div>
  </Spin>
</template>
