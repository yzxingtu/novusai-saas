<script lang="ts" setup>
import type { ItemType } from 'ant-design-vue/es/menu';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Dropdown as ADropdown,
  Menu as AMenu,
  Spin,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AIChatPanelUtilityActions' });

const props = withDefaults(
  defineProps<{
    canForceReroute?: boolean;
    compact?: boolean;
    forceRerouteNextTurn?: boolean;
    hasHeaderVariableValues?: boolean;
    headerMemoryHasAttention?: boolean;
    headerMoreHasAttention?: boolean;
    headerMoreMenuItems?: ItemType[];
    memoryLoading?: boolean;
    showHeaderMemoryButton?: boolean;
    showHeaderMoreMenu?: boolean;
    showHeaderVarsButton?: boolean;
    showHistory?: boolean;
    showMemoryPanel?: boolean;
    showRerouteButton?: boolean;
  }>(),
  {
    canForceReroute: false,
    compact: false,
    forceRerouteNextTurn: false,
    hasHeaderVariableValues: false,
    headerMemoryHasAttention: false,
    headerMoreHasAttention: false,
    headerMoreMenuItems: () => [],
    memoryLoading: false,
    showHeaderMemoryButton: false,
    showHeaderMoreMenu: false,
    showHeaderVarsButton: false,
    showHistory: false,
    showMemoryPanel: false,
    showRerouteButton: false,
  },
);

const emit = defineEmits<{
  editVars: [];
  newChat: [];
  toggleHistory: [];
  toggleMemory: [];
  toggleReroute: [];
}>();

const effectiveHeaderMoreMenuItems = computed(
  () => props.headerMoreMenuItems ?? [],
);
</script>

<template>
  <div
    data-testid="ai-panel-utility-bar"
    class="flex items-center justify-end"
    :class="compact ? 'max-w-full gap-1' : 'flex-wrap gap-1.5'"
  >
    <span
      v-if="forceRerouteNextTurn && !compact"
      data-testid="ai-panel-header-status"
      class="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-1 text-[10px] font-medium text-amber-700"
    >
      <IconifyIcon icon="lucide:compass" class="size-2.5" />
      {{ $t('common.globalAiChat.rerouteArmed') }}
    </span>

    <div
      data-testid="ai-panel-header-actions"
      class="flex shrink-0 items-center"
      :class="
        compact
          ? 'gap-1'
          : 'flex-wrap gap-1.5'
      "
    >
      <Tooltip
        v-if="showHeaderVarsButton"
        :title="$t('user.aiChat.varsModal.editVars')"
      >
        <button
          type="button"
          class="hover:bg-primary/8 relative flex items-center gap-1.5 font-medium text-primary transition-colors"
          :class="
            compact
              ? 'h-7 rounded-lg px-1.5 text-xs'
              : 'ai-panel-utility-chip h-8 rounded-full border px-3 text-[11px]'
          "
          :aria-label="$t('user.aiChat.varsModal.editVars')"
          @click="emit('editVars')"
        >
          <IconifyIcon icon="lucide:sliders-horizontal" class="size-3.5" />
          <span v-if="!compact" class="truncate">
            {{ $t('user.aiChat.varsModal.editVars') }}
          </span>
          <span
            v-if="hasHeaderVariableValues && !compact"
            class="size-2 rounded-full bg-green-500"
          ></span>
        </button>
      </Tooltip>
      <Tooltip
        v-if="showRerouteButton"
        :title="$t('common.globalAiChat.rerouteThisTurn')"
      >
        <button
          type="button"
          class="flex items-center justify-center transition-colors disabled:opacity-40"
          :class="
            compact
              ? forceRerouteNextTurn
                ? 'size-7 rounded-lg bg-amber-500/12 text-amber-700'
                : 'size-7 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground'
              : forceRerouteNextTurn
                ? 'ai-panel-utility-chip h-8 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 text-[11px] text-amber-700'
                : 'ai-panel-utility-chip h-8 rounded-full border px-3 text-[11px] text-muted-foreground'
          "
          :aria-label="$t('common.globalAiChat.rerouteThisTurn')"
          :disabled="!canForceReroute"
          @click="emit('toggleReroute')"
        >
          <IconifyIcon icon="lucide:compass" class="size-3.5" />
          <span v-if="!compact" class="truncate">
            {{ $t('common.globalAiChat.rerouteThisTurn') }}
          </span>
        </button>
      </Tooltip>
      <Tooltip :title="$t('common.aiPanel.newChat')">
        <button
          type="button"
          class="flex items-center justify-center text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          :class="
            compact
              ? 'size-7 rounded-lg'
              : 'ai-panel-utility-chip h-8 rounded-full border px-3 text-[11px] font-medium'
          "
          :aria-label="$t('common.aiPanel.newChat')"
          @click="emit('newChat')"
        >
          <IconifyIcon icon="lucide:plus" class="size-3.5" />
          <span v-if="!compact" class="truncate">
            {{ $t('common.aiPanel.newChat') }}
          </span>
        </button>
      </Tooltip>
      <Tooltip :title="$t('common.aiPanel.history')">
        <button
          type="button"
          class="flex items-center justify-center transition-colors hover:bg-muted"
          :class="
            compact
              ? showHistory
                ? 'size-7 rounded-lg bg-primary/10 text-primary'
                : 'size-7 rounded-lg text-muted-foreground hover:text-foreground'
              : showHistory
                ? 'ai-panel-utility-chip h-8 rounded-full border border-primary/20 bg-primary/10 px-3 text-[11px] font-medium text-primary'
                : 'ai-panel-utility-chip h-8 rounded-full border px-3 text-[11px] font-medium text-muted-foreground'
          "
          :aria-label="$t('common.aiPanel.history')"
          @click="emit('toggleHistory')"
        >
          <IconifyIcon icon="lucide:history" class="size-3.5" />
          <span v-if="!compact" class="truncate">
            {{ $t('common.aiPanel.history') }}
          </span>
        </button>
      </Tooltip>
      <Tooltip
        v-if="showHeaderMemoryButton"
        :title="$t('common.aiPanel.memory')"
      >
        <button
          data-testid="ai-panel-memory-button"
          type="button"
          class="relative flex items-center justify-center transition-colors hover:bg-muted disabled:opacity-40"
          :class="
            compact
              ? showMemoryPanel
                ? 'size-7 rounded-lg bg-primary/10 text-primary'
                : headerMemoryHasAttention
                  ? 'size-7 rounded-lg text-primary'
                  : 'size-7 rounded-lg text-muted-foreground hover:text-foreground'
              : showMemoryPanel
                ? 'ai-panel-utility-chip h-8 rounded-full border border-primary/20 bg-primary/10 px-3 text-[11px] font-medium text-primary'
                : headerMemoryHasAttention
                  ? 'ai-panel-utility-chip h-8 rounded-full border border-primary/20 bg-primary/[0.06] px-3 text-[11px] font-medium text-primary'
                  : 'ai-panel-utility-chip h-8 rounded-full border px-3 text-[11px] font-medium text-muted-foreground'
          "
          :aria-label="$t('common.aiPanel.memory')"
          @click="emit('toggleMemory')"
        >
          <Spin v-if="memoryLoading" size="small" />
          <IconifyIcon v-else icon="lucide:brain" class="size-3.5" />
          <span v-if="!compact" class="truncate">
            {{ $t('common.aiPanel.memory') }}
          </span>
          <span
            v-if="headerMemoryHasAttention && !showMemoryPanel && !compact"
            class="size-2 rounded-full bg-primary"
          ></span>
        </button>
      </Tooltip>
      <ADropdown
        v-if="showHeaderMoreMenu"
        :trigger="['click']"
        placement="bottomRight"
      >
        <Tooltip :title="$t('common.aiPanel.moreActions')">
          <button
            type="button"
            class="relative flex items-center justify-center text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            :class="
              compact
                ? 'size-7 rounded-lg'
                : 'ai-panel-utility-chip h-8 rounded-full border px-3 text-[11px] font-medium'
            "
            :aria-label="$t('common.aiPanel.moreActions')"
          >
            <IconifyIcon icon="lucide:ellipsis" class="size-3.5" />
            <span v-if="!compact" class="truncate">
              {{ $t('common.aiPanel.moreActions') }}
            </span>
            <span
              v-if="headerMoreHasAttention && !compact"
              class="size-2 rounded-full bg-primary"
            ></span>
          </button>
        </Tooltip>
        <template #overlay>
          <AMenu :items="effectiveHeaderMoreMenuItems" />
        </template>
      </ADropdown>
    </div>
  </div>
</template>

<style scoped>
.ai-panel-utility-chip {
  border-color: hsl(var(--border) / 0.2);
  background: hsl(var(--background) / 0.9);
  box-shadow: 0 8px 16px -28px hsl(var(--foreground) / 0.1);
}
</style>
