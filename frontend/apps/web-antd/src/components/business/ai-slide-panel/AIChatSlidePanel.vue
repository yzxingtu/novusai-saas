<script lang="ts" setup>
import AIChatSlidePanelShell from './AIChatSlidePanelShell.vue';

defineOptions({ inheritAttrs: false, name: 'AIChatSlidePanel' });

const props = withDefaults(
  defineProps<{
    apiPrefix: string;
    pendingConversationId?: null | number;
    pendingMessage?: null | string;
    showAttachments?: boolean;
    uploadUrl: string;
  }>(),
  {
    showAttachments: true,
    pendingMessage: null,
    pendingConversationId: null,
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
