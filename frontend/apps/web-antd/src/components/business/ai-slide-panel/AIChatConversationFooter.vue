<script lang="ts" setup>
import type { ItemType } from 'ant-design-vue/es/menu';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

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

const hasVisibleSummary = computed(
  () => props.totalTokensUsed > 0 && props.streaming !== true,
);
const isVisible = computed(() => hasVisibleSummary.value);

const tokenSummary = computed(
  () =>
    `${props.messageCount} ${$t('common.globalAiChat.messages')} · ${props.totalTokensUsed.toLocaleString()} ${$t('common.globalAiChat.tokens')}`,
);
</script>

<template>
  <div
    v-if="isVisible"
    class="border-border/8 flex items-center border-t px-2.5 py-1"
  >
    <div
      data-testid="ai-chat-footer-summary"
      class="text-muted-foreground/58 border-border/12 ml-auto inline-flex items-center gap-1.5 rounded-full border bg-muted/[0.36] px-2.5 py-0.5 text-[8px] font-medium"
    >
      <IconifyIcon icon="lucide:activity" class="text-primary/56 size-2" />
      <span>{{ tokenSummary }}</span>
    </div>
  </div>
</template>
