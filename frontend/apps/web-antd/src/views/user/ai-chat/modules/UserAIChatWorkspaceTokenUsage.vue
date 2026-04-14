<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Dropdown, Menu } from 'ant-design-vue';

import { $t } from '#/locales';

import { useUserAIChatWorkspaceContext } from './user-ai-chat-workspace-context';

const {
  page: { chat, exportMenuItems },
} = useUserAIChatWorkspaceContext();
const { totalTokensUsed, streaming, chatMessages } = chat;
</script>

<template>
  <div
    v-if="totalTokensUsed > 0 && !streaming"
    class="flex items-center justify-center gap-1.5 border-t border-border/50 px-4 py-1 text-[11px] text-muted-foreground"
  >
    <IconifyIcon icon="lucide:activity" class="size-3" />
    <span>
      {{ chatMessages.length }}
      {{ $t('common.globalAiChat.messages') }} ·
      {{ totalTokensUsed.toLocaleString() }}
      {{ $t('common.globalAiChat.tokens') }}
    </span>
    <span class="text-border">|</span>
    <Dropdown :trigger="['click']" placement="bottomRight">
      <button class="hover:text-foreground" type="button">
        <IconifyIcon icon="lucide:download" class="size-3" />
      </button>
      <template #overlay>
        <Menu :items="exportMenuItems" />
      </template>
    </Dropdown>
  </div>
</template>
