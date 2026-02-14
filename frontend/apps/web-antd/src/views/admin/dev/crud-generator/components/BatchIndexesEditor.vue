<script setup lang="ts">
import { computed } from 'vue';

import {
  Button,
  Empty,
  Input,
  Popconfirm,
  Select,
  Switch,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, IndexConfig } from '../types';

const props = defineProps<{
  entity: CrudConfig;
}>();

const emit = defineEmits<{
  touched: [path: string];
}>();

const fieldOptions = computed(() =>
  props.entity.fields.map((f) => ({ value: f.name, label: f.name || '(unnamed)' })),
);

function addIndex() {
  const idx: IndexConfig = {
    name: null,
    fields: [],
    unique: false,
  };
  props.entity.indexes.push(idx);
  emit('touched', 'indexes');
}

function removeIndex(index: number) {
  props.entity.indexes.splice(index, 1);
  emit('touched', 'indexes');
}

function onIndexChange() {
  emit('touched', 'indexes');
}
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
      <span class="text-sm font-medium">
        {{ $t('admin.dev.crudGenerator.batchEditor.tabs.indexes') }}
        ({{ entity.indexes.length }})
      </span>
      <Button size="small" type="primary" @click="addIndex">
        <template #icon>
          <span class="icon-[lucide--plus] size-3.5" />
        </template>
        {{ $t('common.add') }}
      </Button>
    </div>

    <div v-if="entity.indexes.length > 0" class="space-y-3">
      <div
        v-for="(idx, i) in entity.indexes"
        :key="i"
        class="flex items-center gap-3 rounded-lg border bg-accent/30 p-3"
      >
        <div class="min-w-0 flex-1">
          <div class="grid grid-cols-3 gap-3">
            <div>
              <label class="mb-1 block text-xs text-muted-foreground">
                {{ $t('common.name') }}
              </label>
              <Input
                :value="idx.name ?? ''"
                placeholder="auto"
                size="small"
                @update:value="(v: string) => { idx.name = v || null; onIndexChange(); }"
              />
            </div>
            <div class="col-span-2">
              <label class="mb-1 block text-xs text-muted-foreground">
                {{ $t('admin.dev.crudGenerator.batchEditor.tabs.fields') }}
              </label>
              <Select
                v-model:value="idx.fields"
                :options="fieldOptions"
                class="w-full"
                mode="multiple"
                placeholder="Select fields"
                size="small"
                @change="onIndexChange"
              />
            </div>
          </div>
          <div class="mt-2">
            <label class="flex items-center gap-1.5 text-xs">
              <Switch
                v-model:checked="idx.unique"
                size="small"
                @change="onIndexChange"
              />
              Unique
            </label>
          </div>
        </div>

        <Popconfirm
          :title="$t('common.confirmDelete')"
          @confirm="removeIndex(i)"
        >
          <Button danger size="small" type="text">
            <template #icon>
              <span class="icon-[lucide--trash-2] size-3.5" />
            </template>
          </Button>
        </Popconfirm>
      </div>
    </div>

    <Empty
      v-else
      :description="$t('admin.dev.crudGenerator.batchEditor.tabs.indexes')"
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
    />
  </div>
</template>
