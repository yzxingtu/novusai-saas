<script lang="ts" setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { AuthenticationLoginExpiredModal, VbenFullScreen } from '@vben/common-ui';
import { useRefresh, useWatermark } from '@vben/hooks';
import { IconifyIcon } from '@vben/icons';
import {
  BasicLayout,
  LanguageToggle,
  LockScreen,
  PreferencesButton,
  ThemeToggle,
  TimezoneButton,
  UserDropdown,
} from '@vben/layouts';
import { preferences } from '@vben/preferences';
import { useAccessStore, useTabbarStore, useUserStore } from '@vben/stores';

import { message, Popover, Tooltip } from 'ant-design-vue';

import { getApiEndpoint } from '#/api';
import { AIChatSlidePanel } from '#/components/business/ai-slide-panel';
import CacheClearModal from '#/components/business/cache-clear-modal/CacheClearModal.vue';
import { CommandBar } from '#/components/business/command-bar';
import NotificationPanel from '#/components/business/notification-panel/NotificationPanel.vue';
import NotificationToast from '#/components/business/notification-toast/NotificationToast.vue';
import PluginFloatingPanels from '#/components/business/plugin-slots/PluginFloatingPanels.vue';
import { useCurrentPageAIPolicy } from '#/composables';
import { usePageOperationChannel } from '#/composables/use-page-operation-channel';
import { usePageSession } from '#/composables/use-page-session';
import {
  refreshPluginSlots,
  resetPluginRoutesReady,
  usePluginFrontendInit,
} from '#/composables/use-plugin-frontend-init';
import { $t } from '#/locales';
import { generateAccess } from '#/router/access';
import { accessRoutes } from '#/router/routes';
import {
  useAIPanelStore,
  useMultiAuthStore,
  useNotificationStore,
  usePresenceStore,
  useSocketIOStore,
} from '#/store';
import { usePluginSlotsStore } from '#/stores/plugin-slots';
import LoginForm from '#/views/user/authentication/login.vue';

const router = useRouter();
const userStore = useUserStore();
const multiAuthStore = useMultiAuthStore();
const aiPanelStore = useAIPanelStore();
const socketIOStore = useSocketIOStore();
const notificationStore = useNotificationStore();
const presenceStore = usePresenceStore();
const accessStore = useAccessStore();
const tabbarStore = useTabbarStore();
const pluginSlotsStore = usePluginSlotsStore();
const { destroyWatermark, updateWatermark } = useWatermark();
const { refresh } = useRefresh();
const cacheClearModalRef = ref<InstanceType<typeof CacheClearModal>>();

// ============ AI Panel ============

usePageSession();
usePageOperationChannel();
const { aiEnabled, pageContextKey } = useCurrentPageAIPolicy();

const apiPrefix = computed(() => {
  const path = router.currentRoute.value.path;
  if (path.startsWith('/admin')) return '/admin';
  if (path.startsWith('/tenant')) return '/tenant';
  return '/tenant';
});

// ============ Endpoint Indicator ============

const isAdminEndpoint = computed(() => apiPrefix.value === '/admin');

const endpointLabel = computed(() =>
  isAdminEndpoint.value
    ? $t('common.endpoint.admin')
    : $t('common.endpoint.tenant'),
);

const endpointIcon = computed(() =>
  isAdminEndpoint.value ? 'lucide:shield-check' : 'lucide:building-2',
);

const uploadUrl = computed(() => `${apiPrefix.value}/attachments/upload`);

/** AI Panel 固定时的右侧偏移量（页面禁用 AI 时归零） */
const aiPanelRightOffset = computed(() => {
  if (!aiEnabled.value || !aiPanelStore.visible || aiPanelStore.mode === 'full' || !aiPanelStore.docked) {
    return 0;
  }
  return aiPanelStore.panelWidth;
});

/** CommandBar 发送的待处理消息 */
const pendingMessage = ref<null | string>(null);

/** CommandBar 选择的待恢复对话 ID */
const pendingConversationId = ref<null | number>(null);

function onCommandBarSubmit(text: string) {
  pendingMessage.value = text;
  aiPanelStore.open();
}

function onCommandBarSelectConversation(convId: number) {
  pendingConversationId.value = convId;
}

function onMessageSent() {
  pendingMessage.value = null;
}

function onConversationRestored() {
  pendingConversationId.value = null;
}

/** CommandBar 组件引用 */
const commandBarRef = ref<InstanceType<typeof CommandBar> | null>(null);

// 初始化插件前端（动态加载已启用插件的 UMD 包并注册到插槽 Store）
const currentEndpointPrefix = computed(() => {
  const path = router.currentRoute.value.path;
  return path.startsWith('/tenant') ? '/tenant' : '/admin';
});

usePluginFrontendInit(currentEndpointPrefix.value);

watch(currentEndpointPrefix, async (endpoint, previousEndpoint) => {
  if (!previousEndpoint || endpoint === previousEndpoint) {
    return;
  }
  resetPluginRoutesReady(router);
  await refreshPluginSlots(endpoint, router);
});

/** Socket.IO 断连/重连 UI 提示 */
let disconnectMsgKey: string | undefined;
function clearDisconnectToast() {
  if (disconnectMsgKey) {
    message.destroy(disconnectMsgKey);
    disconnectMsgKey = undefined;
  }
}
watch(
  () => socketIOStore.status,
  (newStatus, oldStatus) => {
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
  },
);

onMounted(() => {
  // Socket.IO: 登录后自动连接
  socketIOStore.connect();
  // 设置通知端类型后再加载未读数（避免默认 admin 端导致 401）
  const ep = router.currentRoute.value.path.startsWith('/admin')
    ? 'admin'
    : 'tenant';
  notificationStore.setEndpoint(ep);
  notificationStore.loadUnreadCount();
  notificationStore.initSocketHandlers();
  presenceStore.initSocketHandlers();
});

onBeforeUnmount(() => {
  clearDisconnectToast();
});

const menus = computed(() => [
  {
    handler: () => {
      const isTenant = router.currentRoute.value.path.startsWith('/tenant');
      router.push({ name: isTenant ? 'TenantProfile' : 'AdminProfile' });
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
    :panel-right-offset="aiPanelRightOffset"
    @clear-preferences-and-logout="() => cacheClearModalRef?.open()"
    @locale-change="handleLocaleChange"
  >
    <template #sidebar-bottom>
      <div
        v-if="!preferences.sidebar.collapsed"
        class="flex items-center justify-center border-t border-border px-2 py-2"
      >
        <span
          class="inline-flex items-center gap-1 rounded-sm bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary"
        >
          <IconifyIcon :icon="endpointIcon" class="size-3" />
          {{ endpointLabel }}
        </span>
      </div>
    </template>
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
            :description="
              userStore.userInfo?.email || userStore.userInfo?.username
            "
            :tag-text="userStore.userInfo?.roles?.[0] || ''"
            @logout="handleLogout"
          />
          <span
            class="pointer-events-none absolute bottom-1 right-2.5 z-10 block size-2.5 rounded-full border-2 border-background"
            :class="[
              socketIOStore.isConnected
                ? 'bg-green-500'
                : socketIOStore.status === 'reconnecting'
                  ? 'animate-pulse bg-yellow-500'
                  : 'bg-gray-400',
            ]"
          ></span>
        </div>
      </Tooltip>
    </template>
    <template #notification>
      <Tooltip
        :title="$t('ui.widgets.notifications')"
        placement="bottom"
      >
        <Popover
          trigger="click"
          placement="bottomRight"
          :arrow="false"
          overlay-class-name="notification-popover"
        >
          <template #content>
            <NotificationPanel />
          </template>
          <div
            class="relative flex cursor-pointer items-center justify-center rounded-md p-1.5 transition-colors hover:bg-accent"
          >
            <IconifyIcon icon="lucide:bell" class="size-4" />
            <span
              v-if="notificationStore.unreadCount > 0"
              class="absolute -right-0.5 -top-0.5 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] text-white"
            >
              {{
                notificationStore.unreadCount > 99
                  ? '99+'
                  : notificationStore.unreadCount
              }}
            </span>
          </div>
        </Popover>
      </Tooltip>
    </template>
    <template #refresh>
      <Tooltip :title="$t('ui.widgets.refresh')" placement="bottom">
        <div
          class="my-0 mr-1 flex cursor-pointer items-center justify-center rounded-md p-1.5 transition-colors hover:bg-accent"
          @click="refresh"
        >
          <IconifyIcon icon="lucide:rotate-cw" class="size-4" />
        </div>
      </Tooltip>
    </template>
    <template #theme-toggle>
      <Tooltip :title="$t('ui.widgets.themeToggle')" placement="bottom">
        <ThemeToggle class="mr-1 mt-[2px]" />
      </Tooltip>
    </template>
    <template #language-toggle>
      <Tooltip :title="$t('ui.widgets.languageToggle')" placement="bottom">
        <LanguageToggle class="mr-1" />
      </Tooltip>
    </template>
    <template #fullscreen>
      <Tooltip :title="$t('ui.widgets.fullscreen')" placement="bottom">
        <VbenFullScreen class="mr-1" />
      </Tooltip>
    </template>
    <template #timezone>
      <Tooltip
        :title="$t('ui.widgets.timezone.setTimezone')"
        placement="bottom"
      >
        <TimezoneButton class="mr-1 mt-[2px]" />
      </Tooltip>
    </template>
    <template #preferences>
      <Tooltip :title="$t('ui.widgets.setting')" placement="bottom">
        <PreferencesButton
          class="mr-1"
          @clear-preferences-and-logout="() => cacheClearModalRef?.open()"
        />
      </Tooltip>
    </template>
    <!-- 插件 headerWidgets 动态注入（sort_order 映射到 header-right-{n} 槽位） -->
    <template #header-right-89>
      <template
        v-for="widget in pluginSlotsStore.headerWidgets"
        :key="`${widget.pluginName}-${widget.name}`"
      >
        <component :is="widget.component" />
      </template>
    </template>
    <template #global-search>
      <!-- Replaced by unified CommandBar (AI + search) / 由统一的 CommandBar（AI + 搜索）替代 -->
    </template>
    <template #header-right-51>
      <div
        v-if="aiEnabled"
        class="group relative mr-1 flex h-8 cursor-pointer items-center gap-2 rounded-2xl bg-accent/50 px-3 py-0.5 transition-colors hover:bg-accent sm:mr-4"
        @click="commandBarRef?.show()"
      >
        <IconifyIcon
          icon="lucide:sparkles"
          class="size-4 text-muted-foreground transition-colors group-hover:text-foreground"
        />
        <span
          class="hidden text-xs text-muted-foreground transition-colors group-hover:text-foreground md:block"
        >
          {{ $t('common.aiPanel.title') }}
        </span>
        <kbd
          class="hidden rounded-sm border border-foreground/15 bg-background px-1.5 py-0.5 text-[10px] leading-none text-muted-foreground md:block"
        >
          Ctrl K
        </kbd>
        <span
          v-if="aiPanelStore.hasUnread"
          class="absolute -right-0.5 -top-0.5 size-2 rounded-full bg-destructive"
        ></span>
      </div>
    </template>
    <template #extra>
      <AuthenticationLoginExpiredModal
        v-model:open="accessStore.loginExpired"
        :avatar
      >
        <LoginForm />
      </AuthenticationLoginExpiredModal>
      <CommandBar
        v-if="aiEnabled"
        ref="commandBarRef"
        :api-prefix="apiPrefix"
        :can-chat="aiEnabled"
        :menus="accessStore.accessMenus"
        @submit="onCommandBarSubmit"
        @select-conversation="onCommandBarSelectConversation"
      />
      <AIChatSlidePanel
        v-if="aiEnabled"
        :api-prefix="apiPrefix"
        :upload-url="uploadUrl"
        :pending-message="pendingMessage"
        :pending-conversation-id="pendingConversationId"
        :page-context-key="pageContextKey"
        @message-sent="onMessageSent"
        @conversation-restored="onConversationRestored"
      />
      <CacheClearModal ref="cacheClearModalRef" />
      <NotificationToast />
      <!-- 插件 floatingPanels 动态注入（支持 icon/position/弹出控制） -->
      <PluginFloatingPanels />
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
