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
    :class="compact ? 'max-w-full gap-1' : 'flex-wrap gap-2'"
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
      class="flex shrink-0 items-center rounded-xl border border-border/40 bg-muted/15 px-1 py-1"
      :class="compact ? 'gap-0' : 'gap-0.5'"
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
      <Tooltip
        v-if="showHeaderMemoryButton"
        :title="$t('common.aiPanel.memory')"
      >
        <button
          data-testid="ai-panel-memory-button"
          class="relative flex size-7 items-center justify-center rounded-lg transition-colors hover:bg-muted disabled:opacity-40"
          :class="
            showMemoryPanel
              ? 'bg-primary/10 text-primary'
              : headerMemoryHasAttention
                ? 'text-primary'
                : 'text-muted-foreground hover:text-foreground'
          "
          :aria-label="$t('common.aiPanel.memory')"
          type="button"
          @click="emit('toggleMemory')"
        >
          <Spin v-if="memoryLoading" size="small" />
          <IconifyIcon v-else icon="lucide:brain" class="size-3.5" />
          <span
            v-if="headerMemoryHasAttention && !showMemoryPanel"
            class="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-primary"
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
</template>
