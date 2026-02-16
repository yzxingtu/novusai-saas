<script setup lang="ts">
import { Button, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig } from '../types';

import QuickStartPopover from './QuickStartPopover.vue';

const T = 'admin.dev.crudGenerator';

defineProps<{
  canUndo: boolean;
  canRedo: boolean;
  isDirty: boolean;
  isGenerating: boolean;
  hasModule: boolean;
  hasFields: boolean;
}>();

const emit = defineEmits<{
  undo: [];
  redo: [];
  reset: [];
  generate: [];
  toggleJson: [];
  openHistory: [];
  openImport: [];
  quickStartSelect: [config: CrudConfig];
  openAiChat: [];
  openCommandPalette: [];
}>();
</script>

<template>
  <div class="flex items-center justify-between border-b px-4 py-2">
    <!-- Left: Quick Start / Import / History -->
    <div class="flex items-center gap-1">
      <QuickStartPopover
        :is-dirty="isDirty"
        @select="(c) => emit('quickStartSelect', c)"
      >
        <Button size="small">
          <template #icon>
            <span class="icon-[lucide--zap] size-3.5" />
          </template>
          {{ $t(`${T}.toolbar.quickStart`) }}
        </Button>
      </QuickStartPopover>

      <Button size="small" type="text" @click="emit('openImport')">
        <template #icon>
          <span class="icon-[lucide--database] size-3.5" />
        </template>
        {{ $t(`${T}.toolbar.importDDL`) }}
      </Button>

      <Button size="small" type="text" @click="emit('openHistory')">
        <template #icon>
          <span class="icon-[lucide--history] size-3.5" />
        </template>
        {{ $t(`${T}.toolbar.history`) }}
      </Button>
    </div>

    <!-- Right: Undo/Redo / JSON / AI / Reset / Generate -->
    <div class="flex items-center gap-1">
      <Tooltip title="Ctrl+Z">
        <Button
          :disabled="!canUndo"
          size="small"
          type="text"
          @click="emit('undo')"
        >
          <template #icon>
            <span class="icon-[lucide--undo-2] size-4" />
          </template>
        </Button>
      </Tooltip>

      <Tooltip title="Ctrl+Shift+Z">
        <Button
          :disabled="!canRedo"
          size="small"
          type="text"
          @click="emit('redo')"
        >
          <template #icon>
            <span class="icon-[lucide--redo-2] size-4" />
          </template>
        </Button>
      </Tooltip>

      <div class="bg-border mx-1 h-5 w-px" />

      <Tooltip title="Ctrl+I">
        <Button size="small" type="text" @click="emit('openAiChat')">
          <template #icon>
            <span class="icon-[lucide--sparkles] size-4" />
          </template>
        </Button>
      </Tooltip>

      <Tooltip title="Ctrl+M">
        <Button size="small" type="text" @click="emit('toggleJson')">
          <template #icon>
            <span class="icon-[lucide--braces] size-4" />
          </template>
        </Button>
      </Tooltip>

      <Tooltip title="Ctrl+K">
        <Button size="small" type="text" @click="emit('openCommandPalette')">
          <template #icon>
            <span class="icon-[lucide--command] size-4" />
          </template>
        </Button>
      </Tooltip>

      <Button
        v-if="isDirty"
        danger
        size="small"
        type="text"
        @click="emit('reset')"
      >
        <template #icon>
          <span class="icon-[lucide--rotate-ccw] size-3.5" />
        </template>
        {{ $t(`${T}.reset`) }}
      </Button>

      <div class="bg-border mx-1 h-5 w-px" />

      <Button
        :disabled="!hasModule || !hasFields"
        :loading="isGenerating"
        type="primary"
        size="small"
        @click="emit('generate')"
      >
        <template #icon>
          <span class="icon-[lucide--play] size-3.5" />
        </template>
        {{ $t(`${T}.generate`) }}
      </Button>
    </div>
  </div>
</template>
