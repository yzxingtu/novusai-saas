<script setup lang="ts">
import { ref, watch } from 'vue';

import { Alert, Button, Drawer, Space } from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig } from '../types';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
  open: boolean;
}>();

const emit = defineEmits<{
  'update:open': [value: boolean];
  apply: [config: CrudConfig];
}>();

const codeContent = ref('');
const jsonError = ref<string | null>(null);

// Sync config → editor when opening or config changes
watch(
  () => [props.open, props.config],
  () => {
    if (props.open) {
      codeContent.value = JSON.stringify(props.config, null, 2);
      jsonError.value = null;
    }
  },
  { deep: true, immediate: true },
);

function onEditorChange(value: string | undefined) {
  codeContent.value = value ?? '';
  try {
    JSON.parse(codeContent.value);
    jsonError.value = null;
  } catch (e: unknown) {
    jsonError.value = (e as Error).message;
  }
}

function handleApply() {
  try {
    const parsed = JSON.parse(codeContent.value) as CrudConfig;
    emit('apply', parsed);
    emit('update:open', false);
  } catch (e: unknown) {
    jsonError.value = (e as Error).message;
  }
}

function handleFormat() {
  try {
    const parsed = JSON.parse(codeContent.value);
    codeContent.value = JSON.stringify(parsed, null, 2);
    jsonError.value = null;
  } catch {
    // keep current content if invalid
  }
}

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(codeContent.value);
  } catch {
    // clipboard not available
  }
}

function onClose() {
  emit('update:open', false);
}
</script>

<template>
  <Drawer
    :open="open"
    :title="$t(`${T}.mode.jsonEditor`)"
    :width="'50%'"
    placement="right"
    :destroy-on-close="false"
    @close="onClose"
  >
    <template #extra>
      <Space>
        <Button size="small" @click="handleFormat">
          <template #icon>
            <span class="icon-[lucide--align-left] size-3.5" />
          </template>
          {{ $t(`${T}.mode.format`) }}
        </Button>
        <Button size="small" @click="handleCopy">
          <template #icon>
            <span class="icon-[lucide--copy] size-3.5" />
          </template>
          {{ $t(`${T}.mode.copy`) }}
        </Button>
        <Button
          type="primary"
          size="small"
          :disabled="!!jsonError"
          @click="handleApply"
        >
          {{ $t(`${T}.mode.apply`) }}
        </Button>
      </Space>
    </template>

    <div class="flex h-full flex-col">
      <div class="flex-1 overflow-hidden rounded border">
        <textarea
          :value="codeContent"
          class="bg-background text-foreground h-full w-full resize-none border-none p-3 font-mono text-xs leading-relaxed outline-none"
          spellcheck="false"
          @input="(e) => onEditorChange((e.target as HTMLTextAreaElement).value)"
        />
      </div>

      <Alert
        v-if="jsonError"
        type="error"
        class="mt-2"
        :message="jsonError"
        show-icon
      />
    </div>
  </Drawer>
</template>
