<script setup lang="ts">
import { computed } from 'vue';

import { Badge, Collapse } from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig } from '../types';

import AdvancedOptionsSection from './AdvancedOptionsSection.vue';
import BasicInfoSection from './BasicInfoSection.vue';
import EnumEditor from './EnumEditor.vue';
import FieldListSection from './FieldListSection.vue';
import RelationEditor from './RelationEditor.vue';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
}>();

const emit = defineEmits<{
  'update:config': [config: CrudConfig];
  snapshot: [];
  openImport: [];
}>();

const relationCount = computed(() => props.config.relations.length);
const enumCount = computed(() => props.config.enums.length);

function onUpdateConfig(config: CrudConfig) {
  emit('update:config', config);
}

function onSnapshot() {
  emit('snapshot');
}
</script>

<template>
  <div class="config-panel h-full overflow-y-auto p-4">
    <Collapse
      :default-active-key="['basic', 'fields']"
      :bordered="false"
      class="config-collapse"
    >
      <!-- Section 1: Basic Info -->
      <Collapse.Panel key="basic" :header="$t(`${T}.sections.basicInfo`)">
        <BasicInfoSection
          :config="config"
          @update:config="(c) => emit('update:config', c)"
          @snapshot="emit('snapshot')"
        />
      </Collapse.Panel>

      <!-- Section 2: Fields -->
      <Collapse.Panel key="fields">
        <template #header>
          <span>{{ $t(`${T}.sections.fields`) }}</span>
        </template>
        <FieldListSection
          :config="config"
          @update:config="onUpdateConfig"
          @snapshot="onSnapshot"
          @open-import="emit('openImport')"
        />
      </Collapse.Panel>

      <!-- Section 3: Relations -->
      <Collapse.Panel key="relations">
        <template #header>
          <div class="flex items-center gap-2">
            <span>{{ $t(`${T}.sections.relations`) }}</span>
            <Badge
              v-if="relationCount > 0"
              :count="relationCount"
              :number-style="{ backgroundColor: 'var(--primary)' }"
            />
          </div>
        </template>
        <RelationEditor
          :relations="config.relations"
          @update:relations="(rels) => onUpdateConfig({ ...config, relations: rels })"
          @snapshot="onSnapshot"
        />
      </Collapse.Panel>

      <!-- Section 4: Enums -->
      <Collapse.Panel key="enums">
        <template #header>
          <div class="flex items-center gap-2">
            <span>{{ $t(`${T}.sections.enums`) }}</span>
            <Badge
              v-if="enumCount > 0"
              :count="enumCount"
              :number-style="{ backgroundColor: 'var(--primary)' }"
            />
          </div>
        </template>
        <EnumEditor
          :config="config"
          @update:config="onUpdateConfig"
        />
      </Collapse.Panel>

      <!-- Section 5: Advanced Options -->
      <Collapse.Panel key="advanced" :header="$t(`${T}.sections.advanced`)">
        <AdvancedOptionsSection
          :config="config"
          @update:config="onUpdateConfig"
          @snapshot="onSnapshot"
        />
      </Collapse.Panel>
    </Collapse>
  </div>
</template>

<style scoped>
.config-collapse :deep(.ant-collapse-header) {
  font-weight: 500;
}
</style>
