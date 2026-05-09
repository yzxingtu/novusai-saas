<script lang="ts" setup>
import type { MemoryState } from '#/api/shared/ai-chat';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Spin, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AIChatMemoryPanel' });

const props = withDefaults(
  defineProps<{
    clearing?: boolean;
    loading?: boolean;
    memoryState?: MemoryState | null;
    open?: boolean;
  }>(),
  {
    clearing: false,
    loading: false,
    memoryState: null,
    open: false,
  },
);

const emit = defineEmits<{
  clear: [];
}>();

const sections = computed(() => {
  const state = props.memoryState;
  if (!state) {
    return [];
  }
  return [
    {
      key: 'preferences',
      icon: 'lucide:heart',
      label: $t('common.globalAiChat.memoryPreferences'),
      items: state.preferences,
    },
    {
      key: 'constraints',
      icon: 'lucide:shield',
      label: $t('common.globalAiChat.memoryConstraints'),
      items: state.constraints,
    },
    {
      key: 'task_states',
      icon: 'lucide:list-checks',
      label: $t('common.globalAiChat.memoryTaskStates'),
      items: state.task_states,
    },
    {
      key: 'verified_facts',
      icon: 'lucide:check-circle',
      label: $t('common.globalAiChat.memoryVerifiedFacts'),
      items: state.verified_facts,
    },
    {
      key: 'long_term_memories',
      icon: 'lucide:database',
      label: $t('common.globalAiChat.longTermMemories'),
      items: state.long_term_memories ?? [],
    },
  ].filter((section) => section.items.length > 0);
});

const isEmpty = computed(
  () => !props.memoryState || sections.value.length === 0,
);
</script>

<template>
  <Transition name="fade">
    <div
      v-if="open"
      class="ai-memory-panel shrink-0 border-b border-border/30 px-4 py-3"
    >
      <div class="mb-2.5 flex items-center justify-between">
        <div
          class="text-foreground/84 flex items-center gap-1.5 text-xs font-medium"
        >
          <IconifyIcon icon="lucide:brain" class="size-3.5 text-primary" />
          {{ $t('common.aiPanel.memory') }}
        </div>
        <Tooltip :title="$t('common.globalAiChat.clearMemory')">
          <button
            class="flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-40"
            :disabled="clearing"
            @click="emit('clear')"
          >
            <Spin v-if="clearing" size="small" />
            <IconifyIcon v-else icon="lucide:eraser" class="size-3" />
            {{ $t('common.globalAiChat.clearMemory') }}
          </button>
        </Tooltip>
      </div>

      <div v-if="loading" class="py-3 text-center">
        <Spin size="small" />
      </div>
      <div
        v-else-if="isEmpty"
        class="py-2 text-center text-xs text-muted-foreground"
      >
        {{ $t('common.globalAiChat.clearMemoryEmpty') }}
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="section in sections"
          :key="section.key"
          class="ai-memory-section rounded-[16px] px-3 py-2.5"
        >
          <div
            class="mb-1 flex items-center gap-1 text-[11px] font-medium text-muted-foreground"
          >
            <IconifyIcon :icon="section.icon" class="size-3" />
            {{ section.label }}
          </div>
          <ul class="space-y-0.5 text-[11px] text-foreground/80">
            <li
              v-for="(item, ii) in section.items"
              :key="ii"
              class="flex items-start gap-1.5 pl-1"
            >
              <span class="mt-1.5 size-1 shrink-0 rounded-full bg-primary/40">
              </span>
              {{ item }}
            </li>
          </ul>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.ai-memory-panel {
  background: hsl(var(--background));
}

.ai-memory-section {
  background: hsl(var(--muted) / 8%);
  border: 1px solid hsl(var(--border) / 18%);
}
</style>
