<script setup lang="ts">
import { computed, ref } from 'vue';

import {
  Badge,
  Button,
  Card,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Select,
  Switch,
  Tabs,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { UseBatchEditorReturn } from '../composables/use-batch-editor';
import { useTemplates } from '../composables/use-templates';
import type {
  BatchEditorTab,
  BatchPreviewResult,
  BatchWriteSummary,
  EntityRelation,
  RelationType,
} from '../types';

import BatchEnumsEditor from './BatchEnumsEditor.vue';
import BatchFieldsEditor from './BatchFieldsEditor.vue';
import BatchGenerationPreview from './BatchGenerationPreview.vue';
import BatchIndexesEditor from './BatchIndexesEditor.vue';
import BatchRelationsEditor from './BatchRelationsEditor.vue';
import ErDiagram from './er-diagram/ErDiagram.vue';
import TemplatePanel from './TemplatePanel.vue';
import TouchedPathsPanel from './TouchedPathsPanel.vue';

const props = defineProps<{
  editor: UseBatchEditorReturn;
}>();

const T = 'admin.dev.crudGenerator.batchEditor';

// ---- New entity dialog ----
const showNewEntityDialog = ref(false);
const newEntityModule = ref('');
const newEntityDisplayName = ref('');

function openNewEntityDialog() {
  newEntityModule.value = '';
  newEntityDisplayName.value = '';
  showNewEntityDialog.value = true;
}

function confirmNewEntity() {
  const mod = newEntityModule.value.trim();
  const name = newEntityDisplayName.value.trim();
  if (!mod) return;

  props.editor.addEntity(mod, name || mod);
  showNewEntityDialog.value = false;
}

// ---- Tab items ----
const tabItems = computed(() => {
  const tabs: Array<{ key: BatchEditorTab; label: string; icon: string }> = [
    { key: 'basic', label: $t(`${T}.tabs.basic`), icon: 'icon-[lucide--file-text]' },
    { key: 'fields', label: $t(`${T}.tabs.fields`), icon: 'icon-[lucide--columns]' },
    { key: 'relations', label: $t(`${T}.tabs.relations`), icon: 'icon-[lucide--link]' },
    { key: 'enums', label: $t(`${T}.tabs.enums`), icon: 'icon-[lucide--list]' },
    { key: 'indexes', label: $t(`${T}.tabs.indexes`), icon: 'icon-[lucide--database]' },
  ];
  return tabs;
});

// ---- Cross-relation helpers ----
const relationTypeOptions = computed(() => [
  { value: 'belongs_to', label: $t('admin.dev.crudGenerator.relation.belongsTo') },
  { value: 'has_many', label: $t('admin.dev.crudGenerator.relation.hasMany') },
  { value: 'self_ref_tree', label: $t('admin.dev.crudGenerator.relation.selfRefTree') },
]);

const newCrossRelation = ref({
  source_entity: '',
  target_entity: '',
  relation_type: 'belongs_to' as RelationType,
  foreign_key: '',
  nullable: true,
});

function addCrossRelation() {
  if (!newCrossRelation.value.source_entity || !newCrossRelation.value.target_entity) return;
  const rel: EntityRelation = {
    ...newCrossRelation.value,
    foreign_key: newCrossRelation.value.foreign_key || null,
  };
  props.editor.addCrossRelation(rel);
  newCrossRelation.value = {
    source_entity: '',
    target_entity: '',
    relation_type: 'belongs_to' as RelationType,
    foreign_key: '',
    nullable: true,
  };
}

// ---- TouchedPaths panel toggle ----
const showTouchedPaths = ref(false);

// ---- Clone entity dialog ----
const showCloneDialog = ref(false);
const cloneSource = ref('');
const cloneModule = ref('');
const cloneTableName = ref('');
const cloneDisplayName = ref('');
const cloneDisplayNameEn = ref('');
const cloneIncludeRelations = ref(true);
const cloneIncludeEnums = ref(true);
const cloneIncludeCrossRelations = ref(false);
const cloneError = ref('');

const CT = 'admin.dev.crudGenerator.cloneEntity';

function openCloneDialog(sourceModule: string) {
  cloneSource.value = sourceModule;
  cloneModule.value = `${sourceModule}-copy`;
  cloneTableName.value = `${sourceModule.replace(/-/g, '_')}_copys`;
  cloneDisplayName.value = '';
  cloneDisplayNameEn.value = '';
  cloneIncludeRelations.value = true;
  cloneIncludeEnums.value = true;
  cloneIncludeCrossRelations.value = false;
  cloneError.value = '';
  showCloneDialog.value = true;
}

function confirmClone() {
  const result = props.editor.cloneEntity({
    sourceModule: cloneSource.value,
    newModule: cloneModule.value,
    newTableName: cloneTableName.value,
    newDisplayName: cloneDisplayName.value || cloneModule.value,
    newDisplayNameEn: cloneDisplayNameEn.value || cloneModule.value,
    includeRelations: cloneIncludeRelations.value,
    includeEnums: cloneIncludeEnums.value,
    includeCrossRelations: cloneIncludeCrossRelations.value,
  });
  if (result.success) {
    showCloneDialog.value = false;
  } else {
    cloneError.value = result.error ?? '';
  }
}

// ---- Template management ----
const templateManager = useTemplates();
const showTemplates = ref(false);

// ---- ER Diagram toggle ----
const showErDiagram = ref(false);

// ---- Batch generation preview/summary ----
const batchPreview = ref<BatchPreviewResult | null>(null);
const batchSummary = ref<BatchWriteSummary | null>(null);
const isGenerating = ref(false);
const showPreview = ref(false);

function onConfirmGenerate() {
  isGenerating.value = true;
  // Actual generation would be triggered via backend API
  // This is the UI scaffold - backend integration in M58-T6-3
}

function onConfirmPartial(_entities: string[]) {
  isGenerating.value = true;
  // Partial generation for selected entities only
  // Backend integration pending
}

function onUpdateStrategy(path: string, _strategy: string) {
  if (!batchPreview.value) return;
  for (const group of batchPreview.value.entityGroups) {
    const file = group.files.find((f) => f.path === path);
    if (file) {
      file.action = _strategy as 'skip' | 'overwrite' | 'merge' | 'patch';
      break;
    }
  }
  const shared = batchPreview.value.sharedFiles.find((f) => f.path === path);
  if (shared) {
    shared.action = _strategy as 'skip' | 'overwrite' | 'merge' | 'patch';
  }
}

function onApplyAllStrategy(strategy: string) {
  if (!batchPreview.value) return;
  const action = strategy as 'skip' | 'overwrite' | 'merge' | 'patch';
  for (const group of batchPreview.value.entityGroups) {
    for (const file of group.files) {
      if (file.isConflict) file.action = action;
    }
  }
  for (const file of batchPreview.value.sharedFiles) {
    if (file.isConflict) file.action = action;
  }
}

// ---- Basic info change → markTouched ----
function onBasicFieldChange(fieldName: string) {
  const mod = props.editor.selectedModule.value;
  if (mod) {
    props.editor.markTouched(mod, fieldName);
  }
}
</script>

<template>
  <div class="flex h-full gap-4">
    <!-- ============ Left: Entity List ============ -->
    <div class="w-64 shrink-0">
      <Card size="small" class="h-full">
        <template #title>
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">{{ $t(`${T}.entityList`) }}</span>
            <Badge
              :count="editor.entities.value.length"
              :number-style="{ backgroundColor: 'var(--ant-color-primary)' }"
              :overflow-count="99"
            />
          </div>
        </template>
        <template #extra>
          <Tooltip :title="$t(`${T}.addEntity`)">
            <Button size="small" type="text" @click="openNewEntityDialog">
              <template #icon>
                <span class="icon-[lucide--plus] size-4" />
              </template>
            </Button>
          </Tooltip>
        </template>

        <!-- Search -->
        <Input
          v-model:value="editor.searchQuery.value"
          :placeholder="$t(`${T}.searchEntity`)"
          allow-clear
          size="small"
          class="mb-3"
        >
          <template #prefix>
            <span class="icon-[lucide--search] size-3.5 text-muted-foreground" />
          </template>
        </Input>

        <!-- Entity List -->
        <div v-if="editor.filteredEntities.value.length > 0" class="space-y-1">
          <div
            v-for="entity in editor.filteredEntities.value"
            :key="entity.module"
            class="group flex cursor-pointer items-center justify-between rounded-md px-2 py-1.5 transition-colors hover:bg-accent"
            :class="{
              'bg-primary/10 text-primary': entity.module === editor.selectedModule.value,
            }"
            @click="editor.selectEntity(entity.module)"
          >
            <div class="flex min-w-0 flex-1 flex-col">
              <span class="truncate text-sm font-medium">{{ entity.display_name || entity.module }}</span>
              <span class="truncate text-xs text-muted-foreground">{{ entity.module }}</span>
            </div>
            <div class="flex shrink-0 items-center gap-1">
              <Badge
                v-if="editor.entityErrorCounts.value[entity.module]"
                :count="editor.entityErrorCounts.value[entity.module]"
                :number-style="{ backgroundColor: 'var(--ant-color-error)' }"
                size="small"
              />
              <Tooltip :title="$t(`${CT}.title`)">
                <Button
                  class="opacity-0 group-hover:opacity-100"
                  size="small"
                  type="text"
                  @click.stop="openCloneDialog(entity.module)"
                >
                  <template #icon>
                    <span class="icon-[lucide--copy] size-3.5" />
                  </template>
                </Button>
              </Tooltip>
              <Popconfirm
                :title="$t(`${T}.confirmRemove`, { name: entity.display_name || entity.module })"
                @confirm="editor.removeEntity(entity.module)"
              >
                <Button
                  class="opacity-0 group-hover:opacity-100"
                  danger
                  size="small"
                  type="text"
                  @click.stop
                >
                  <template #icon>
                    <span class="icon-[lucide--trash-2] size-3.5" />
                  </template>
                </Button>
              </Popconfirm>
            </div>
          </div>
        </div>
        <Empty
          v-else
          :description="$t(`${T}.noEntities`)"
          class="py-8"
        />

        <!-- TouchedPaths Toggle -->
        <div class="mt-3 border-t pt-3">
          <Button
            block
            size="small"
            type="text"
            @click="showTouchedPaths = !showTouchedPaths"
          >
            <template #icon>
              <span class="icon-[lucide--lock] size-3.5" />
            </template>
            {{ $t(`${T}.touchedPaths.title`) }}
          </Button>
        </div>
      </Card>
    </div>

    <!-- ============ Right: Entity Detail Editor ============ -->
    <div class="min-w-0 flex-1">
      <template v-if="editor.selectedEntity.value">
        <Tabs
          v-model:activeKey="editor.activeTab.value"
          size="small"
          type="card"
        >
          <Tabs.TabPane
            v-for="tab in tabItems"
            :key="tab.key"
            :tab="tab.label"
          >
            <template #tab>
              <span class="flex items-center gap-1">
                <span :class="tab.icon" class="size-3.5" />
                {{ tab.label }}
              </span>
            </template>
          </Tabs.TabPane>
        </Tabs>

        <div class="mt-2">
          <!-- Basic Info Tab -->
          <div v-if="editor.activeTab.value === 'basic'" class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="mb-1 block text-sm text-muted-foreground">
                  {{ $t('admin.dev.crudGenerator.basicInfo.module') }}
                </label>
                <Input
                  :value="editor.selectedEntity.value.module"
                  disabled
                  size="small"
                />
              </div>
              <div>
                <label class="mb-1 block text-sm text-muted-foreground">
                  {{ $t('admin.dev.crudGenerator.basicInfo.tableName') }}
                </label>
                <Input
                  v-model:value="editor.selectedEntity.value.table_name"
                  size="small"
                  @change="onBasicFieldChange('table_name')"
                />
              </div>
              <div>
                <label class="mb-1 block text-sm text-muted-foreground">
                  {{ $t('admin.dev.crudGenerator.basicInfo.displayName') }}
                </label>
                <Input
                  v-model:value="editor.selectedEntity.value.display_name"
                  size="small"
                  @change="onBasicFieldChange('display_name')"
                />
              </div>
              <div>
                <label class="mb-1 block text-sm text-muted-foreground">
                  {{ $t('admin.dev.crudGenerator.basicInfo.displayNameEn') }}
                </label>
                <Input
                  v-model:value="editor.selectedEntity.value.display_name_en"
                  size="small"
                  @change="onBasicFieldChange('display_name_en')"
                />
              </div>
              <div>
                <label class="mb-1 block text-sm text-muted-foreground">
                  {{ $t('admin.dev.crudGenerator.basicInfo.scope') }}
                </label>
                <Select
                  v-model:value="editor.selectedEntity.value.scope"
                  :options="[
                    { value: 'admin', label: $t('admin.dev.crudGenerator.basicInfo.scopeAdmin') },
                    { value: 'tenant', label: $t('admin.dev.crudGenerator.basicInfo.scopeTenant') },
                    { value: 'both', label: $t('admin.dev.crudGenerator.basicInfo.scopeBoth') },
                  ]"
                  class="w-full"
                  size="small"
                  @change="onBasicFieldChange('scope')"
                />
              </div>
              <div>
                <label class="mb-1 block text-sm text-muted-foreground">
                  {{ $t('admin.dev.crudGenerator.basicInfo.parentMenu') }}
                </label>
                <Input
                  v-model:value="editor.selectedEntity.value.parent_menu"
                  size="small"
                  @change="onBasicFieldChange('parent_menu')"
                />
              </div>
            </div>

            <div>
              <label class="mb-1 block text-sm text-muted-foreground">
                {{ $t('admin.dev.crudGenerator.basicInfo.description') }}
              </label>
              <Input.TextArea
                v-model:value="editor.selectedEntity.value.description"
                :rows="2"
                size="small"
                @change="onBasicFieldChange('description')"
              />
            </div>

            <div class="flex flex-wrap gap-4">
              <label class="flex items-center gap-2 text-sm">
                <Switch
                  v-model:checked="editor.selectedEntity.value.soft_delete"
                  size="small"
                  @change="onBasicFieldChange('soft_delete')"
                />
                {{ $t('admin.dev.crudGenerator.basicInfo.softDelete') }}
              </label>
              <label class="flex items-center gap-2 text-sm">
                <Switch
                  v-model:checked="editor.selectedEntity.value.drag_sort"
                  size="small"
                  @change="onBasicFieldChange('drag_sort')"
                />
                {{ $t('admin.dev.crudGenerator.basicInfo.dragSort') }}
              </label>
              <label class="flex items-center gap-2 text-sm">
                <Switch
                  v-model:checked="editor.selectedEntity.value.has_status_toggle"
                  size="small"
                  @change="onBasicFieldChange('has_status_toggle')"
                />
                {{ $t('admin.dev.crudGenerator.basicInfo.statusToggle') }}
              </label>
              <label class="flex items-center gap-2 text-sm">
                <Switch
                  v-model:checked="editor.selectedEntity.value.recyclable"
                  size="small"
                  @change="onBasicFieldChange('recyclable')"
                />
                {{ $t('admin.dev.crudGenerator.basicInfo.recyclable') }}
              </label>
            </div>
          </div>

          <!-- Fields Tab -->
          <BatchFieldsEditor
            v-else-if="editor.activeTab.value === 'fields'"
            :entity="editor.selectedEntity.value"
            @touched="(path: string) => editor.markTouched(editor.selectedModule.value, path)"
          />

          <!-- Relations Tab -->
          <BatchRelationsEditor
            v-else-if="editor.activeTab.value === 'relations'"
            :entity="editor.selectedEntity.value"
            :entity-modules="editor.entityModules.value"
            @touched="(path: string) => editor.markTouched(editor.selectedModule.value, path)"
          />

          <!-- Enums Tab -->
          <BatchEnumsEditor
            v-else-if="editor.activeTab.value === 'enums'"
            :entity="editor.selectedEntity.value"
            @touched="(path: string) => editor.markTouched(editor.selectedModule.value, path)"
          />

          <!-- Indexes Tab -->
          <BatchIndexesEditor
            v-else-if="editor.activeTab.value === 'indexes'"
            :entity="editor.selectedEntity.value"
            @touched="(path: string) => editor.markTouched(editor.selectedModule.value, path)"
          />
        </div>
      </template>

      <!-- No entity selected -->
      <div v-else class="flex h-64 items-center justify-center">
        <Empty :description="$t(`${T}.noEntities`)">
          <Button type="primary" @click="openNewEntityDialog">
            <template #icon>
              <span class="icon-[lucide--plus] size-4" />
            </template>
            {{ $t(`${T}.addEntity`) }}
          </Button>
        </Empty>
      </div>

      <!-- ============ Template Panel ============ -->
      <div v-if="showTemplates" class="mt-4">
        <TemplatePanel
          :editor="editor"
          :template-manager="templateManager"
          @close="showTemplates = false"
        />
      </div>

      <!-- ============ ER Diagram ============ -->
      <div v-if="showErDiagram" class="mt-4">
        <ErDiagram
          :editor="editor"
          @select-entity="(m: string) => editor.selectEntity(m)"
        />
      </div>

      <!-- ============ Preview / Generation ============ -->
      <div v-if="showPreview" class="mt-4">
        <BatchGenerationPreview
          :preview="batchPreview"
          :summary="batchSummary"
          :is-generating="isGenerating"
          @confirm="onConfirmGenerate"
          @confirm-partial="onConfirmPartial"
          @update-strategy="onUpdateStrategy"
          @apply-all-strategy="onApplyAllStrategy"
          @jump-to-entity="(entity: string) => editor.selectEntity(entity)"
        />
      </div>

      <!-- Toggle buttons -->
      <div class="mt-4 flex justify-end gap-2">
        <Button
          :type="showTemplates ? 'primary' : 'default'"
          size="small"
          @click="showTemplates = !showTemplates"
        >
          <template #icon>
            <span class="icon-[lucide--layout-template] size-3.5" />
          </template>
          {{ $t('admin.dev.crudGenerator.templates.title') }}
        </Button>
        <Button
          :type="showErDiagram ? 'primary' : 'default'"
          size="small"
          @click="showErDiagram = !showErDiagram"
        >
          <template #icon>
            <span class="icon-[lucide--git-fork] size-3.5" />
          </template>
          {{ $t('admin.dev.crudGenerator.erDiagram.title') }}
        </Button>
        <Button
          :type="showPreview ? 'primary' : 'default'"
          size="small"
          @click="showPreview = !showPreview"
        >
          <template #icon>
            <span :class="showPreview ? 'icon-[lucide--eye-off]' : 'icon-[lucide--eye]'" class="size-3.5" />
          </template>
          {{ $t('admin.dev.crudGenerator.batchGeneration.preview') }}
        </Button>
      </div>

      <!-- ============ Cross-Relations Section ============ -->
      <Card size="small" class="mt-4">
        <template #title>
          <div class="flex items-center gap-2">
            <span class="icon-[lucide--git-branch] size-4" />
            <span class="text-sm font-medium">{{ $t(`${T}.crossRelations`) }}</span>
            <Badge :count="editor.crossRelations.value.length" />
          </div>
        </template>

        <div v-if="editor.crossRelations.value.length > 0" class="space-y-2">
          <div
            v-for="(rel, idx) in editor.crossRelations.value"
            :key="idx"
            class="flex items-center gap-2 rounded-md bg-accent/50 px-3 py-2"
          >
            <Tag color="blue">{{ rel.source_entity }}</Tag>
            <span class="text-xs text-muted-foreground">→</span>
            <Tag>{{ rel.relation_type }}</Tag>
            <span class="text-xs text-muted-foreground">→</span>
            <Tag color="green">{{ rel.target_entity }}</Tag>
            <span v-if="rel.foreign_key" class="text-xs text-muted-foreground">
              ({{ rel.foreign_key }})
            </span>
            <div class="flex-1" />
            <Button
              danger
              size="small"
              type="text"
              @click="editor.removeCrossRelation(idx)"
            >
              <template #icon>
                <span class="icon-[lucide--x] size-3.5" />
              </template>
            </Button>
          </div>
        </div>
        <Empty
          v-else
          :description="$t(`${T}.noCrossRelations`)"
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
        />

        <!-- Add cross-relation -->
        <div
          v-if="editor.entityModules.value.length >= 2"
          class="mt-3 flex items-center gap-2 border-t pt-3"
        >
          <Select
            v-model:value="newCrossRelation.source_entity"
            :options="editor.entityModules.value.map((m: string) => ({ value: m, label: m }))"
            :placeholder="$t(`${T}.sourceEntity`)"
            class="w-32"
            size="small"
          />
          <Select
            v-model:value="newCrossRelation.relation_type"
            :options="relationTypeOptions"
            class="w-28"
            size="small"
          />
          <Select
            v-model:value="newCrossRelation.target_entity"
            :options="editor.entityModules.value.map((m: string) => ({ value: m, label: m }))"
            :placeholder="$t(`${T}.targetEntity`)"
            class="w-32"
            size="small"
          />
          <Input
            v-model:value="newCrossRelation.foreign_key"
            :placeholder="$t(`${T}.foreignKey`)"
            class="w-32"
            size="small"
          />
          <Button size="small" type="primary" @click="addCrossRelation">
            <template #icon>
              <span class="icon-[lucide--plus] size-3.5" />
            </template>
          </Button>
        </div>
      </Card>
    </div>

    <!-- ============ TouchedPaths Panel ============ -->
    <TouchedPathsPanel
      v-if="showTouchedPaths && editor.selectedModule.value"
      :entity-module="editor.selectedModule.value"
      :locked-paths="editor.getLockedPaths(editor.selectedModule.value)"
      @close="showTouchedPaths = false"
      @unlock="(path: string) => editor.unlockPath(editor.selectedModule.value, path)"
      @unlock-all="editor.unlockAllPaths(editor.selectedModule.value)"
    />

    <!-- ============ New Entity Dialog ============ -->
    <Modal
      v-model:open="showNewEntityDialog"
      :title="$t(`${T}.newEntity.title`)"
      @ok="confirmNewEntity"
    >
      <div class="space-y-4 py-2">
        <div>
          <label class="mb-1 block text-sm">{{ $t(`${T}.newEntity.module`) }}</label>
          <Input
            v-model:value="newEntityModule"
            :placeholder="$t(`${T}.newEntity.modulePlaceholder`)"
          />
        </div>
        <div>
          <label class="mb-1 block text-sm">{{ $t(`${T}.newEntity.displayName`) }}</label>
          <Input
            v-model:value="newEntityDisplayName"
            :placeholder="$t(`${T}.newEntity.displayNamePlaceholder`)"
          />
        </div>
      </div>
    </Modal>

    <!-- ============ Clone Entity Dialog ============ -->
    <Modal
      v-model:open="showCloneDialog"
      :title="$t(`${CT}.title`)"
      @ok="confirmClone"
    >
      <div class="space-y-4 py-2">
        <!-- Source -->
        <div>
          <label class="mb-1 block text-sm">{{ $t(`${CT}.sourceEntity`) }}</label>
          <div class="rounded-md bg-accent/50 px-3 py-1.5 font-mono text-sm">
            {{ cloneSource }}
          </div>
        </div>

        <!-- New module -->
        <div>
          <label class="mb-1 block text-sm">{{ $t(`${CT}.newModule`) }}</label>
          <Input
            v-model:value="cloneModule"
            :placeholder="$t(`${CT}.newModulePlaceholder`)"
            :status="cloneError === 'module_exists' ? 'error' : undefined"
          />
          <div v-if="cloneError === 'module_exists'" class="mt-1 text-xs text-destructive">
            {{ $t(`${CT}.moduleExists`) }}
          </div>
        </div>

        <!-- New table name -->
        <div>
          <label class="mb-1 block text-sm">{{ $t(`${CT}.newTableName`) }}</label>
          <Input
            v-model:value="cloneTableName"
            :placeholder="$t(`${CT}.newTableNamePlaceholder`)"
            :status="cloneError === 'table_exists' ? 'error' : undefined"
          />
          <div v-if="cloneError === 'table_exists'" class="mt-1 text-xs text-destructive">
            {{ $t(`${CT}.tableExists`) }}
          </div>
        </div>

        <!-- Display names -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="mb-1 block text-sm">{{ $t(`${CT}.newDisplayName`) }}</label>
            <Input
              v-model:value="cloneDisplayName"
              :placeholder="$t(`${CT}.newDisplayNamePlaceholder`)"
            />
          </div>
          <div>
            <label class="mb-1 block text-sm">{{ $t(`${CT}.newDisplayNameEn`) }}</label>
            <Input
              v-model:value="cloneDisplayNameEn"
              :placeholder="$t(`${CT}.newDisplayNameEnPlaceholder`)"
            />
          </div>
        </div>

        <!-- Copy scope -->
        <div>
          <label class="mb-2 block text-sm font-medium">{{ $t(`${CT}.copyScope`) }}</label>
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-sm">{{ $t(`${CT}.includeRelations`) }}</span>
              <Switch v-model:checked="cloneIncludeRelations" size="small" />
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm">{{ $t(`${CT}.includeEnums`) }}</span>
              <Switch v-model:checked="cloneIncludeEnums" size="small" />
            </div>
            <div class="flex items-center justify-between">
              <div>
                <span class="text-sm">{{ $t(`${CT}.includeCrossRelations`) }}</span>
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${CT}.crossRelationHint`) }}
                </div>
              </div>
              <Switch v-model:checked="cloneIncludeCrossRelations" size="small" />
            </div>
          </div>
        </div>
      </div>
    </Modal>
  </div>
</template>
