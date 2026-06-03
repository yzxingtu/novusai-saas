<script setup lang="ts">
import { ref, watch } from 'vue';

import { usePluginSlotsStore } from '#/stores/plugin-slots';

const slotsStore = usePluginSlotsStore();
const activeTab = ref<string>('');

function tabKey(tab: { name: string; pluginName: string }): string {
  return `${tab.pluginName}-${tab.name}`;
}

watch(
  () => slotsStore.settingsTabs,
  (tabs) => {
    if (tabs.length === 0) {
      activeTab.value = '';
      return;
    }
    const existing = tabs.some((tab) => tabKey(tab) === activeTab.value);
    if (!existing) {
      activeTab.value = tabKey(tabs[0]!);
    }
  },
  { deep: true, immediate: true },
);
</script>

<template>
  <template v-if="slotsStore.settingsTabs.length > 0">
    <a-tabs v-model:active-key="activeTab" class="plugin-settings-tabs">
      <a-tab-pane
        v-for="tab in slotsStore.settingsTabs"
        :key="tabKey(tab)"
        :tab="tab.title ?? tab.name"
      >
        <component :is="tab.component" v-if="tab.component" />
      </a-tab-pane>
    </a-tabs>
  </template>
</template>
