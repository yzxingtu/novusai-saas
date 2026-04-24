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

const hasExportActions = computed(() => props.exportMenuItems.length > 0);

const tokenSummary = computed(
  () =>
    `${props.messageCount} ${$t('common.globalAiChat.messages')} · ${props.totalTokensUsed.toLocaleString()} ${$t('common.globalAiChat.tokens')}`,
);
</script>

<template>
  <div
    v-if="isVisible"
    class="flex items-center justify-center gap-1 border-t border-border/12 bg-background/92 px-2 py-0.5 text-[8.75px] text-muted-foreground/58"
  >
    <IconifyIcon icon="lucide:activity" class="size-2.5 text-primary/60" />
    <span>{{ tokenSummary }}</span>
    <span v-if="hasExportActions" class="text-border/70">·</span>
    <ADropdown v-if="hasExportActions" :trigger="['click']" placement="bottomRight">
      <button
        class="inline-flex size-4.5 items-center justify-center rounded-full border border-transparent transition-colors hover:border-border/24 hover:bg-muted/55 hover:text-foreground/78"
        type="button"
      >
        <IconifyIcon icon="lucide:download" class="size-2.5" />
      </button>
      <template #overlay>
        <AMenu :items="exportMenuItems" />
      </template>
    </ADropdown>
  </div>
</template>
