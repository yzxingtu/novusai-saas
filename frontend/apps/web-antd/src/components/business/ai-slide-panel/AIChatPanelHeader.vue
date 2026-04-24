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
    class="ai-panel-header flex shrink-0 items-center justify-between gap-2.5 border-b border-border/16 px-3.5 py-2.5"
  >
    <div class="flex min-w-0 flex-1 items-center gap-2">
      <div class="ai-panel-header-mark shrink-0">
        <span class="ai-panel-header-dot">
          <IconifyIcon icon="lucide:sparkles" class="size-2.5 shrink-0" />
        </span>
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 items-center gap-1.5 leading-none">
          <span
            class="truncate text-[12.5px] font-semibold tracking-[0.01em] text-foreground/86"
          >
            {{ panelTitle }}
          </span>
        </div>
        <div
          v-if="routeNotice || headerConversationSummary || routing"
          class="mt-0.5 flex min-w-0 items-center gap-1.5"
        >
          <div
            v-if="routeNotice"
            data-testid="ai-panel-route-banner"
            class="ai-panel-route-note inline-flex min-w-0 max-w-full items-center gap-1 text-[10px] text-muted-foreground/66"
          >
            <IconifyIcon
              icon="lucide:route"
              class="size-2.5 shrink-0 text-primary/72"
            />
            <span class="truncate">{{ routeNotice }}</span>
          </div>
          <div
            v-else-if="routing"
            class="inline-flex items-center gap-1 text-[10px] text-muted-foreground/62"
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
            class="truncate text-[10px] text-muted-foreground/54"
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
            class="flex size-6 items-center justify-center rounded-[10px] transition-colors hover:bg-muted/60"
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
              class="size-[0.85rem]"
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
            class="flex size-6 items-center justify-center rounded-[10px] text-muted-foreground/66 transition-colors hover:bg-muted/60 hover:text-foreground/82"
            :aria-label="
              mode === 'full'
                ? $t('common.aiPanel.exitFullscreen')
                : $t('common.aiPanel.fullscreen')
            "
            @click="emit('toggleMode')"
          >
            <IconifyIcon
              :icon="mode === 'full' ? 'lucide:minimize-2' : 'lucide:maximize-2'"
              class="size-[0.85rem]"
            />
          </button>
        </Tooltip>
        <Tooltip :title="$t('common.aiPanel.minimize')">
          <button
            type="button"
            class="flex size-6 items-center justify-center rounded-[10px] text-muted-foreground/66 transition-colors hover:bg-muted/60 hover:text-foreground/82"
            :aria-label="$t('common.aiPanel.minimize')"
            @click="emit('minimize')"
          >
            <IconifyIcon icon="lucide:minus" class="size-[0.85rem]" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('common.aiPanel.close')">
          <button
            type="button"
            class="flex size-6 items-center justify-center rounded-[10px] text-muted-foreground/66 transition-colors hover:bg-muted/60 hover:text-destructive"
            :aria-label="$t('common.aiPanel.close')"
            @click="emit('close')"
          >
            <IconifyIcon icon="lucide:x" class="size-[0.85rem]" />
          </button>
        </Tooltip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-panel-header {
  background: hsl(var(--background) / 0.985);
  backdrop-filter: blur(10px);
}

.ai-panel-header-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ai-panel-header-dot {
  display: inline-flex;
  width: 1.65rem;
  height: 1.65rem;
  align-items: center;
  justify-content: center;
  border: 1px solid hsl(var(--border) / 0.28);
  border-radius: 999px;
  color: hsl(var(--primary));
  background: hsl(var(--muted) / 0.26);
}

.ai-panel-header-actions {
  border: 0;
  background: transparent;
  box-shadow: none;
}

.ai-panel-route-note {
  color: hsl(var(--muted-foreground) / 0.66);
}
</style>
