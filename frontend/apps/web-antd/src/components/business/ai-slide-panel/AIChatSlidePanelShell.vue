<script lang="ts" setup>
import type {
  AIChatSlidePanelShellEmit,
  AIChatSlidePanelShellProps,
} from './use-ai-chat-slide-panel-shell';

import AgentVarsModal from './AgentVarsModal.vue';
import AIChatMemoryPanel from './AIChatMemoryPanel.vue';
import AIChatPanelBody from './AIChatPanelBody.vue';
import AIChatPanelHeader from './AIChatPanelHeader.vue';
import AIChatPanelOverlays from './AIChatPanelOverlays.vue';
import AIChatPanelToolbarRow from './AIChatPanelToolbarRow.vue';
import { useAIChatSlidePanelShell } from './use-ai-chat-slide-panel-shell';

defineOptions({ name: 'AIChatSlidePanelShell' });

const props = withDefaults(defineProps<AIChatSlidePanelShellProps>(), {
  showAttachments: true,
  pendingMessage: null,
  pendingConversationId: null,
});

const emit = defineEmits<AIChatSlidePanelShellEmit>();

const {
  aiPanelStore,
  agentVarsModalListeners,
  agentVarsModalProps,
  clearingMemory,
  dragging,
  effectivePanelStyle,
  headerListeners,
  headerProps,
  isFullMode,
  memoryLoading,
  memoryState,
  onClearMemory,
  onDragStart,
  overlayListeners,
  overlayProps,
  panelBodyListeners,
  panelBodyProps,
  setPanelRef,
  showHistory,
  showMemoryPanel,
  streaming,
  toolbarListeners,
  toolbarProps,
} = useAIChatSlidePanelShell(props, emit);
</script>

<template>
  <Teleport to="body">
    <!-- Panel -->
    <Transition name="slide-panel">
      <div
        v-if="aiPanelStore.visible"
        :ref="setPanelRef"
        data-ai-panel
        class="ai-chat-slide-panel-shell fixed right-0 top-0 z-[2001] flex h-full flex-col overflow-hidden transition-[width] duration-200"
        :class="isFullMode ? 'full-mode-shell' : 'panel-mode-shell'"
        :style="effectivePanelStyle"
      >
        <!-- Drag handle (left edge, hidden in fullscreen) -->
        <div
          v-if="!isFullMode"
          class="absolute left-0 top-0 z-10 h-full w-1 cursor-col-resize transition-colors hover:bg-primary/30"
          :class="dragging ? 'bg-primary/40' : ''"
          @mousedown="onDragStart"
        ></div>

        <AgentVarsModal
          v-bind="agentVarsModalProps"
          v-on="agentVarsModalListeners"
        />

        <!-- Header -->
        <AIChatPanelHeader v-bind="headerProps" v-on="headerListeners" />

        <AIChatPanelToolbarRow v-bind="toolbarProps" v-on="toolbarListeners" />

        <!-- Streaming progress bar (T5) -->
        <div
          v-if="streaming"
          class="h-0.5 w-full overflow-hidden bg-primary/10"
        >
          <div class="streaming-bar h-full bg-primary/60"></div>
        </div>

        <AIChatMemoryPanel
          :open="showMemoryPanel && !showHistory"
          :loading="memoryLoading"
          :clearing="clearingMemory"
          :memory-state="memoryState"
          @clear="onClearMemory"
        />

        <AIChatPanelBody v-bind="panelBodyProps" v-on="panelBodyListeners" />
      </div>
    </Transition>

    <AIChatPanelOverlays v-bind="overlayProps" v-on="overlayListeners" />
  </Teleport>
</template>

<style scoped src="./ai-chat-slide-panel-shell.css"></style>
