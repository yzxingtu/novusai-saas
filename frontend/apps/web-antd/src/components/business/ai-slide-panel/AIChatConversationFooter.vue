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

const hasExportActions = computed(() => props.exportMenuItems.length > 0);
const hasVisibleSummary = computed(
  () => props.totalTokensUsed > 0 && props.streaming !== true,
);
const isVisible = computed(
  () => hasExportActions.value || hasVisibleSummary.value,
);

const tokenSummary = computed(
  () =>
    `${props.messageCount} ${$t('common.globalAiChat.messages')} · ${props.totalTokensUsed.toLocaleString()} ${$t('common.globalAiChat.tokens')}`,
);
</script>

<template>
  <div
    v-if="isVisible"
    class="border-border/12 text-muted-foreground/62 flex items-center justify-center gap-1.5 border-t bg-background px-2 py-1 text-[9px]"
  >
    <template v-if="hasVisibleSummary">
      <IconifyIcon icon="lucide:activity" class="size-2.5 text-primary/60" />
      <span>{{ tokenSummary }}</span>
    </template>
    <span v-if="hasVisibleSummary && hasExportActions" class="text-border/70">
      ·
    </span>
    <ADropdown
      v-if="hasExportActions"
      :trigger="['click']"
      placement="bottomRight"
    >
      <button
        class="hover:border-border/24 hover:text-foreground/78 inline-flex size-5 items-center justify-center rounded-full border border-transparent transition-colors hover:bg-muted/55"
        type="button"
      >
        <IconifyIcon icon="lucide:download" class="size-[11px]" />
      </button>
      <template #overlay>
        <AMenu :items="exportMenuItems" />
      </template>
    </ADropdown>
  </div>
</template>
