<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

defineOptions({ name: 'AIChatPanelMinimizedBubble' });

const props = defineProps<{
  hasUnread: boolean;
  open: boolean;
}>();

const emit = defineEmits<{
  close: [];
  restore: [];
}>();
</script>

<template>
  <Transition name="bubble">
    <div
      v-if="open"
      class="fixed bottom-6 right-6 z-[2001] flex cursor-pointer items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-primary-foreground shadow-lg transition-all hover:shadow-xl hover:brightness-110"
      @click="emit('restore')"
    >
      <IconifyIcon icon="lucide:sparkles" class="size-5" />
      <span class="text-sm font-medium">
        {{ $t('common.aiPanel.title') }}
      </span>
      <span
        v-if="hasUnread"
        class="size-2 rounded-full bg-destructive"
      ></span>
      <IconifyIcon
        icon="lucide:x"
        class="ml-1 size-3.5 opacity-60 hover:opacity-100"
        @click.stop="emit('close')"
      />
    </div>
  </Transition>
</template>
