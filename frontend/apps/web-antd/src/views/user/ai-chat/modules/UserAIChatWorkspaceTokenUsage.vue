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
    class="border-border/16 text-muted-foreground/66 flex items-center justify-center gap-1.5 border-t px-3 py-0.5 text-[10px]"
  >
    <IconifyIcon icon="lucide:activity" class="size-2.5 text-primary/60" />
    <span>
      {{ chatMessages.length }}
      {{ $t('common.globalAiChat.messages') }} ·
      {{ totalTokensUsed.toLocaleString() }}
      {{ $t('common.globalAiChat.tokens') }}
    </span>
    <span class="text-border">|</span>
    <Dropdown :trigger="['click']" placement="bottomRight">
      <button
        class="inline-flex size-5 items-center justify-center rounded-full transition-colors hover:bg-muted hover:text-foreground"
        type="button"
      >
        <IconifyIcon icon="lucide:download" class="size-2.5" />
      </button>
      <template #overlay>
        <Menu :items="exportMenuItems" />
      </template>
    </Dropdown>
  </div>
</template>
