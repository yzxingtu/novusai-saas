<script setup lang="ts">
import {
  Button,
  Empty,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

defineProps<{
  entityModule: string;
  lockedPaths: string[];
}>();

const emit = defineEmits<{
  close: [];
  unlock: [path: string];
  unlockAll: [];
}>();

const T = 'admin.dev.crudGenerator.batchEditor.touchedPaths';
</script>

<template>
  <div class="w-56 shrink-0 rounded-lg border bg-background p-3">
    <div class="mb-3 flex items-center justify-between">
      <div class="flex items-center gap-1.5">
        <span class="icon-[lucide--lock] size-4 text-warning" />
        <span class="text-sm font-medium">{{ $t(`${T}.title`) }}</span>
      </div>
      <Button size="small" type="text" @click="emit('close')">
        <template #icon>
          <span class="icon-[lucide--x] size-3.5" />
        </template>
      </Button>
    </div>

    <div class="mb-2 text-xs text-muted-foreground">
      {{ $t(`${T}.hint`) }}
    </div>

    <div v-if="lockedPaths.length > 0" class="space-y-1.5">
      <div
        v-for="path in lockedPaths"
        :key="path"
        class="flex items-center justify-between rounded bg-warning/10 px-2 py-1"
      >
        <div class="flex items-center gap-1.5">
          <span class="icon-[lucide--lock] size-3 text-warning" />
          <span class="text-xs font-mono">{{ path }}</span>
        </div>
        <Tooltip :title="$t(`${T}.unlock`)">
          <Button size="small" type="text" @click="emit('unlock', path)">
            <template #icon>
              <span class="icon-[lucide--unlock] size-3" />
            </template>
          </Button>
        </Tooltip>
      </div>

      <Button
        block
        class="mt-2"
        size="small"
        type="text"
        @click="emit('unlockAll')"
      >
        <template #icon>
          <span class="icon-[lucide--unlock] size-3.5" />
        </template>
        {{ $t(`${T}.unlockAll`) }}
      </Button>
    </div>

    <Empty
      v-else
      :description="$t(`${T}.noLocked`)"
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
      class="py-4"
    />

    <div v-if="entityModule" class="mt-2 border-t pt-2">
      <Tag color="blue" class="text-xs">{{ entityModule }}</Tag>
    </div>
  </div>
</template>
