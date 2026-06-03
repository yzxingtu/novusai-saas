<script setup lang="ts">
import { ref } from 'vue';

import { usePluginSlotsStore } from '#/stores/plugin-slots';

const slotsStore = usePluginSlotsStore();

const openPanels = ref<Record<string, boolean>>({});

function togglePanel(key: string) {
  openPanels.value[key] = !openPanels.value[key];
}

function panelKey(pluginName: string, name: string) {
  return `${pluginName}-${name}`;
}

function panelStyle(position: string | undefined) {
  switch (position) {
    case 'bottom-left': {
      return { bottom: '24px', left: '24px' };
    }
    case 'top-left': {
      return { top: '80px', left: '24px' };
    }
    case 'top-right': {
      return { top: '80px', right: '24px' };
    }
    default: {
      return { bottom: '24px', right: '24px' };
    }
  }
}
</script>

<template>
  <template
    v-for="panel in slotsStore.floatingPanels"
    :key="`${panel.pluginName}-${panel.name}`"
  >
    <div class="plugin-floating-panel" :style="panelStyle(panel.position)">
      <!-- Trigger button / 触发按钮 -->
      <div
        class="plugin-floating-trigger flex h-10 w-10 cursor-pointer items-center justify-center rounded-full bg-primary/80 text-white shadow-lg transition-all hover:bg-primary"
        :title="panel.title ?? panel.name"
        @click="togglePanel(panelKey(panel.pluginName, panel.name))"
      >
        <span v-if="panel.icon" class="text-sm">{{ panel.icon }}</span>
        <span v-else class="text-xs font-bold">{{
          (panel.name ?? '?')[0]?.toUpperCase()
        }}</span>
      </div>
      <!-- Panel content / 面板内容 -->
      <div
        v-if="openPanels[panelKey(panel.pluginName, panel.name)]"
        class="plugin-floating-content absolute bottom-12 right-0 z-50 min-w-64 rounded-lg border border-border bg-background shadow-xl"
      >
        <component :is="panel.component" v-if="panel.component" />
      </div>
    </div>
  </template>
</template>

<style scoped>
.plugin-floating-panel {
  position: fixed;
  z-index: 1000;
}
</style>
