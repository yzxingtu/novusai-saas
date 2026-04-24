<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AIChatPanelHeader' });

withDefaults(
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
  <div
    class="ai-panel-header flex shrink-0 flex-col gap-1.5 border-b border-border/32 px-3 py-2"
  >
    <div class="flex items-center justify-between gap-3">
      <div class="flex min-w-0 flex-1 items-center gap-2.5">
        <div
          class="ai-panel-header-orb flex size-7 shrink-0 items-center justify-center rounded-[18px] text-primary"
        >
          <IconifyIcon icon="lucide:sparkles" class="size-3.5 shrink-0" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-1.5 leading-none">
            <span
              class="truncate text-[12px] font-semibold tracking-[0.01em] text-foreground/88"
            >
              {{ panelTitle }}
            </span>
            <span
              v-if="routing"
              class="routing-badge relative inline-flex items-center gap-1 overflow-hidden rounded-full px-1.5 py-0.5 text-[9px] font-medium text-primary"
            >
              <span class="routing-dot size-1.5 rounded-full bg-primary"></span>
              {{ $t('common.globalAiChat.routingAgent') }}
              <span class="routing-shimmer absolute inset-0"></span>
            </span>
          </div>
          <div
            v-if="headerConversationSummary"
            data-testid="ai-panel-header-summary"
            class="mt-1 truncate text-[11px] text-muted-foreground/72"
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
          class="ai-panel-header-actions flex shrink-0 items-center gap-0.5 rounded-[16px] px-1 py-1"
        >
          <Tooltip
            :title="
              docked ? $t('common.aiPanel.undock') : $t('common.aiPanel.dock')
            "
          >
            <button
              type="button"
              class="flex size-[26px] items-center justify-center rounded-[12px] transition-colors hover:bg-muted/70"
              :class="
                docked
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground/72 hover:text-foreground/84'
              "
              :aria-label="
                docked ? $t('common.aiPanel.undock') : $t('common.aiPanel.dock')
              "
              @click="emit('toggleDock')"
            >
              <IconifyIcon
                :icon="docked ? 'lucide:lock' : 'lucide:lock-open'"
                class="size-[13px]"
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
              type="button"
              class="flex size-[26px] items-center justify-center rounded-[12px] text-muted-foreground/72 transition-colors hover:bg-muted/70 hover:text-foreground/84"
              :aria-label="
                mode === 'full'
                  ? $t('common.aiPanel.exitFullscreen')
                  : $t('common.aiPanel.fullscreen')
              "
              @click="emit('toggleMode')"
            >
              <IconifyIcon
                :icon="
                  mode === 'full' ? 'lucide:minimize-2' : 'lucide:maximize-2'
                "
                class="size-[13px]"
              />
            </button>
          </Tooltip>
          <Tooltip :title="$t('common.aiPanel.minimize')">
            <button
              type="button"
              class="flex size-[26px] items-center justify-center rounded-[12px] text-muted-foreground/72 transition-colors hover:bg-muted/70 hover:text-foreground/84"
              :aria-label="$t('common.aiPanel.minimize')"
              @click="emit('minimize')"
            >
              <IconifyIcon icon="lucide:minus" class="size-[13px]" />
            </button>
          </Tooltip>
          <Tooltip :title="$t('common.aiPanel.close')">
            <button
              type="button"
              class="flex size-[26px] items-center justify-center rounded-[12px] text-muted-foreground/72 transition-colors hover:bg-muted/70 hover:text-destructive"
              :aria-label="$t('common.aiPanel.close')"
              @click="emit('close')"
            >
              <IconifyIcon icon="lucide:x" class="size-[13px]" />
            </button>
          </Tooltip>
        </div>
      </div>
    </div>

    <Transition name="fade">
      <div
        v-if="routeNotice"
        data-testid="ai-panel-route-banner"
        class="ai-panel-route-banner flex items-start gap-2 rounded-[18px] px-2.5 py-2"
      >
        <div
          class="bg-primary/12 mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-[12px] text-primary"
        >
          <IconifyIcon icon="lucide:route" class="size-3" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="truncate text-[10px] font-medium text-foreground/84">
            {{ routeNotice }}
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.ai-panel-header {
  background:
    linear-gradient(
      180deg,
      hsl(var(--background) / 0.985) 0%,
      hsl(var(--muted) / 0.055) 100%
    );
  backdrop-filter: blur(14px);
}

.ai-panel-header-orb {
  background:
    radial-gradient(
      circle at 30% 30%,
      hsl(var(--primary) / 0.22),
      transparent 58%
    ),
    linear-gradient(
      180deg,
      hsl(var(--background)) 0%,
      hsl(var(--muted) / 0.42) 100%
    );
  border: 1px solid hsl(var(--primary) / 0.16);
  box-shadow:
    0 12px 24px -24px hsl(var(--primary) / 0.4),
    0 1px 0 hsl(var(--background) / 0.84) inset;
}

.ai-panel-header-actions {
  border: 1px solid hsl(var(--border) / 0.34);
  background: hsl(var(--background) / 0.88);
  box-shadow: 0 10px 20px -28px hsl(var(--foreground) / 0.14);
}

.ai-panel-route-banner {
  border: 1px solid hsl(var(--primary) / 0.14);
  background:
    linear-gradient(
      135deg,
      hsl(var(--primary) / 0.075) 0%,
      hsl(var(--background) / 0.92) 72%
    );
}

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
