<script lang="ts" setup>
import type { AIPageMode } from '@vben/types';

import AIChatSlidePanelShell from './AIChatSlidePanelShell.vue';

defineOptions({ name: 'AIChatSlidePanel' });

const props = withDefaults(
  defineProps<{
    aiMode?: AIPageMode;
    apiPrefix: string;
    disabledCapabilities?: string[];
    disabledOperations?: string[];
    pageContextKey?: string;
    pendingConversationId?: null | number;
    pendingMessage?: null | string;
    showAttachments?: boolean;
    uploadUrl: string;
  }>(),
  {
    aiMode: 'operate',
    disabledCapabilities: undefined,
    disabledOperations: undefined,
    showAttachments: true,
    pendingMessage: null,
    pendingConversationId: null,
    pageContextKey: undefined,
  },
);

const emit = defineEmits<{
  conversationRestored: [];
  messageSent: [];
}>();

const forwardListeners = {
  conversationRestored: () => emit('conversationRestored'),
  messageSent: () => emit('messageSent'),
};
</script>

<template>
  <AIChatSlidePanelShell v-bind="props" v-on="forwardListeners" />
</template>
