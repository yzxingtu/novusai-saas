<script lang="ts" setup>
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Spin, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

import { useUserAIChatWorkspaceContext } from './user-ai-chat-workspace-context';

const {
  page: { chat, showMemoryPanel, onClearMemory },
} = useUserAIChatWorkspaceContext();
const { memoryState, memoryLoading, clearingMemory } = chat;

const memorySections = computed(() =>
  [
    {
      key: 'preferences',
      icon: 'lucide:heart',
      label: $t('common.globalAiChat.memoryPreferences'),
      items: memoryState.value?.preferences ?? [],
    },
    {
      key: 'constraints',
      icon: 'lucide:shield',
      label: $t('common.globalAiChat.memoryConstraints'),
      items: memoryState.value?.constraints ?? [],
    },
    {
      key: 'task_states',
      icon: 'lucide:list-checks',
      label: $t('common.globalAiChat.memoryTaskStates'),
      items: memoryState.value?.task_states ?? [],
    },
    {
      key: 'verified_facts',
      icon: 'lucide:check-circle',
      label: $t('common.globalAiChat.memoryVerifiedFacts'),
      items: memoryState.value?.verified_facts ?? [],
    },
  ].filter((section) => section.items.length > 0),
);
</script>

<template>
  <Transition name="fade">
    <div
      v-if="showMemoryPanel"
      class="user-memory-panel shrink-0 border-b border-border/30 px-4 py-3"
    >
      <div class="mb-2.5 flex items-center justify-between">
        <div
          class="flex items-center gap-1.5 text-xs font-medium text-foreground"
        >
          <IconifyIcon icon="lucide:brain" class="size-3.5 text-primary" />
          {{ $t('common.aiPanel.memory') }}
        </div>
        <Tooltip :title="$t('common.globalAiChat.clearMemory')">
          <button
            class="flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-40"
            :disabled="clearingMemory"
            @click="onClearMemory"
          >
            <Spin v-if="clearingMemory" size="small" />
            <IconifyIcon v-else icon="lucide:eraser" class="size-3" />
            {{ $t('common.globalAiChat.clearMemory') }}
          </button>
        </Tooltip>
      </div>

      <div v-if="memoryLoading" class="py-3 text-center">
        <Spin size="small" />
      </div>

      <div
        v-else-if="memorySections.length === 0"
        class="py-2 text-center text-xs text-muted-foreground"
      >
        {{ $t('common.globalAiChat.clearMemoryEmpty') }}
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="section in memorySections"
          :key="section.key"
          class="user-memory-section rounded-[16px] px-3 py-2.5"
        >
          <div
            class="mb-1 flex items-center gap-1 text-[11px] font-medium text-muted-foreground"
          >
            <IconifyIcon :icon="section.icon" class="size-3" />
            {{ section.label }}
          </div>
          <ul class="space-y-0.5 text-[11px] text-foreground/80">
            <li
              v-for="(item, index) in section.items"
              :key="index"
              class="flex items-start gap-1.5 pl-1"
            >
              <span
                class="mt-1.5 size-1 shrink-0 rounded-full bg-primary/40"
              ></span>
              {{ item }}
            </li>
          </ul>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active {
  transition: opacity 0.2s ease-out;
}

.fade-leave-active {
  transition: opacity 0.3s ease-in;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.user-memory-panel {
  background: hsl(var(--background));
}

.user-memory-section {
  border: 1px solid hsl(var(--border) / 0.18);
  background: hsl(var(--muted) / 0.08);
}
</style>
