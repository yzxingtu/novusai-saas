<script lang="ts" setup>
/**
 * Global AI Floating Chat Drawer
 *
 * Uses the shared AIChatPanel component in 'drawer' mode.
 * Automatically detects admin vs tenant context from the current route path.
 */
defineOptions({ name: 'GlobalAIChat' });

import { ref, computed, watch, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Button, Drawer, Tooltip } from 'ant-design-vue';

import { getAdminSelectableKBApi } from '#/api/admin/knowledge-bases';
import { getTenantSelectableKBApi } from '#/api/tenant/knowledge-bases';
import { AIChatPanel } from '#/components/business/ai-chat-panel';
import { $t } from '#/locales';
import { useGlobalAIChatStore, useNotificationStore } from '#/store';

const route = useRoute();
const router = useRouter();
const chatStore = useGlobalAIChatStore();
const notificationStore = useNotificationStore();

function handleStreamComplete() {
  chatStore.markUnread();
  if (!chatStore.open) {
    notificationStore.addLocalNotification({
      category: 'ai',
      title: $t('common.notification.aiChatReply'),
      body: null,
      data: null,
      link: null,
      priority: 'normal',
    });
  }
}

const chatPanelRef = ref<InstanceType<typeof AIChatPanel> | null>(null);

const apiPrefix = computed(() => {
  const path = route.path;
  if (path.startsWith('/admin')) return '/admin';
  if (path.startsWith('/tenant')) return '/tenant';
  return '/tenant';
});

const uploadUrl = computed(() => `${apiPrefix.value}/attachments/upload`);

const fetchKBApi = computed(() =>
  apiPrefix.value === '/admin' ? getAdminSelectableKBApi : getTenantSelectableKBApi,
);

// ============ Fullscreen switch ============

function openFullPage() {
  const chatPath = apiPrefix.value === '/admin' ? '/admin/ai/chat' : '/tenant/ai/chat';
  chatStore.hide();
  router.push(chatPath);
}

// ============ Resizable width ============

const STORAGE_KEY = 'ai-chat-drawer-width';
const MIN_WIDTH = 420;
const MAX_WIDTH = 800;
const DEFAULT_WIDTH = 480;

const drawerWidth = ref(DEFAULT_WIDTH);
const dragging = ref(false);

function loadSavedWidth() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const w = Number.parseInt(saved, 10);
      if (w >= MIN_WIDTH && w <= MAX_WIDTH) drawerWidth.value = w;
    }
  } catch { /* ignore */ }
}

function saveWidth() {
  try {
    localStorage.setItem(STORAGE_KEY, String(drawerWidth.value));
  } catch { /* ignore */ }
}

function onDragStart(e: MouseEvent) {
  e.preventDefault();
  dragging.value = true;
  const startX = e.clientX;
  const startWidth = drawerWidth.value;

  function onMouseMove(ev: MouseEvent) {
    const diff = startX - ev.clientX;
    drawerWidth.value = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth + diff));
  }

  function onMouseUp() {
    dragging.value = false;
    saveWidth();
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

onMounted(loadSavedWidth);

watch(
  () => chatStore.open,
  async (isOpen) => {
    if (isOpen && chatPanelRef.value) {
      const agentId = chatStore.consumePendingAgentId();
      await chatPanelRef.value.loadAgents(agentId);
      chatPanelRef.value.loadConversations();
    }
  },
);
</script>

<template>
  <Drawer
    v-model:open="chatStore.open"
    :title="$t('common.globalAiChat.title')"
    placement="right"
    :width="drawerWidth"
    :body-style="{
      padding: 0,
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      overflow: 'hidden',
    }"
    :header-style="{ padding: '12px 16px' }"
    :destroy-on-close="false"
  >
    <template #extra>
      <div class="flex items-center gap-1">
        <Tooltip :title="$t('common.globalAiChat.history')">
          <Button
            size="small"
            type="text"
            @click="chatPanelRef?.toggleHistory()"
          >
            <template #icon>
              <IconifyIcon icon="lucide:history" class="size-3.5" />
            </template>
          </Button>
        </Tooltip>
        <Tooltip :title="$t('common.globalAiChat.newChat')">
          <Button
            size="small"
            type="text"
            @click="chatPanelRef?.onStartNewChat()"
          >
            <template #icon>
              <IconifyIcon icon="lucide:plus" class="size-3.5" />
            </template>
          </Button>
        </Tooltip>
        <Tooltip :title="$t('common.globalAiChat.openFullPage')">
          <Button
            size="small"
            type="text"
            @click="openFullPage"
          >
            <template #icon>
              <IconifyIcon icon="lucide:maximize-2" class="size-3.5" />
            </template>
          </Button>
        </Tooltip>
        <Tooltip :title="$t('common.globalAiChat.minimize')">
          <Button
            size="small"
            type="text"
            @click="chatStore.minimize()"
          >
            <template #icon>
              <IconifyIcon icon="lucide:minus" class="size-3.5" />
            </template>
          </Button>
        </Tooltip>
      </div>
    </template>

    <!-- Drag handle (left edge) -->
    <div
      class="absolute left-0 top-0 z-10 h-full w-1 cursor-col-resize transition-colors hover:bg-primary/30"
      :class="dragging ? 'bg-primary/40' : ''"
      @mousedown="onDragStart"
    />

    <AIChatPanel
      ref="chatPanelRef"
      mode="drawer"
      :api-prefix="apiPrefix"
      :upload-url="uploadUrl"
      :show-attachments="true"
      :show-kb-selector="true"
      :fetch-kb-api="fetchKBApi"
      :on-tool-call="(name: string, output: string) => chatStore.dispatchToolCall(name, output)"
      :on-stream-complete="handleStreamComplete"
    />
  </Drawer>

  <!-- Floating bubble (minimized state) -->
  <Transition name="bubble">
    <div
      v-if="chatStore.minimized && !chatStore.open"
      class="fixed bottom-6 right-6 z-[999] flex cursor-pointer items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-primary-foreground shadow-lg transition-all hover:shadow-xl hover:brightness-110"
      @click="chatStore.restore()"
    >
      <IconifyIcon icon="lucide:bot" class="size-5" />
      <span class="text-sm font-medium">{{ $t('common.globalAiChat.title') }}</span>
      <span
        v-if="chatStore.hasUnread"
        class="size-2 rounded-full bg-destructive"
      />
      <IconifyIcon
        icon="lucide:x"
        class="ml-1 size-3.5 opacity-60 hover:opacity-100"
        @click.stop="chatStore.hide()"
      />
    </div>
  </Transition>
</template>

<style scoped>
.bubble-enter-active {
  animation: bubble-in 0.3s ease-out;
}
.bubble-leave-active {
  animation: bubble-in 0.2s ease-in reverse;
}
@keyframes bubble-in {
  0% {
    opacity: 0;
    transform: scale(0.6) translateY(20px);
  }
  100% {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
