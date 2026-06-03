<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Button, Modal, Spin } from 'ant-design-vue';

interface ChunkRow {
  char_count: number;
  chunk_index: number;
  content: string;
  id: number;
}

interface Props {
  chunks: ChunkRow[];
  commonI18nPrefix: string;
  currentPage: number;
  fileName?: string;
  i18nPrefix: string;
  loading: boolean;
  total: number;
}

defineProps<Props>();

const emit = defineEmits<{
  pageChange: [page: number];
}>();

const open = defineModel<boolean>('open', { required: true });
</script>

<template>
  <Modal
    v-model:open="open"
    :title="`${$t(`${i18nPrefix}.document.viewChunks`)} - ${fileName ?? ''}`"
    :footer="null"
    width="720px"
  >
    <Spin :spinning="loading">
      <div
        v-if="chunks.length === 0 && !loading"
        class="flex flex-col items-center justify-center py-12"
      >
        <IconifyIcon
          icon="lucide:layers"
          class="mb-2 size-8 text-muted-foreground"
        />
        <p class="text-sm text-muted-foreground">
          {{ $t(`${i18nPrefix}.emptyChunks`) }}
        </p>
      </div>
      <div v-else class="max-h-[60vh] space-y-3 overflow-y-auto pr-1">
        <div
          v-for="chunk in chunks"
          :key="chunk.id"
          class="rounded-lg border border-border/60 transition-colors hover:border-border"
        >
          <div
            class="flex items-center gap-2 border-b border-border/40 bg-accent/20 px-3 py-2 text-xs text-muted-foreground"
          >
            <span
              class="flex size-5 items-center justify-center rounded bg-primary/10 font-mono font-semibold text-primary"
            >
              {{ chunk.chunk_index }}
            </span>
            <span>{{ chunk.char_count }} chars</span>
          </div>
          <div
            class="max-h-40 overflow-y-auto whitespace-pre-wrap px-3 py-2.5 text-sm leading-relaxed text-foreground"
          >
            {{ chunk.content }}
          </div>
        </div>
      </div>
      <div
        v-if="total > 10"
        class="mt-4 flex items-center justify-center gap-3 text-xs"
      >
        <Button
          v-if="currentPage > 1"
          size="small"
          @click="emit('pageChange', currentPage - 1)"
        >
          <template #icon>
            <IconifyIcon icon="lucide:chevron-left" class="size-3.5" />
          </template>
          {{ $t(`${commonI18nPrefix}.prev`) }}
        </Button>
        <span
          class="rounded-md bg-accent/50 px-2.5 py-1 font-mono text-muted-foreground"
        >
          {{ currentPage }} / {{ Math.ceil(total / 10) }}
        </span>
        <Button
          v-if="currentPage < Math.ceil(total / 10)"
          size="small"
          @click="emit('pageChange', currentPage + 1)"
        >
          {{ $t(`${commonI18nPrefix}.next`) }}
          <template #icon>
            <IconifyIcon icon="lucide:chevron-right" class="size-3.5" />
          </template>
        </Button>
      </div>
    </Spin>
  </Modal>
</template>
