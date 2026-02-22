<script lang="ts" setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';

import { AuthenticationLoginExpiredModal } from '@vben/common-ui';
import { useWatermark } from '@vben/hooks';
import { IconifyIcon } from '@vben/icons';
import {
  BasicLayout,
  LockScreen,
  UserDropdown,
} from '@vben/layouts';
import { preferences } from '@vben/preferences';
import { useAccessStore, useTabbarStore, useUserStore } from '@vben/stores';

import { Popover, Tooltip } from 'ant-design-vue';
import { message } from 'ant-design-vue';

import { getApiEndpoint } from '#/api';
import { $t } from '#/locales';
import { generateAccess } from '#/router/access';
import { accessRoutes } from '#/router/routes';
import NotificationPanel from '#/components/business/notification-panel/NotificationPanel.vue';
import NotificationToast from '#/components/business/notification-toast/NotificationToast.vue';
import { useGlobalAIChatStore, useMultiAuthStore, useNotificationStore, usePresenceStore, useSocketIOStore } from '#/store';
import LoginForm from '#/views/_core/authentication/login.vue';
import GlobalAIChat from '#/views/_core/global-ai-chat/GlobalAIChat.vue';


const router = useRouter();
const userStore = useUserStore();
const multiAuthStore = useMultiAuthStore();
const globalAIChatStore = useGlobalAIChatStore();
const socketIOStore = useSocketIOStore();
const notificationStore = useNotificationStore();
const presenceStore = usePresenceStore();
const accessStore = useAccessStore();
const tabbarStore = useTabbarStore();
const { destroyWatermark, updateWatermark } = useWatermark();
function handleGlobalKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === '\\') {
    e.preventDefault();
    globalAIChatStore.toggle();
  }
}

/** Socket.IO 断连/重连 UI 提示 */
let disconnectMsgKey: string | undefined;
function clearDisconnectToast() {
  if (disconnectMsgKey) {
    message.destroy(disconnectMsgKey);
    disconnectMsgKey = undefined;
  }
}
watch(() => socketIOStore.status, (newStatus, oldStatus) => {
  if (newStatus === 'disconnected' && oldStatus === 'connected') {
    // 仅在非主动断开（仍有 endpoint，说明用户未登出）时显示警告
    if (socketIOStore.currentEndpoint) {
      disconnectMsgKey = `sio-disconnect-${Date.now()}`;
      message.warning({
        content: $t('shared.common.connectionLost'),
        key: disconnectMsgKey,
        duration: 0,
      });
    }
  } else if (newStatus === 'connected') {
    clearDisconnectToast();
  }
});

onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeydown);
  // Socket.IO: 登录后自动连接
  socketIOStore.connect();
  // 加载未读通知数
  notificationStore.loadUnreadCount();
  notificationStore.initSocketHandlers();
  presenceStore.initSocketHandlers();
});

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleGlobalKeydown);
  clearDisconnectToast();
});

const menus = computed(() => [
  {
    handler: () => {
      const isTenant = router.currentRoute.value.path.startsWith('/tenant');
      router.push({ name: isTenant ? 'TenantProfile' : 'Profile' });
    },
    icon: 'lucide:user',
    text: $t('page.auth.profile'),
  },
]);

const avatar = computed(() => {
  return userStore.userInfo?.avatar ?? preferences.app.defaultAvatar;
});

async function handleLogout() {
  await multiAuthStore.logout(false);
}

/**
 * 语言切换时重新加载菜单
 */
async function handleLocaleChange() {
  // 显示加载提示
  const hideLoading = message.loading({
    content: $t('common.loadingMenu'),
    duration: 0,
  });

  try {
    // 获取当前端类型
    const currentEndpoint = getApiEndpoint(router.currentRoute.value.path);
    const userRoles = userStore.userInfo?.roles ?? [];

    // 重新获取菜单和路由
    const { accessibleMenus, accessibleRoutes } = await generateAccess(
      {
        roles: userRoles,
        router,
        routes: accessRoutes,
      },
      currentEndpoint,
    );

    // 更新菜单和路由
    accessStore.setAccessMenus(accessibleMenus);
    accessStore.setAccessRoutes(accessibleRoutes);

    // 更新所有已打开的 tabs 的 title
    updateAllTabsTitles();
  } finally {
    hideLoading();
  }
}

/**
 * 更新所有已打开 tabs 的 title
 */
function updateAllTabsTitles() {
  const tabs = tabbarStore.getTabs;
  const routes = router.getRoutes();

  // 创建路由路径到 meta.title 的映射
  const routeTitleMap = new Map<string, string>();
  for (const route of routes) {
    if (route.meta?.title) {
      routeTitleMap.set(route.path, route.meta.title as string);
    }
  }

  // 更新每个 tab 的 title
  for (const tab of tabs) {
    const newTitle = routeTitleMap.get(tab.path);
    if (newTitle && tab.meta) {
      tab.meta.title = newTitle;
    }
  }

  // 触发 tabbarStore 更新
  tabbarStore.setUpdateTime();
}

watch(
  () => ({
    enable: preferences.app.watermark,
    content: preferences.app.watermarkContent,
  }),
  async ({ enable, content }) => {
    if (enable) {
      await updateWatermark({
        content:
          content ||
          `${userStore.userInfo?.username} - ${userStore.userInfo?.realName}`,
      });
    } else {
      destroyWatermark();
    }
  },
  {
    immediate: true,
  },
);
</script>

<template>
  <BasicLayout
    @clear-preferences-and-logout="handleLogout"
    @locale-change="handleLocaleChange"
  >
    <template #user-dropdown>
      <Tooltip
        :title="
          socketIOStore.isConnected
            ? $t('common.socketio.connected')
            : socketIOStore.status === 'reconnecting'
              ? $t('common.socketio.reconnecting')
              : $t('common.socketio.disconnected')
        "
        placement="bottom"
        :mouse-enter-delay="0.5"
      >
        <div class="user-dropdown-wrapper relative">
          <UserDropdown
            :avatar
            :menus
            :text="userStore.userInfo?.realName"
            :description="userStore.userInfo?.email || userStore.userInfo?.username"
            :tag-text="userStore.userInfo?.roles?.[0] || ''"
            @logout="handleLogout"
          />
          <span
            class="pointer-events-none absolute bottom-1 right-2.5 z-10 block size-2.5 rounded-full border-2 border-background"
            :class="[
              socketIOStore.isConnected
                ? 'bg-green-500'
                : socketIOStore.status === 'reconnecting'
                  ? 'bg-yellow-500 animate-pulse'
                  : 'bg-gray-400',
            ]"
          />
        </div>
      </Tooltip>
    </template>
    <template #notification>
      <Popover
        trigger="click"
        placement="bottomRight"
        :arrow="false"
        overlay-class-name="notification-popover"
      >
        <template #content>
          <NotificationPanel />
        </template>
        <div class="hover:bg-accent relative flex cursor-pointer items-center justify-center rounded-md p-1.5 transition-colors">
          <IconifyIcon icon="lucide:bell" class="size-4" />
          <span
            v-if="notificationStore.unreadCount > 0"
            class="absolute -right-0.5 -top-0.5 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] text-white"
          >
            {{ notificationStore.unreadCount > 99 ? '99+' : notificationStore.unreadCount }}
          </span>
        </div>
      </Popover>
    </template>
    <template #header-right-51>
      <Tooltip :title="`${$t('common.globalAiChat.title')} (Ctrl+\\)`" placement="bottom">
        <div
          class="hover:bg-accent relative flex cursor-pointer items-center justify-center rounded-md p-1.5 transition-colors"
          @click="globalAIChatStore.toggle()"
        >
          <IconifyIcon icon="lucide:bot" class="size-4" />
          <span
            v-if="globalAIChatStore.hasUnread"
            class="absolute right-0.5 top-0.5 size-2 rounded-full bg-destructive"
          />
        </div>
      </Tooltip>
    </template>
    <template #extra>
      <AuthenticationLoginExpiredModal
        v-model:open="accessStore.loginExpired"
        :avatar
      >
        <LoginForm />
      </AuthenticationLoginExpiredModal>
      <GlobalAIChat />
      <NotificationToast />
    </template>
    <template #lock-screen>
      <LockScreen :avatar @to-login="handleLogout" />
    </template>
  </BasicLayout>
</template>

<style scoped>
/* 隐藏 UserDropdown trigger 中 VbenAvatar 自带的绿点，改用连接状态点 */
.user-dropdown-wrapper :deep(.size-8 > span.absolute) {
  display: none;
}
</style>
