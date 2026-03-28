<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AIChatPanelHeader' });

const props = withDefaults(
  defineProps<{
    docked?: boolean;
    headerConversationSummary?: string;
    mode?: 'full' | 'panel';
    panelTitle: string;
    routeNotice?: null | string;
    routing?: boolean;
  }>(),
  {
    docked: true,
    headerConversationSummary: '',
    mode: 'panel',
    routeNotice: null,
    routing: false,
  },
);

const emit = defineEmits<{
  close: [];
  minimize: [];
  toggleDock: [];
  toggleMode: [];
}>();
</script>

<template>
  <div class="flex shrink-0 flex-col gap-2 border-b border-border/40 px-3 py-2">
    <div class="flex items-start justify-between gap-3">
      <div class="flex min-w-0 flex-1 items-start gap-2.5">
        <div
          class="flex size-8 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"
        >
          <IconifyIcon icon="lucide:sparkles" class="size-4 shrink-0" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-1.5">
            <span class="truncate text-sm font-semibold text-foreground">
              {{ panelTitle }}
            </span>
            <span
              v-if="routing"
              class="routing-badge relative inline-flex items-center gap-1 overflow-hidden rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary"
            >
              <span class="routing-dot size-1.5 rounded-full bg-primary"></span>
              {{ $t('common.globalAiChat.routingAgent') }}
              <span class="routing-shimmer absolute inset-0"></span>
            </span>
          </div>
          <div
            v-if="headerConversationSummary"
            class="mt-0.5 truncate text-[11px] text-muted-foreground"
          >
            {{ headerConversationSummary }}
          </div>
        </div>
      </div>

      <div
        data-testid="ai-panel-primary-actions"
        class="flex shrink-0 flex-wrap items-center justify-end gap-2"
      >
        <div
          class="flex shrink-0 items-center gap-0.5 rounded-xl border border-border/40 bg-background/80 px-1 py-1"
        >
          <Tooltip
            :title="
              docked ? $t('common.aiPanel.undock') : $t('common.aiPanel.dock')
            "
          >
            <button
              class="flex size-7 items-center justify-center rounded-lg transition-colors hover:bg-muted"
              :class="
                docked
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              "
              @click="emit('toggleDock')"
            >
              <IconifyIcon
                :icon="docked ? 'lucide:lock' : 'lucide:lock-open'"
                class="size-3.5"
              />
            </button>
          </Tooltip>
          <Tooltip
            :title="
              mode === 'full'
                ? $t('common.aiPanel.exitFullscreen')
                : $t('common.aiPanel.fullscreen')
            "
          >
            <button
              class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              @click="emit('toggleMode')"
            >
              <IconifyIcon
                :icon="
                  mode === 'full' ? 'lucide:minimize-2' : 'lucide:maximize-2'
                "
                class="size-3.5"
              />
            </button>
          </Tooltip>
          <Tooltip :title="$t('common.aiPanel.minimize')">
            <button
              class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              @click="emit('minimize')"
            >
              <IconifyIcon icon="lucide:minus" class="size-3.5" />
            </button>
          </Tooltip>
          <Tooltip :title="$t('common.aiPanel.close')">
            <button
              class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-destructive"
              @click="emit('close')"
            >
              <IconifyIcon icon="lucide:x" class="size-3.5" />
            </button>
          </Tooltip>
        </div>
      </div>
    </div>

    <Transition name="fade">
      <div
        v-if="routeNotice"
        data-testid="ai-panel-route-banner"
        class="flex items-start gap-2 rounded-xl border border-primary/15 bg-primary/5 px-3 py-2"
      >
        <div
          class="bg-primary/12 mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-lg text-primary"
        >
          <IconifyIcon icon="lucide:route" class="size-3" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="truncate text-[11px] font-medium text-foreground/85">
            {{ routeNotice }}
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
@keyframes shimmer-slide {
  0% {
    transform: translateX(-100%);
  }

  100% {
    transform: translateX(100%);
  }
}

@keyframes routing-pulse {
  0%,
  100% {
    opacity: 0.3;
    transform: scale(0.8);
  }

  50% {
    opacity: 1;
    transform: scale(1);
  }
}

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

.routing-shimmer {
  background: linear-gradient(
    90deg,
    transparent 0%,
    hsl(var(--primary) / 6%) 50%,
    transparent 100%
  );
  animation: shimmer-slide 2s ease-in-out infinite;
}

.routing-dot {
  animation: routing-pulse 0.8s ease-in-out infinite;
}
</style>
