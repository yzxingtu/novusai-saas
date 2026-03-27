<script lang="ts" setup>
import type { ItemType } from 'ant-design-vue/es/menu';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Dropdown as ADropdown, Menu as AMenu, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AIChatPanelHeader' });

const props = withDefaults(
  defineProps<{
    canForceReroute?: boolean;
    docked?: boolean;
    forceRerouteNextTurn?: boolean;
    hasHeaderVariableValues?: boolean;
    headerConversationSummary?: string;
    headerMoreHasAttention?: boolean;
    headerMoreMenuItems?: ItemType[];
    mode?: 'full' | 'panel';
    panelTitle: string;
    routeNotice?: null | string;
    routing?: boolean;
    showHeaderMoreMenu?: boolean;
    showHeaderVarsButton?: boolean;
    showHistory?: boolean;
    showRerouteButton?: boolean;
  }>(),
  {
    canForceReroute: false,
    docked: true,
    forceRerouteNextTurn: false,
    hasHeaderVariableValues: false,
    headerConversationSummary: '',
    headerMoreHasAttention: false,
    headerMoreMenuItems: () => [],
    mode: 'panel',
    routeNotice: null,
    routing: false,
    showHeaderMoreMenu: false,
    showHeaderVarsButton: false,
    showHistory: false,
    showRerouteButton: false,
  },
);

const emit = defineEmits<{
  close: [];
  editVars: [];
  minimize: [];
  newChat: [];
  toggleDock: [];
  toggleHistory: [];
  toggleMode: [];
  toggleReroute: [];
}>();

const effectiveHeaderMoreMenuItems = computed(
  () => props.headerMoreMenuItems ?? [],
);
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

    <div class="flex flex-wrap items-start justify-between gap-2">
      <slot></slot>

      <div
        data-testid="ai-panel-header-actions"
        class="flex shrink-0 items-center gap-0.5 rounded-xl border border-border/40 bg-muted/15 px-1 py-1"
      >
        <Tooltip
          v-if="showHeaderVarsButton"
          :title="$t('user.aiChat.varsModal.editVars')"
        >
          <button
            class="hover:bg-primary/8 relative flex h-7 items-center gap-1 rounded-lg px-1.5 text-xs font-medium text-primary transition-colors"
            @click="emit('editVars')"
          >
            <IconifyIcon icon="lucide:sliders-horizontal" class="size-3.5" />
            <span
              v-if="hasHeaderVariableValues"
              class="absolute right-1 top-1 size-1.5 rounded-full bg-green-500"
            ></span>
          </button>
        </Tooltip>
        <Tooltip
          v-if="showRerouteButton"
          :title="$t('common.globalAiChat.rerouteThisTurn')"
        >
          <button
            class="flex size-7 items-center justify-center rounded-lg transition-colors disabled:opacity-40"
            :class="
              forceRerouteNextTurn
                ? 'bg-amber-500/12 text-amber-700'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            "
            :aria-label="$t('common.globalAiChat.rerouteThisTurn')"
            :disabled="!canForceReroute"
            @click="emit('toggleReroute')"
          >
            <IconifyIcon icon="lucide:compass" class="size-3.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('common.aiPanel.newChat')">
          <button
            class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            @click="emit('newChat')"
          >
            <IconifyIcon icon="lucide:plus" class="size-3.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('common.aiPanel.history')">
          <button
            class="flex size-7 items-center justify-center rounded-lg transition-colors hover:bg-muted"
            :class="
              showHistory
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:text-foreground'
            "
            @click="emit('toggleHistory')"
          >
            <IconifyIcon icon="lucide:history" class="size-3.5" />
          </button>
        </Tooltip>
        <ADropdown
          v-if="showHeaderMoreMenu"
          :trigger="['click']"
          placement="bottomRight"
        >
          <Tooltip :title="$t('common.aiPanel.moreActions')">
            <button
              class="relative flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              :aria-label="$t('common.aiPanel.moreActions')"
              type="button"
            >
              <IconifyIcon icon="lucide:ellipsis" class="size-3.5" />
              <span
                v-if="headerMoreHasAttention"
                class="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-primary"
              ></span>
            </button>
          </Tooltip>
          <template #overlay>
            <AMenu :items="effectiveHeaderMoreMenuItems" />
          </template>
        </ADropdown>
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
