<script lang="ts" setup>
/**
 * 字段属性面板 / Field Property Panel
 *
 * 右侧属性面板，选中字段时显示
 */
import { computed, provide } from 'vue';

import { fieldPropertyPanelContextKey } from './field-property-panel/context';
import { getFieldPropertyPanelSectionState } from './field-property-panel/field-property-panel-sections';
import FieldPropertyBasicSection from './field-property-panel/FieldPropertyBasicSection.vue';
import FieldPropertyCascaderSection from './field-property-panel/FieldPropertyCascaderSection.vue';
import FieldPropertyDatabaseSection from './field-property-panel/FieldPropertyDatabaseSection.vue';
import FieldPropertyDividerSection from './field-property-panel/FieldPropertyDividerSection.vue';
import FieldPropertyEmptyState from './field-property-panel/FieldPropertyEmptyState.vue';
import FieldPropertyEnumSection from './field-property-panel/FieldPropertyEnumSection.vue';
import FieldPropertyFormSection from './field-property-panel/FieldPropertyFormSection.vue';
import FieldPropertyRelationSection from './field-property-panel/FieldPropertyRelationSection.vue';
import FieldPropertySelectedHeader from './field-property-panel/FieldPropertySelectedHeader.vue';
import FieldPropertyUploadSection from './field-property-panel/FieldPropertyUploadSection.vue';
import FieldPropertyVisibilitySection from './field-property-panel/FieldPropertyVisibilitySection.vue';
import { useFieldPropertyPanel } from './field-property-panel/use-field-property-panel';

defineOptions({ name: 'FieldPropertyPanel' });

const panel = useFieldPropertyPanel();
provide(fieldPropertyPanelContextKey, panel);

const {
  isDivider,
  selectedField,
  selectedFieldType,
  selectedFormComponent,
  showSelectRelationConfig,
  showTreeRelationConfig,
  showUserRelationConfig,
} = panel;

const sectionState = computed(() =>
  getFieldPropertyPanelSectionState({
    selectedFieldType: selectedFieldType.value,
    selectedFormComponent: selectedFormComponent.value,
    showSelectRelationConfig: showSelectRelationConfig.value,
    showTreeRelationConfig: showTreeRelationConfig.value,
    showUserRelationConfig: showUserRelationConfig.value,
  }),
);
</script>

<template>
  <FieldPropertyEmptyState v-if="!selectedField" />
  <FieldPropertyDividerSection v-else-if="isDivider" />
  <div v-else class="flex flex-1 flex-col overflow-hidden">
    <FieldPropertySelectedHeader />
    <FieldPropertyVisibilitySection />

    <div class="flex-1 overflow-y-auto p-3">
      <div class="flex flex-col gap-2">
        <FieldPropertyBasicSection />
        <FieldPropertyDatabaseSection />
        <FieldPropertyFormSection />
        <FieldPropertyEnumSection v-if="sectionState.showEnumSection" />
        <FieldPropertyRelationSection
          v-for="mode in sectionState.relationModes"
          :key="mode"
          :mode="mode"
        />
        <FieldPropertyCascaderSection v-if="sectionState.showCascaderSection" />
        <FieldPropertyUploadSection v-if="sectionState.showUploadSection" />
      </div>
    </div>
  </div>
</template>
