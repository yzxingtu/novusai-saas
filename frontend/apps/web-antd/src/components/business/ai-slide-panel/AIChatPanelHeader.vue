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
    class="ai-panel-header border-border/16 flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2"
  >
    <div class="flex min-w-0 flex-1 items-center gap-2">
      <div class="ai-panel-header-mark shrink-0">
        <span class="ai-panel-header-dot">
          <IconifyIcon icon="lucide:sparkles" class="size-2.5 shrink-0" />
        </span>
      </div>
      <div class="min-w-0 flex-1 leading-none">
        <div class="flex min-w-0 items-center gap-1.5">
          <span class="text-foreground/88 truncate text-[12px] font-semibold">
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
            class="ai-panel-route-note text-muted-foreground/66 inline-flex min-w-0 max-w-full items-center gap-1 text-[9.5px]"
          >
            <IconifyIcon
              icon="lucide:route"
              class="text-primary/72 size-2.5 shrink-0"
            />
            <span class="truncate">{{ routeNotice }}</span>
          </div>
          <div
            v-else-if="routing"
            class="text-muted-foreground/62 inline-flex items-center gap-1 text-[9.5px]"
          >
            <IconifyIcon
              icon="lucide:route"
              class="text-primary/72 size-2.5 shrink-0"
            />
            <span>{{ $t('common.globalAiChat.routingAgent') }}</span>
          </div>
          <div
            v-if="headerConversationSummary"
            data-testid="ai-panel-header-summary"
            class="text-muted-foreground/54 truncate text-[9.5px]"
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
            class="flex size-6 items-center justify-center rounded-[9px] transition-colors hover:bg-muted/60"
            :class="
              docked
                ? 'bg-primary/8 text-primary shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.12)]'
                : 'text-muted-foreground/62 hover:text-foreground/82'
            "
            :aria-label="
              docked ? $t('common.aiPanel.undock') : $t('common.aiPanel.dock')
            "
            @click="emit('toggleDock')"
          >
            <IconifyIcon
              :icon="docked ? 'lucide:lock' : 'lucide:lock-open'"
              class="size-3.5"
            />
          </button>
        </Tooltip>
        <Tooltip :title="$t('common.aiPanel.minimize')">
          <button
            type="button"
            class="text-muted-foreground/62 hover:text-foreground/82 flex size-6 items-center justify-center rounded-[9px] transition-colors hover:bg-muted/60"
            :aria-label="$t('common.aiPanel.minimize')"
            @click="emit('minimize')"
          >
            <IconifyIcon icon="lucide:minus" class="size-3.5" />
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
            class="hover:text-foreground/74 flex size-6 items-center justify-center rounded-[9px] text-muted-foreground/50 transition-colors hover:bg-muted/60"
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
              class="size-3.5"
            />
          </button>
        </Tooltip>
        <Tooltip :title="$t('common.aiPanel.close')">
          <button
            type="button"
            class="text-muted-foreground/62 flex size-6 items-center justify-center rounded-[9px] transition-colors hover:bg-muted/60 hover:text-destructive"
            :aria-label="$t('common.aiPanel.close')"
            @click="emit('close')"
          >
            <IconifyIcon icon="lucide:x" class="size-3.5" />
          </button>
        </Tooltip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-panel-header {
  background: hsl(var(--background) / 96%);
  box-shadow: 0 1px 0 hsl(var(--background) / 80%) inset;
  backdrop-filter: blur(10px);
}

.ai-panel-header-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ai-panel-header-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.3rem;
  height: 1.3rem;
  color: hsl(var(--primary));
  background: hsl(var(--muted) / 18%);
  border: 1px solid hsl(var(--border) / 28%);
  border-radius: 10px;
}

.ai-panel-header-actions {
  background: hsl(var(--background) / 70%);
  border: 1px solid hsl(var(--border) / 14%);
  box-shadow: none;
}

.ai-panel-route-note {
  color: hsl(var(--muted-foreground) / 66%);
}
</style>
