<script setup lang="ts">
import { computed } from 'vue';

import { Handle, Position } from '@vue-flow/core';
import type { NodeProps } from '@vue-flow/core';
import { Badge, Tag, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

interface EntityNodeData {
  module: string;
  label: string;
  fieldCount: number;
  relationCount: number;
  generationOrder: number;
  issueCount: number;
  warningCount: number;
  isSelected: boolean;
}

const props = defineProps<NodeProps<EntityNodeData>>();

const T = 'admin.dev.crudGenerator.erDiagram';

const borderClass = computed(() => {
  if (props.data.issueCount > 0) return 'border-destructive';
  if (props.data.warningCount > 0) return 'border-warning';
  if (props.data.isSelected) return 'border-primary';
  return 'border-border';
});
</script>

<template>
  <div
    class="min-w-[160px] rounded-lg border-2 bg-background shadow-md transition-all"
    :class="[borderClass, data.isSelected ? 'ring-2 ring-primary/30' : '']"
  >
    <!-- Header -->
    <div class="flex items-center justify-between rounded-t-md bg-primary/10 px-3 py-1.5">
      <div class="flex items-center gap-1.5">
        <span class="icon-[lucide--table-2] size-3.5 text-primary" />
        <span class="text-sm font-semibold text-primary">{{ data.label }}</span>
      </div>
      <Tooltip :title="$t(`${T}.generationOrder`)">
        <Badge
          :count="data.generationOrder"
          :number-style="{ backgroundColor: 'var(--ant-color-primary)', fontSize: '10px', minWidth: '16px', height: '16px', lineHeight: '16px' }"
          size="small"
        />
      </Tooltip>
    </div>

    <!-- Body -->
    <div class="space-y-1 px-3 py-2 text-xs">
      <div class="flex items-center justify-between text-muted-foreground">
        <span class="flex items-center gap-1">
          <span class="icon-[lucide--columns-3] size-3" />
          {{ $t(`${T}.fields`) }}
        </span>
        <span>{{ data.fieldCount }}</span>
      </div>
      <div class="flex items-center justify-between text-muted-foreground">
        <span class="flex items-center gap-1">
          <span class="icon-[lucide--git-branch] size-3" />
          {{ $t(`${T}.relations`) }}
        </span>
        <span>{{ data.relationCount }}</span>
      </div>
    </div>

    <!-- Issues/Warnings footer -->
    <div v-if="data.issueCount > 0 || data.warningCount > 0" class="flex gap-1.5 border-t px-3 py-1">
      <Tag v-if="data.issueCount > 0" color="error" class="text-[10px]">
        {{ data.issueCount }} {{ $t(`${T}.issues`) }}
      </Tag>
      <Tag v-if="data.warningCount > 0" color="warning" class="text-[10px]">
        {{ data.warningCount }} {{ $t(`${T}.warnings`) }}
      </Tag>
    </div>

    <!-- Handles -->
    <Handle type="target" :position="Position.Top" class="!bg-primary" />
    <Handle type="source" :position="Position.Bottom" class="!bg-primary" />
    <Handle id="left" type="target" :position="Position.Left" class="!bg-primary" />
    <Handle id="right" type="source" :position="Position.Right" class="!bg-primary" />
  </div>
</template>
