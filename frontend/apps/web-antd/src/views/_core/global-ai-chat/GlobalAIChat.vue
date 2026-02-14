<script lang="ts" setup>
/**
 * Global AI Floating Chat Drawer
 *
 * Uses the shared AIChatPanel component in 'drawer' mode.
 * Automatically detects admin vs tenant context from the current route path.
 */
defineOptions({ name: 'GlobalAIChat' });

import { ref, computed, watch } from 'vue';
import { useRoute } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Button, Drawer, Tooltip } from 'ant-design-vue';

import { AIChatPanel } from '#/components/business/ai-chat-panel';
import { $t } from '#/locales';
import { useGlobalAIChatStore } from '#/store';

const route = useRoute();
const chatStore = useGlobalAIChatStore();

const chatPanelRef = ref<InstanceType<typeof AIChatPanel> | null>(null);

const apiPrefix = computed(() => {
  const path = route.path;
  if (path.startsWith('/admin')) return '/admin';
  if (path.startsWith('/tenant')) return '/tenant';
  return '/tenant';
});

const uploadUrl = computed(() => `${apiPrefix.value}/attachments/upload`);

watch(
  () => chatStore.open,
  (isOpen) => {
    if (isOpen && chatPanelRef.value) {
      chatPanelRef.value.loadAgents();
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
    :width="480"
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
      </div>
    </template>

    <AIChatPanel
      ref="chatPanelRef"
      mode="drawer"
      :api-prefix="apiPrefix"
      :upload-url="uploadUrl"
      :show-attachments="true"
    />
  </Drawer>
</template>
