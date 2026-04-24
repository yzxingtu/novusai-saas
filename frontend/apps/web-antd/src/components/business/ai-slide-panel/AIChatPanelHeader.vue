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
    class="ai-panel-header shrink-0 border-b border-border/18"
  >
    <div
      class="ai-panel-header-main flex items-start justify-between gap-2 px-2.5 py-2 sm:px-3"
    >
      <div class="flex min-w-0 flex-1 items-start gap-2">
        <div class="ai-panel-header-mark shrink-0">
          <span class="ai-panel-header-dot">
            <IconifyIcon icon="lucide:sparkles" class="size-2.5 shrink-0" />
          </span>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex min-w-0 items-center gap-1.5 leading-none">
            <span
              class="truncate text-[10.5px] font-semibold uppercase tracking-[0.08em] text-foreground/72 sm:text-[11px]"
            >
              {{ panelTitle }}
            </span>
          </div>
          <div
            v-if="routeNotice || headerConversationSummary || routing"
            class="mt-1 flex min-w-0 flex-wrap items-center gap-1.5"
          >
            <div
              v-if="routeNotice"
              data-testid="ai-panel-route-banner"
              class="ai-panel-route-note inline-flex min-w-0 max-w-full items-center gap-1 rounded-full bg-primary/[0.06] px-1.5 py-[2px] text-[9px] text-muted-foreground/72"
            >
              <IconifyIcon
                icon="lucide:route"
                class="size-2.5 shrink-0 text-primary/72"
              />
              <span class="truncate">{{ routeNotice }}</span>
            </div>
            <div
              v-else-if="routing"
              class="inline-flex items-center gap-1 rounded-full bg-primary/[0.05] px-1.5 py-[2px] text-[9px] text-muted-foreground/66"
            >
              <IconifyIcon
                icon="lucide:route"
                class="size-2.5 shrink-0 text-primary/72"
              />
              <span>{{ $t('common.globalAiChat.routingAgent') }}</span>
            </div>
            <div
              v-if="headerConversationSummary"
              data-testid="ai-panel-header-summary"
              class="truncate text-[9px] text-muted-foreground/56"
            >
              {{ headerConversationSummary }}
            </div>
          </div>
        </div>
      </div>

      <div
        data-testid="ai-panel-primary-actions"
        class="flex shrink-0 flex-wrap items-center justify-end gap-1"
      >
        <div
          class="ai-panel-header-actions flex shrink-0 items-center gap-0.5 rounded-[12px] px-0.5 py-0.5"
        >
          <Tooltip
            :title="
              docked ? $t('common.aiPanel.undock') : $t('common.aiPanel.dock')
            "
          >
            <button
              type="button"
              class="flex size-5.5 items-center justify-center rounded-[10px] transition-colors hover:bg-muted/60"
              :class="
                docked
                  ? 'bg-primary/8 text-primary'
                  : 'text-muted-foreground/66 hover:text-foreground/82'
              "
              :aria-label="
                docked ? $t('common.aiPanel.undock') : $t('common.aiPanel.dock')
              "
              @click="emit('toggleDock')"
            >
              <IconifyIcon
                :icon="docked ? 'lucide:lock' : 'lucide:lock-open'"
                class="size-[0.8rem]"
              />
            </button>
          </Tooltip>
          <Tooltip :title="$t('common.aiPanel.minimize')">
            <button
              type="button"
              class="flex size-5.5 items-center justify-center rounded-[10px] text-muted-foreground/66 transition-colors hover:bg-muted/60 hover:text-foreground/82"
              :aria-label="$t('common.aiPanel.minimize')"
              @click="emit('minimize')"
            >
              <IconifyIcon icon="lucide:minus" class="size-[0.8rem]" />
            </button>
          </Tooltip>
          <Tooltip :title="$t('common.aiPanel.close')">
            <button
              type="button"
              class="flex size-5.5 items-center justify-center rounded-[10px] text-muted-foreground/66 transition-colors hover:bg-muted/60 hover:text-destructive"
              :aria-label="$t('common.aiPanel.close')"
              @click="emit('close')"
            >
              <IconifyIcon icon="lucide:x" class="size-[0.8rem]" />
            </button>
          </Tooltip>
        </div>
      </div>
    </div>

    <div
      v-if="$slots.default"
      class="ai-panel-header-body border-t border-border/10 px-1.5 pb-1.5 pt-1"
    >
      <slot />
    </div>
  </div>
</template>

<style scoped>
.ai-panel-header {
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 0.985) 0%,
    hsl(var(--background) / 0.965) 100%
  );
  backdrop-filter: blur(12px);
}

.ai-panel-header-main {
  min-width: 0;
}

.ai-panel-header-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ai-panel-header-dot {
  display: inline-flex;
  width: 1.45rem;
  height: 1.45rem;
  align-items: center;
  justify-content: center;
  border: 1px solid hsl(var(--border) / 0.24);
  border-radius: 999px;
  color: hsl(var(--primary));
  background: linear-gradient(
    180deg,
    hsl(var(--background)) 0%,
    hsl(var(--muted) / 0.24) 100%
  );
  box-shadow: 0 12px 24px -28px hsl(var(--foreground) / 0.18);
}

.ai-panel-header-actions {
  border: 1px solid hsl(var(--border) / 0.16);
  background: hsl(var(--background) / 0.86);
  box-shadow: 0 14px 24px -34px hsl(var(--foreground) / 0.18);
}

.ai-panel-header-body {
  background: hsl(var(--background) / 0.58);
}

.ai-panel-route-note {
  color: hsl(var(--muted-foreground) / 0.72);
}
</style>
