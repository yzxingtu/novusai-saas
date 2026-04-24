<script lang="ts" setup>
import type { ItemType } from 'ant-design-vue/es/menu';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Dropdown as ADropdown, Menu as AMenu } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AIChatConversationFooter' });

const props = withDefaults(
  defineProps<{
    exportMenuItems?: ItemType[];
    messageCount?: number;
    streaming?: boolean;
    totalTokensUsed?: number;
  }>(),
  {
    exportMenuItems: () => [],
    messageCount: 0,
    streaming: false,
    totalTokensUsed: 0,
  },
);

const isVisible = computed(
  () => props.totalTokensUsed > 0 && props.streaming !== true,
);

const tokenSummary = computed(
  () =>
    `${props.messageCount} ${$t('common.globalAiChat.messages')} · ${props.totalTokensUsed.toLocaleString()} ${$t('common.globalAiChat.tokens')}`,
);
</script>

<template>
  <div
    v-if="isVisible"
    class="flex items-center justify-center gap-2 border-t border-border/18 bg-background/94 px-4 py-1.5 text-[8.5px] text-muted-foreground/68"
  >
    <IconifyIcon icon="lucide:activity" class="size-3 text-primary/72" />
    <span>{{ tokenSummary }}</span>
    <span class="text-border/70">|</span>
    <ADropdown :trigger="['click']" placement="bottomRight">
      <button class="transition-colors hover:text-foreground/82" type="button">
        <IconifyIcon icon="lucide:download" class="size-3" />
      </button>
      <template #overlay>
        <AMenu :items="exportMenuItems" />
      </template>
    </ADropdown>
  </div>
</template>
