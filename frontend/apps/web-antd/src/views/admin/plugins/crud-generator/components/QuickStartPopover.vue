<script setup lang="ts">
import { ref } from 'vue';

import { Modal, Popover } from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig } from '../types';
import {
  buildConfigFromPreset,
  QUICK_START_PRESETS,
} from '../composables/quick-start-presets';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  isDirty: boolean;
}>();

const emit = defineEmits<{
  select: [config: CrudConfig];
}>();

const open = ref(false);

function onSelect(presetKey: string) {
  const preset = QUICK_START_PRESETS.find((p) => p.key === presetKey);
  if (!preset) return;

  const apply = () => {
    const config = buildConfigFromPreset(preset);
    emit('select', config);
    open.value = false;
  };

  if (props.isDirty) {
    Modal.confirm({
      title: $t(`${T}.quickStart.confirmOverwrite`),
      onOk: apply,
    });
  } else {
    apply();
  }
}
</script>

<template>
  <Popover
    v-model:open="open"
    :title="$t(`${T}.quickStart.title`)"
    trigger="click"
    placement="bottomLeft"
    overlay-class-name="quick-start-popover"
  >
    <template #content>
      <div class="grid w-[400px] grid-cols-2 gap-2">
        <button
          v-for="preset in QUICK_START_PRESETS"
          :key="preset.key"
          class="hover:border-primary hover:bg-primary/5 flex cursor-pointer items-start gap-2 rounded-lg border border-transparent p-3 text-left transition-colors"
          @click="onSelect(preset.key)"
        >
          <span :class="preset.icon" class="text-primary mt-0.5 size-5 shrink-0" />
          <div class="min-w-0">
            <div class="text-sm font-medium">
              {{ $t(`${T}.quickStart.${preset.key}`) }}
            </div>
            <div class="text-muted-foreground mt-0.5 text-xs leading-snug">
              {{ $t(`${T}.quickStart.${preset.key}Desc`) }}
            </div>
          </div>
        </button>
      </div>
    </template>

    <slot />
  </Popover>
</template>
