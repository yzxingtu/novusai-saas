<script lang="ts" setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import {
  AuthenticationLoginExpiredModal,
  VbenFullScreen,
} from '@vben/common-ui';
import { useRefresh, useWatermark } from '@vben/hooks';
import { IconifyIcon } from '@vben/icons';
import {
  BasicLayout,
  LanguageToggle,
  LockScreen,
  PreferencesButton,
  ThemeToggle,
  UserDropdown,
} from '@vben/layouts';
import { preferences, updatePreferences } from '@vben/preferences';
import { useAccessStore, useTabbarStore, useUserStore } from '@vben/stores';

import { message, Popover, Tooltip } from 'ant-design-vue';

import { ensureGlobalUIRuntime } from '#/components/business/ai-runtime/runtime-bridge';
import { AIChatSlidePanel } from '#/components/business/ai-slide-panel';
import AnnouncementGlobalModal from '#/components/business/announcement/AnnouncementGlobalModal.vue';
import CacheClearModal from '#/components/business/cache-clear-modal/CacheClearModal.vue';
import { CommandBar } from '#/components/business/command-bar';
import NotificationPanel from '#/components/business/notification-panel/NotificationPanel.vue';
import NotificationToast from '#/components/business/notification-toast/NotificationToast.vue';
import PluginFloatingPanels from '#/components/business/plugin-slots/PluginFloatingPanels.vue';
import ReLoginForm from '#/components/business/re-login-form/ReLoginForm.vue';
import { useCurrentPageAIPolicy } from '#/composables';
import { usePageSession } from '#/composables/use-page-session';
import {
  refreshPluginSlots,
  resetPluginRoutesReady,
  usePluginFrontendInit,
} from '#/composables/use-plugin-frontend-init';
import { usePreferenceSync } from '#/composables/use-preference-sync';
import { useUIActionChannel } from '#/composables/use-ui-action-channel';
import { $t, $te } from '#/locales';
import { generateAccess } from '#/router/access';
import { accessRoutes } from '#/router/routes';
import {
  useAIPanelStore,
  useAnnouncementStore,
  useMultiAuthStore,
  useNotificationStore,
  usePresenceStore,
  useSocketIOStore,
} from '#/store';
import { useUserPreferenceStore } from '#/store/shared';
import { usePluginSlotsStore } from '#/stores/plugin-slots';
import { getEndpointFromPath } from '#/utils';

import { syncLocaleNavigation } from './locale-navigation-sync';

const router = useRouter();
const userStore = useUserStore();
const multiAuthStore = useMultiAuthStore();
const aiPanelStore = useAIPanelStore();
const announcementStore = useAnnouncementStore();
const socketIOStore = useSocketIOStore();
const notificationStore = useNotificationStore();
const presenceStore = usePresenceStore();
const accessStore = useAccessStore();
const tabbarStore = useTabbarStore();
const pluginSlotsStore = usePluginSlotsStore();
const preferenceStore = useUserPreferenceStore();
const { destroyWatermark, updateWatermark } = useWatermark();
const { refresh } = useRefresh();
const cacheClearModalRef = ref<InstanceType<typeof CacheClearModal>>();
let localeSyncTask: null | Promise<void> = null;
let localeSyncQueued = false;
let lastSyncedLocale = String(preferences.app.locale || '');

// ============ Preference Sync / 偏好同步 ============
const { initSnapshot, skipSync } = usePreferenceSync();

// ============ AI Panel / AI 面板 ============

usePageSession();
ensureGlobalUIRuntime({
  getRoute: () => {
    const currentRoute = router.currentRoute.value;
    return {
      fullPath: currentRoute.fullPath,
      meta:
        currentRoute.meta && typeof currentRoute.meta === 'object'
          ? (currentRoute.meta as Record<string, unknown> & { title?: string })
          : undefined,
      name:
        currentRoute.name === undefined || currentRoute.name === null
          ? undefined
          : String(currentRoute.name),
    };
  },
});
useUIActionChannel();
const {
  aiEnabled,
  disabledCapabilities,
  disabledOperations,
  effectiveMode,
  pageContextKey,
} = useCurrentPageAIPolicy();
// Keep a single policy chain:
// route.meta.ai -> useCurrentPageAIPolicy -> basic.vue -> AIChatSlidePanel -> usePageAICapability.
// Do not introduce an alternate page-policy path inside panel shells.

const apiPrefix = computed(() => {
  const path = router.currentRoute.value.path;
  if (path.startsWith('/admin')) return '/admin';
  if (path.startsWith('/tenant')) return '/tenant';
  return '/tenant';
});

// ============ Endpoint Indicator / 当前端点标识 ============

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

/** AI Panel 固定时的右侧偏移量（页面禁用 AI 时归零） / AI Panel right offset */
const aiPanelRightOffset = computed(() => {
  if (!aiEnabled.value || !aiPanelStore.visible || !aiPanelStore.docked) {
    return 0;
  }
  return aiPanelStore.panelWidth;
});

/** CommandBar / plugin bridge queued message / CommandBar / 插件桥接排队消息 */
const pendingMessage = computed(() => aiPanelStore.pendingMessage);

/** CommandBar / plugin bridge queued conversation restore / CommandBar / 插件桥接排队恢复对话 */
const pendingConversationId = computed(
  () => aiPanelStore.pendingConversationId,
);

function onCommandBarSubmit(text: string) {
  aiPanelStore.queueMessage(text);
  aiPanelStore.open();
}

function onCommandBarSelectConversation(convId: number) {
  aiPanelStore.queueConversationRestore(convId);
  aiPanelStore.open();
}

function onMessageSent() {
  aiPanelStore.consumePendingMessage();
}

function onConversationRestored() {
  aiPanelStore.consumePendingConversationId();
}

/** CommandBar 组件引用 / CommandBar component ref */
const commandBarRef = ref<InstanceType<typeof CommandBar> | null>(null);

// 初始化插件前端（动态加载已启用插件的 UMD 包并注册到插槽 Store）/ plugin UMD + slots
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
  await refreshPluginSlots(endpoint, router, { reloadAssets: false });
});

/** Socket.IO 断连/重连 UI 提示 / Socket disconnect/reconnect UI hint */
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

watch(
  () => preferences.app.locale,
  (newLocale, oldLocale) => {
    const nextLocale = String(newLocale || '');
    if (!oldLocale || nextLocale === String(oldLocale)) {
      return;
    }
    void syncLocaleDrivenState(nextLocale).catch((error) => {
      console.warn('[BasicLayout] locale sync failed:', error);
    });
  },
);

onMounted(async () => {
  updatePreferences({ copyright: { settingShow: false } });

  socketIOStore.connect();
  // 设置通知端类型后再加载未读数（避免默认 admin 端导致 401）
  const ep = router.currentRoute.value.path.startsWith('/admin')
    ? 'admin'
    : 'tenant';
  notificationStore.setEndpoint(ep);
  notificationStore.loadUnreadCount();
  notificationStore.initSocketHandlers();
  announcementStore.setEndpoint(ep);
  announcementStore.loadPending();
  announcementStore.initSocketHandlers();
  presenceStore.initSocketHandlers();

  // 加载用户偏好并同步到框架 / Load preferences and sync to Vben
  skipSync();
  await preferenceStore.loadPreferences(ep as 'admin' | 'tenant');
  initSnapshot();
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
  {
    handler: async () => {
      const result = await preferenceStore.resetMyPreferences();
      if (result) {
        skipSync();
        initSnapshot();
        message.success($t('common.preference.resetSuccess'));
      }
    },
    icon: 'lucide:rotate-ccw',
    text: $t('common.preference.resetToGlobal'),
  },
]);

async function handleResetPreferences() {
  const result = await preferenceStore.resetMyPreferences();
  if (result) {
    skipSync();
    initSnapshot();
    message.success($t('common.preference.resetSuccess'));
  }
}

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
  await syncLocaleDrivenState(String(preferences.app.locale || ''), {
    showLoading: true,
  });
}

async function syncLocaleDrivenState(
  targetLocale: string,
  options: { showLoading?: boolean } = {},
) {
  if (!targetLocale) {
    return;
  }

  if (localeSyncTask) {
    localeSyncQueued = true;
    await localeSyncTask;
    if (targetLocale === lastSyncedLocale) {
      return;
    }
  }

  if (targetLocale === lastSyncedLocale) {
    return;
  }

  localeSyncTask = (async () => {
    const hideLoading = options.showLoading
      ? message.loading({
          content: $t('common.loadingMenu'),
          duration: 0,
        })
      : () => {};

    try {
      const currentEndpoint = getEndpointFromPath(
        router.currentRoute.value.path,
      );
      const userRoles = userStore.userInfo?.roles ?? [];

      await syncLocaleNavigation({
        accessStore,
        endpoint: currentEndpoint,
        generateAccess,
        hasLocaleKey: $te,
        locale: targetLocale,
        refreshPluginSlots,
        router,
        routes: accessRoutes,
        tabbarStore,
        translate: $t,
        userRoles,
      });
      lastSyncedLocale = targetLocale;
    } finally {
      hideLoading();
    }
  })();

  try {
    await localeSyncTask;
  } finally {
    localeSyncTask = null;
    if (localeSyncQueued) {
      localeSyncQueued = false;
      const latestLocale = String(preferences.app.locale || '');
      if (latestLocale && latestLocale !== lastSyncedLocale) {
        await syncLocaleDrivenState(latestLocale);
      }
    }
  }
}

/**
 * 解析水印模板变量 / Resolve watermark template variables
 */
function resolveWatermarkTemplate(template: string): string {
  const info = userStore.userInfo;
  const tenantName =
    ((info as Record<string, unknown>)?.tenantName as string) ||
    preferences.app.name ||
    '';
  return template
    .replaceAll('{tenant_name}', tenantName)
    .replaceAll('{username}', info?.username || '')
    .replaceAll('{real_name}', info?.realName || '')
    .replaceAll('{user_id}', String(info?.id || ''));
}

watch(
  () => ({
    enable: preferenceStore.getPref('watermark_enable'),
    content: preferenceStore.getPref('watermark_content'),
  }),
  async ({ enable, content }) => {
    if (enable) {
      const resolved = resolveWatermarkTemplate(
        (content as string) || '{tenant_name} - {real_name}',
      );
      await updateWatermark({ content: resolved });
    } else {
      destroyWatermark();
    }
  },
  { immediate: true },
);
</script>

<template>
  <BasicLayout
    :panel-right-offset="aiPanelRightOffset"
    @clear-preferences-and-logout="() => cacheClearModalRef?.open()"
    @locale-change="handleLocaleChange"
    @reset-preferences="handleResetPreferences"
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
      <Tooltip :title="$t('ui.widgets.notifications')" placement="bottom">
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
        class="group relative mr-1 flex h-8 cursor-pointer items-center gap-2 rounded-full border px-3 py-0.5 shadow-sm transition-colors sm:mr-4"
        :class="
          aiPanelStore.hasUnread
            ? 'border-primary/18 bg-primary/[0.07] shadow-[0_14px_28px_-30px_hsl(var(--primary)/0.45)] hover:bg-primary/[0.09]'
            : 'border-border/16 bg-background/88 hover:border-border/28 hover:bg-accent/72'
        "
        @click="commandBarRef?.show()"
      >
        <IconifyIcon
          icon="lucide:sparkles"
          class="size-4 transition-colors"
          :class="
            aiPanelStore.hasUnread
              ? 'text-primary'
              : 'text-muted-foreground group-hover:text-foreground'
          "
        />
        <span
          class="hidden text-[11px] font-medium transition-colors md:block"
          :class="
            aiPanelStore.hasUnread
              ? 'text-foreground'
              : 'text-muted-foreground group-hover:text-foreground'
          "
        >
          {{ $t('common.aiPanel.title') }}
        </span>
        <kbd
          class="border-foreground/12 bg-background/92 hidden rounded-full border px-1.5 py-0.5 text-[10px] leading-none text-muted-foreground md:block"
        >
          Ctrl K
        </kbd>
      </div>
    </template>
    <template #extra>
      <AuthenticationLoginExpiredModal
        v-model:open="accessStore.loginExpired"
        :avatar
      >
        <ReLoginForm />
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
        :ai-mode="effectiveMode"
        :disabled-capabilities="disabledCapabilities"
        :disabled-operations="disabledOperations"
        :upload-url="uploadUrl"
        :pending-message="pendingMessage"
        :pending-conversation-id="pendingConversationId"
        :page-context-key="pageContextKey"
        @message-sent="onMessageSent"
        @conversation-restored="onConversationRestored"
      />
      <CacheClearModal ref="cacheClearModalRef" />
      <AnnouncementGlobalModal />
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
/* 隐藏 UserDropdown trigger 中 VbenAvatar 自带的绿点，改用连接状态点 / Hide VbenAvatar green dot, use connection status dot */
.user-dropdown-wrapper :deep(.size-8 > span.absolute) {
  display: none;
}
</style>
