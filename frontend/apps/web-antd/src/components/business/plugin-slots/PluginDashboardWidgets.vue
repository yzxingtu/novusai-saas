<script setup lang="ts">
import { computed } from 'vue';

import { usePluginSlotsStore } from '#/stores/plugin-slots';

const props = withDefaults(
  defineProps<{
    /** Empty state description / 空状态描述 */
    emptyDescription?: string;
    /** Empty state title / 空状态标题 */
    emptyTitle?: string;
    /** Filter specific plugin (empty=all) / 过滤特定插件 */
    pluginName?: string;
  }>(),
  {
    emptyDescription: undefined,
    emptyTitle: undefined,
    pluginName: undefined,
  },
);

const slotsStore = usePluginSlotsStore();

const widgets = computed(() => {
  if (props.pluginName) {
    return slotsStore.dashboardWidgets.filter(
      (w) => w.pluginName === props.pluginName,
    );
  }
  return slotsStore.dashboardWidgets;
});
</script>

<template>
  <template v-if="widgets.length > 0">
    <div
      class="plugin-dashboard-widgets grid gap-4"
      style="grid-template-columns: repeat(12, 1fr)"
    >
      <div
        v-for="widget in widgets"
        :key="`${widget.pluginName}-${widget.name}`"
        :style="{
          gridColumn: `span ${widget.grid?.w ?? 6}`,
          gridRow: `span ${widget.grid?.h ?? 4}`,
        }"
        class="plugin-dashboard-widget rounded-lg border border-border bg-background p-4 shadow-sm"
      >
        <h4
          v-if="widget.title"
          class="mb-2 text-sm font-medium text-foreground"
        >
          {{ widget.title }}
        </h4>
        <component :is="widget.component" v-if="widget.component" />
      </div>
    </div>
  </template>
  <div
    v-else
    class="rounded-[22px] border border-dashed border-border/70 bg-background/60 px-5 py-8 text-center"
  >
    <div class="text-sm font-medium text-foreground">
      {{ emptyTitle }}
    </div>
    <div
      v-if="emptyDescription"
      class="mt-2 text-sm leading-6 text-muted-foreground"
    >
      {{ emptyDescription }}
    </div>
  </div>
</template>
