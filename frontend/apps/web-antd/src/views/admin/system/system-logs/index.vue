<script lang="ts" setup>
import { Page } from '@vben/common-ui';

import SystemLogCategories from './components/SystemLogCategories.vue';
import SystemLogFileList from './components/SystemLogFileList.vue';
import SystemLogReader from './components/SystemLogReader.vue';
import SystemLogToolbar from './components/SystemLogToolbar.vue';
import { provideSystemLogsContext } from './composables/useSystemLogs';

defineOptions({ name: 'SystemLogList' });

provideSystemLogsContext();
</script>

<template>
  <Page auto-content-height content-class="flex min-h-0 flex-col gap-4 !p-4">
    <SystemLogToolbar />
    <SystemLogCategories />
    <section
      class="grid min-h-0 flex-1 gap-4 xl:grid-cols-[280px_minmax(0,1fr)]"
    >
      <SystemLogFileList />
      <SystemLogReader />
    </section>
  </Page>
</template>

<style scoped>
.scrollbar-thin::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}

.scrollbar-thin::-webkit-scrollbar-thumb {
  background: rgb(148 163 184 / 30%);
  border-radius: 9999px;
}

.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background: rgb(148 163 184 / 55%);
}
</style>
