<script lang="ts" setup>
import type { ItemType } from 'ant-design-vue/es/menu';

import AIChatPanelUtilityActions from './AIChatPanelUtilityActions.vue';

defineOptions({ name: 'AIChatPanelToolbarRow' });

withDefaults(
  defineProps<{
    canForceReroute?: boolean;
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
</script>

<template>
  <div
    data-testid="ai-panel-toolbar-row"
    class="ai-panel-toolbar-row flex w-full shrink-0 items-center justify-end px-1 pb-0.5 pt-0.5 sm:px-1.5"
  >
    <AIChatPanelUtilityActions
      :can-force-reroute="canForceReroute"
      :force-reroute-next-turn="forceRerouteNextTurn"
      :has-header-variable-values="hasHeaderVariableValues"
      :header-memory-has-attention="headerMemoryHasAttention"
      :header-more-has-attention="headerMoreHasAttention"
      :header-more-menu-items="headerMoreMenuItems"
      :memory-loading="memoryLoading"
      :show-header-memory-button="showHeaderMemoryButton"
      :show-header-more-menu="showHeaderMoreMenu"
      :show-header-vars-button="showHeaderVarsButton"
      :show-history="showHistory"
      :show-memory-panel="showMemoryPanel"
      :show-reroute-button="showRerouteButton"
      @edit-vars="emit('editVars')"
      @new-chat="emit('newChat')"
      @toggle-history="emit('toggleHistory')"
      @toggle-memory="emit('toggleMemory')"
      @toggle-reroute="emit('toggleReroute')"
    />
  </div>
</template>

<style scoped>
.ai-panel-toolbar-row {
  background: transparent;
}
</style>
