<script setup lang="ts">
import { ref } from 'vue';

import { usePluginSlotsStore } from '#/stores/plugin-slots';

const slotsStore = usePluginSlotsStore();
const activeTab = ref<string>('');
</script>

<template>
  <template v-if="slotsStore.settingsTabs.length > 0">
    <a-tabs v-model:activeKey="activeTab" class="plugin-settings-tabs">
      <a-tab-pane
        v-for="tab in slotsStore.settingsTabs"
        :key="`${tab.pluginName}-${tab.name}`"
        :tab="tab.title ?? tab.name"
      >
        <component :is="tab.component" v-if="tab.component" />
      </a-tab-pane>
    </a-tabs>
  </template>
</template>
