<script setup lang="ts">
import { computed, ref } from 'vue';

import { Tabs } from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig } from '../types';
import type { MockDataRow } from '../composables/use-mock-data';

import FormPreview from './FormPreview.vue';
import ListPreview from './ListPreview.vue';
import StepCodePreview from './StepCodePreview.vue';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
  mockData: MockDataRow[];
}>();

const activeTab = ref<'code' | 'form' | 'list'>('list');

const hasFields = computed(() => props.config.fields.length > 0);

const formPreviewRef = ref<InstanceType<typeof FormPreview> | null>(null);

function openFormPreview() {
  formPreviewRef.value?.open();
}
</script>

<template>
  <div class="preview-panel h-full">
    <Tabs v-model:activeKey="activeTab" size="small" class="px-4 pt-2">
      <Tabs.TabPane key="list">
        <template #tab>
          <span class="flex items-center gap-1">
            <span class="icon-[lucide--table] size-3.5" />
            {{ $t(`${T}.preview.list`) }}
          </span>
        </template>
        <div v-if="hasFields" class="p-4">
          <ListPreview :config="config" :data="mockData" />
        </div>
        <div v-else class="text-muted-foreground py-16 text-center text-sm">
          {{ $t(`${T}.preview.listPlaceholder`) }}
        </div>
      </Tabs.TabPane>

      <Tabs.TabPane key="form">
        <template #tab>
          <span class="flex items-center gap-1">
            <span class="icon-[lucide--square-pen] size-3.5" />
            {{ $t(`${T}.preview.form`) }}
          </span>
        </template>
        <div v-if="hasFields" class="p-4">
          <button
            class="text-primary mb-3 cursor-pointer text-sm underline"
            @click="openFormPreview"
          >
            {{ $t(`${T}.formPreview.createTitle`, { name: config.display_name || 'Item' }) }}
          </button>
          <FormPreview ref="formPreviewRef" :config="config" />
        </div>
        <div v-else class="text-muted-foreground py-16 text-center text-sm">
          {{ $t(`${T}.preview.formPlaceholder`) }}
        </div>
      </Tabs.TabPane>

      <Tabs.TabPane key="code">
        <template #tab>
          <span class="flex items-center gap-1">
            <span class="icon-[lucide--code] size-3.5" />
            {{ $t(`${T}.preview.code`) }} / {{ $t(`${T}.preview.migration`) }}
          </span>
        </template>
        <div v-if="hasFields" class="p-4">
          <StepCodePreview :config="config" />
        </div>
        <div v-else class="text-muted-foreground py-16 text-center text-sm">
          {{ $t(`${T}.preview.codePlaceholder`) }}
        </div>
      </Tabs.TabPane>
    </Tabs>
  </div>
</template>
