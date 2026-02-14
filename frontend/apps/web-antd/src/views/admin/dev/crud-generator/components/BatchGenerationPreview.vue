<script setup lang="ts">
import { computed, ref } from 'vue';

import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Collapse,
  Empty,
  Radio,
  Result,
  Select,
  Table,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type {
  BatchPreviewResult,
  BatchWriteSummary,
  ConflictStrategy,
  WritePlanItem,
} from '../types';

import FileDiffViewer from './FileDiffViewer.vue';

const props = defineProps<{
  preview: BatchPreviewResult | null;
  summary: BatchWriteSummary | null;
  isGenerating: boolean;
}>();

const emit = defineEmits<{
  confirm: [];
  'confirm-partial': [entities: string[]];
  'update-strategy': [path: string, strategy: ConflictStrategy];
  'apply-all-strategy': [strategy: ConflictStrategy];
  'jump-to-entity': [entity: string];
}>();

const T = 'admin.dev.crudGenerator.batchGeneration';
const PT = 'admin.dev.crudGenerator.previewEnhanced';
const CB = 'admin.dev.crudGenerator.conflictBatch';

// ---- Default strategy preference (localStorage) ----
const PREF_KEY = 'novusai_conflict_strategy_prefs';

interface StrategyPreferences {
  byKind: Record<string, ConflictStrategy>;
  defaultStrategy: ConflictStrategy;
}

function loadPreferences(): StrategyPreferences {
  try {
    const raw = localStorage.getItem(PREF_KEY);
    if (raw) return JSON.parse(raw) as StrategyPreferences;
  } catch { /* ignore */ }
  return { byKind: {}, defaultStrategy: 'overwrite' };
}

function savePreferences(prefs: StrategyPreferences) {
  localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
}

const strategyPrefs = ref<StrategyPreferences>(loadPreferences());

function setDefaultStrategy(strategy: ConflictStrategy) {
  strategyPrefs.value.defaultStrategy = strategy;
  savePreferences(strategyPrefs.value);
}

function setKindPreference(kind: string, strategy: ConflictStrategy) {
  strategyPrefs.value.byKind[kind] = strategy;
  savePreferences(strategyPrefs.value);
}

function resetPreferences() {
  strategyPrefs.value = { byKind: {}, defaultStrategy: 'overwrite' };
  localStorage.removeItem(PREF_KEY);
}

// ---- Conflict statistics (real-time) ----
const conflictStats = computed(() => {
  if (!props.preview) return { total: 0, skip: 0, overwrite: 0, merge: 0, patch: 0 };
  const allFiles = [
    ...props.preview.entityGroups.flatMap((g) => g.files),
    ...props.preview.sharedFiles,
  ];
  const conflicts = allFiles.filter((f) => f.isConflict);
  return {
    total: conflicts.length,
    skip: conflicts.filter((f) => f.action === 'skip').length,
    overwrite: conflicts.filter((f) => f.action === 'overwrite').length,
    merge: conflicts.filter((f) => f.action === 'merge').length,
    patch: conflicts.filter((f) => f.action === 'patch').length,
  };
});

// ---- Scoped batch operations ----
function applyStrategyToEntity(entity: string, strategy: ConflictStrategy) {
  if (!props.preview) return;
  const group = props.preview.entityGroups.find((g) => g.entity === entity);
  if (!group) return;
  for (const file of group.files) {
    if (file.isConflict) {
      emit('update-strategy', file.path, strategy);
    }
  }
}

function applyStrategyToShared(strategy: ConflictStrategy) {
  if (!props.preview) return;
  for (const file of props.preview.sharedFiles) {
    if (file.isConflict) {
      emit('update-strategy', file.path, strategy);
    }
  }
}

function applyStrategyByKind(kind: string, strategy: ConflictStrategy) {
  if (!props.preview) return;
  const allFiles = [
    ...props.preview.entityGroups.flatMap((g) => g.files),
    ...props.preview.sharedFiles,
  ];
  for (const file of allFiles) {
    if (file.isConflict && file.kind === kind) {
      emit('update-strategy', file.path, strategy);
    }
  }
  setKindPreference(kind, strategy);
}

function resetAllStrategies() {
  if (!props.preview) return;
  const defaultStrat = strategyPrefs.value.defaultStrategy;
  const allFiles = [
    ...props.preview.entityGroups.flatMap((g) => g.files),
    ...props.preview.sharedFiles,
  ];
  for (const file of allFiles) {
    if (file.isConflict) {
      const kindPref = strategyPrefs.value.byKind[file.kind];
      emit('update-strategy', file.path, kindPref ?? defaultStrat);
    }
  }
}

const isConfirmed = computed(() => !!props.summary);

// ---- Kind batch target for two-step kind+strategy selection ----
const kindBatchTarget = ref('');

// ---- Active entity navigation ----
const activeEntity = ref<string>('');

function selectEntity(entity: string) {
  activeEntity.value = entity;
  emit('jump-to-entity', entity);
}

const activeFiles = computed<WritePlanItem[]>(() => {
  if (!props.preview) return [];
  if (activeEntity.value === '__shared__') {
    return props.preview.sharedFiles;
  }
  const group = props.preview.entityGroups.find(
    (g) => g.entity === activeEntity.value,
  );
  return group?.files ?? [];
});

// ---- File filter mode ----
type FilterMode = 'all' | 'conflicts' | 'changed' | 'shared';
const filterMode = ref<FilterMode>('all');
const kindFilter = ref<string>('');

const displayedFiles = computed(() => {
  let files = activeFiles.value;
  switch (filterMode.value) {
    case 'conflicts': {
      files = files.filter((f) => f.isConflict);
      break;
    }
    case 'changed': {
      files = files.filter((f) => f.action !== 'skip');
      break;
    }
    case 'shared': {
      files = files.filter((f) => f.kind === 'shared');
      break;
    }
  }
  if (kindFilter.value) {
    files = files.filter((f) => f.kind === kindFilter.value);
  }
  return files;
});

const filterOptions = computed(() => [
  { value: 'all', label: $t(`${PT}.filterAll`) },
  { value: 'conflicts', label: $t(`${PT}.filterConflicts`) },
  { value: 'changed', label: $t(`${PT}.filterChanged`) },
  { value: 'shared', label: $t(`${PT}.filterShared`) },
]);

const kindOptions = computed(() => [
  { value: '', label: $t(`${PT}.filterAll`) },
  { value: 'backend', label: $t(`${T}.kindBackend`) },
  { value: 'frontend', label: $t(`${T}.kindFrontend`) },
  { value: 'i18n', label: $t(`${T}.kindI18n`) },
  { value: 'migration', label: $t(`${T}.kindMigration`) },
  { value: 'test', label: $t(`${T}.kindTest`) },
  { value: 'shared', label: $t(`${T}.kindShared`) },
]);

// ---- Diff viewer state ----
const diffFile = ref<WritePlanItem | null>(null);
const diffExisting = ref('');
const diffGenerated = ref('');

function openDiff(file: WritePlanItem) {
  diffFile.value = file;
  // In real integration, existing/generated content comes from backend preview API
  diffExisting.value = file.isConflict ? `// existing content of ${file.path}` : '';
  diffGenerated.value = `// generated content for ${file.path}\n// entity: ${file.entity}\n// kind: ${file.kind}`;
}

function closeDiff() {
  diffFile.value = null;
}

// ---- Partial generation: entity selection ----
const showPartialSelect = ref(false);
const selectedEntities = ref<string[]>([]);

function toggleEntitySelection(entity: string) {
  const idx = selectedEntities.value.indexOf(entity);
  if (idx >= 0) {
    selectedEntities.value.splice(idx, 1);
  } else {
    selectedEntities.value.push(entity);
  }
}

function selectAllEntities() {
  if (!props.preview) return;
  selectedEntities.value = props.preview.entityGroups.map((g) => g.entity);
}

function deselectAllEntities() {
  selectedEntities.value = [];
}

function confirmPartial() {
  emit('confirm-partial', [...selectedEntities.value]);
}

// ---- Strategy options ----
const strategyOptions = computed(() => [
  { value: 'skip', label: $t(`${T}.strategySkip`) },
  { value: 'overwrite', label: $t(`${T}.strategyOverwrite`) },
  { value: 'merge', label: $t(`${T}.strategyMerge`) },
  { value: 'patch', label: $t(`${T}.strategyPatch`) },
]);

// ---- Kind tag colors ----
function kindColor(kind: string): string {
  const map: Record<string, string> = {
    backend: 'blue',
    frontend: 'green',
    i18n: 'purple',
    migration: 'orange',
    test: 'cyan',
    shared: 'gold',
  };
  return map[kind] ?? 'default';
}

function actionColor(action: string): string {
  const map: Record<string, string> = {
    create: 'green',
    overwrite: 'orange',
    merge: 'blue',
    skip: 'default',
    patch: 'purple',
  };
  return map[action] ?? 'default';
}

// ---- Table columns ----
const fileColumns = [
  { title: $t(`${T}.fileTree`), dataIndex: 'path', ellipsis: true },
  {
    title: $t(`${T}.conflictStrategy`),
    dataIndex: 'action',
    width: 120,
    align: 'center' as const,
  },
  { title: '', dataIndex: 'kind', width: 80, align: 'center' as const },
];

// ---- Summary helpers ----
const summaryStatus = computed(() => {
  if (!props.summary) return 'info';
  if (props.summary.totalErrors > 0 && props.summary.totalWritten === 0)
    return 'error';
  if (props.summary.totalErrors > 0) return 'warning';
  return 'success';
});

const summaryTitle = computed(() => {
  if (!props.summary) return '';
  const s = props.summary;
  if (s.totalErrors > 0 && s.totalWritten === 0)
    return $t(`${T}.summary.failed`);
  if (s.totalErrors > 0) return $t(`${T}.summary.partial`);
  return $t(`${T}.summary.success`);
});
</script>

<template>
  <div class="flex gap-4">
    <!-- ============ Left: Entity Navigation ============ -->
    <div class="w-52 shrink-0">
      <Card size="small">
        <template #title>
          <span class="text-sm font-medium">{{ $t(`${T}.entityNav`) }}</span>
        </template>

        <div v-if="preview" class="space-y-1">
          <!-- Entity groups -->
          <div
            v-for="group in preview.entityGroups"
            :key="group.entity"
            class="flex cursor-pointer items-center justify-between rounded-md px-2 py-1.5 transition-colors hover:bg-accent"
            :class="{ 'bg-primary/10 text-primary': activeEntity === group.entity }"
            @click="selectEntity(group.entity)"
          >
            <div class="flex min-w-0 flex-col">
              <span class="truncate text-sm">{{ group.displayName }}</span>
              <span class="text-xs text-muted-foreground">
                {{ group.files.length }} {{ $t(`${T}.fileTree`).toLowerCase() }}
              </span>
            </div>
            <div class="flex items-center gap-1">
              <Badge
                v-if="group.conflictCount > 0"
                :count="group.conflictCount"
                :number-style="{ backgroundColor: 'var(--ant-color-warning)' }"
                size="small"
              />
              <Badge
                v-if="group.errorCount > 0"
                :count="group.errorCount"
                :number-style="{ backgroundColor: 'var(--ant-color-error)' }"
                size="small"
              />
            </div>
          </div>

          <!-- Shared files -->
          <div
            v-if="preview.sharedFiles.length > 0"
            class="mt-2 flex cursor-pointer items-center justify-between rounded-md border-t px-2 py-1.5 transition-colors hover:bg-accent"
            :class="{ 'bg-primary/10 text-primary': activeEntity === '__shared__' }"
            @click="selectEntity('__shared__')"
          >
            <div class="flex items-center gap-1.5">
              <span class="icon-[lucide--share-2] size-3.5" />
              <span class="text-sm">{{ $t(`${T}.sharedFiles`) }}</span>
            </div>
            <Badge
              :count="preview.sharedFiles.length"
              :number-style="{ backgroundColor: 'var(--ant-color-primary)' }"
              size="small"
            />
          </div>

          <!-- Stats -->
          <div class="mt-3 space-y-1 border-t pt-2 text-xs text-muted-foreground">
            <div>{{ $t(`${T}.totalFiles`, { count: preview.totalFiles }) }}</div>
            <div v-if="preview.totalConflicts > 0" class="text-warning">
              {{ $t(`${T}.totalConflicts`, { count: preview.totalConflicts }) }}
            </div>
            <div v-else class="text-success">
              {{ $t(`${T}.noConflicts`) }}
            </div>
          </div>
        </div>

        <Empty v-else :description="$t(`${T}.noFiles`)" />
      </Card>
    </div>

    <!-- ============ Right: Preview / Conflicts / Summary ============ -->
    <div class="min-w-0 flex-1 space-y-4">
      <!-- Fallback hint -->
      <Alert
        v-if="preview && preview.entityGroups.length === 0 && preview.sharedFiles.length > 0"
        :message="$t(`${T}.fallbackHint`)"
        show-icon
        type="info"
      />

      <!-- Issues -->
      <Alert
        v-if="preview && preview.issues.length > 0"
        :message="`${preview.issues.filter((i) => i.severity === 'error').length} errors, ${preview.issues.filter((i) => i.severity === 'warning').length} warnings`"
        show-icon
        type="warning"
      >
        <template #description>
          <Collapse :bordered="false" size="small">
            <Collapse.Panel key="issues" header="Details">
              <div
                v-for="(issue, idx) in preview.issues"
                :key="idx"
                class="flex items-center gap-2 py-0.5 text-xs"
              >
                <span
                  :class="issue.severity === 'error' ? 'icon-[lucide--x-circle] text-destructive' : 'icon-[lucide--alert-triangle] text-warning'"
                  class="size-3.5 shrink-0"
                />
                <span class="font-mono">{{ issue.entityModule }}.{{ issue.path }}</span>
                <span>{{ issue.message }}</span>
              </div>
            </Collapse.Panel>
          </Collapse>
        </template>
      </Alert>

      <!-- ============ Conflict Batch Operations ============ -->
      <Card v-if="preview && conflictStats.total > 0 && !isConfirmed" size="small">
        <template #title>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="icon-[lucide--shield-alert] size-4 text-warning" />
              <span class="text-sm font-medium">{{ $t(`${CB}.title`) }}</span>
              <Tag color="warning" size="small">
                {{ $t(`${CB}.conflictStats`, { total: conflictStats.total }) }}
              </Tag>
            </div>
            <div class="flex items-center gap-1 text-xs text-muted-foreground">
              <span v-if="conflictStats.skip > 0">{{ $t(`${CB}.skipCount`, { count: conflictStats.skip }) }}</span>
              <span v-if="conflictStats.overwrite > 0" class="text-warning">{{ $t(`${CB}.overwriteCount`, { count: conflictStats.overwrite }) }}</span>
              <span v-if="conflictStats.merge > 0" class="text-primary">{{ $t(`${CB}.mergeCount`, { count: conflictStats.merge }) }}</span>
              <span v-if="conflictStats.patch > 0" class="text-purple-500">{{ $t(`${CB}.patchCount`, { count: conflictStats.patch }) }}</span>
            </div>
          </div>
        </template>

        <div class="flex flex-wrap items-center gap-2">
          <!-- Apply to current entity -->
          <div v-if="activeEntity && activeEntity !== '__shared__'" class="flex items-center gap-1">
            <span class="text-xs text-muted-foreground">{{ $t(`${CB}.applyToEntity`) }}:</span>
            <Select
              :options="strategyOptions"
              :placeholder="$t(`${T}.conflictStrategy`)"
              class="w-24"
              size="small"
              @change="(val: unknown) => applyStrategyToEntity(activeEntity, val as ConflictStrategy)"
            />
          </div>

          <!-- Apply to shared -->
          <div v-if="preview.sharedFiles.some((f) => f.isConflict)" class="flex items-center gap-1">
            <span class="text-xs text-muted-foreground">{{ $t(`${CB}.applyToShared`) }}:</span>
            <Select
              :options="strategyOptions"
              :placeholder="$t(`${T}.conflictStrategy`)"
              class="w-24"
              size="small"
              @change="(val: unknown) => applyStrategyToShared(val as ConflictStrategy)"
            />
          </div>

          <!-- Apply by kind -->
          <div class="flex items-center gap-1">
            <span class="text-xs text-muted-foreground">{{ $t(`${CB}.applyByKind`) }}:</span>
            <Select
              :options="kindOptions"
              :placeholder="$t(`${PT}.filterByKind`)"
              class="w-24"
              size="small"
              @change="(val: unknown) => { if (val) kindBatchTarget = val as string; }"
            />
            <Select
              v-if="kindBatchTarget"
              :options="strategyOptions"
              :placeholder="$t(`${T}.conflictStrategy`)"
              class="w-24"
              size="small"
              @change="(val: unknown) => { applyStrategyByKind(kindBatchTarget, val as ConflictStrategy); kindBatchTarget = ''; }"
            />
          </div>

          <div class="flex-1" />

          <!-- Default strategy -->
          <div class="flex items-center gap-1">
            <span class="text-xs text-muted-foreground">{{ $t(`${CB}.defaultStrategy`) }}:</span>
            <Select
              :options="strategyOptions"
              :value="strategyPrefs.defaultStrategy"
              class="w-24"
              size="small"
              @change="(val: unknown) => setDefaultStrategy(val as ConflictStrategy)"
            />
          </div>

          <!-- Reset -->
          <Tooltip :title="$t(`${CB}.resetAll`)">
            <Button size="small" type="text" @click="resetAllStrategies">
              <template #icon>
                <span class="icon-[lucide--rotate-ccw] size-3.5" />
              </template>
            </Button>
          </Tooltip>

          <!-- Reset preferences -->
          <Tooltip :title="$t(`${CB}.preferenceReset`)">
            <Button size="small" type="text" @click="resetPreferences">
              <template #icon>
                <span class="icon-[lucide--settings-2] size-3.5" />
              </template>
            </Button>
          </Tooltip>
        </div>
      </Card>

      <!-- File list for active entity -->
      <Card v-if="preview && activeEntity" size="small">
        <template #title>
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">{{ $t(`${T}.fileTree`) }}</span>
            <div class="flex items-center gap-2">
              <!-- Filter mode -->
              <Radio.Group
                :value="filterMode"
                size="small"
                @change="(e: unknown) => filterMode = ((e as { target: { value?: string } }).target.value ?? 'all') as FilterMode"
              >
                <Radio.Button
                  v-for="opt in filterOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </Radio.Button>
              </Radio.Group>
              <!-- Kind filter -->
              <Select
                v-model:value="kindFilter"
                :options="kindOptions"
                :placeholder="$t(`${PT}.filterByKind`)"
                class="w-24"
                size="small"
              />
              <!-- Batch strategy -->
              <Tooltip v-if="displayedFiles.some((f) => f.isConflict)" :title="$t(`${T}.conflictApplyAll`)">
                <Select
                  :options="strategyOptions"
                  :placeholder="$t(`${T}.conflictApplyAll`)"
                  class="w-28"
                  size="small"
                  @change="(val: unknown) => emit('apply-all-strategy', val as ConflictStrategy)"
                />
              </Tooltip>
            </div>
          </div>
        </template>

        <Table
          :columns="fileColumns"
          :custom-row="(record: WritePlanItem) => ({ onClick: () => openDiff(record) })"
          :data-source="displayedFiles"
          :pagination="false"
          :scroll="{ y: 400 }"
          bordered
          row-key="path"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'path'">
              <div class="flex cursor-pointer items-center gap-1.5 hover:text-primary">
                <span
                  :class="(record as WritePlanItem).isConflict
                    ? 'icon-[lucide--alert-triangle] text-warning'
                    : 'icon-[lucide--file] text-muted-foreground'"
                  class="size-3.5 shrink-0"
                />
                <span class="truncate font-mono text-xs">{{ (record as WritePlanItem).path }}</span>
              </div>
            </template>

            <template v-else-if="column.dataIndex === 'action'">
              <Select
                v-if="(record as WritePlanItem).isConflict"
                :options="strategyOptions"
                :value="(record as WritePlanItem).action"
                class="w-full"
                size="small"
                @change="(val: unknown) => emit('update-strategy', (record as WritePlanItem).path, val as ConflictStrategy)"
              />
              <Tag
                v-else
                :color="actionColor((record as WritePlanItem).action)"
                size="small"
              >
                {{ $t(`${T}.action${(record as WritePlanItem).action.charAt(0).toUpperCase() + (record as WritePlanItem).action.slice(1)}`) }}
              </Tag>
            </template>

            <template v-else-if="column.dataIndex === 'kind'">
              <Tag
                :color="kindColor((record as WritePlanItem).kind)"
                size="small"
              >
                {{ $t(`${T}.kind${(record as WritePlanItem).kind.charAt(0).toUpperCase() + (record as WritePlanItem).kind.slice(1)}`) }}
              </Tag>
            </template>
          </template>
        </Table>
      </Card>

      <!-- ============ Diff Viewer ============ -->
      <FileDiffViewer
        v-if="diffFile"
        :file="diffFile"
        :existing-content="diffExisting"
        :generated-content="diffGenerated"
        @close="closeDiff"
      />

      <!-- ============ Partial Generation ============ -->
      <Card v-if="preview && !summary && showPartialSelect" size="small">
        <template #title>
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">{{ $t(`${PT}.selectEntities`) }}</span>
            <div class="flex items-center gap-2">
              <Button size="small" type="link" @click="selectAllEntities">
                {{ $t(`${PT}.selectAll`) }}
              </Button>
              <Button size="small" type="link" @click="deselectAllEntities">
                {{ $t(`${PT}.deselectAll`) }}
              </Button>
            </div>
          </div>
        </template>
        <div class="space-y-1.5">
          <div
            v-for="group in preview.entityGroups"
            :key="group.entity"
            class="flex items-center gap-2"
          >
            <Checkbox
              :checked="selectedEntities.includes(group.entity)"
              @change="toggleEntitySelection(group.entity)"
            />
            <span class="text-sm">{{ group.displayName }}</span>
            <span class="text-xs text-muted-foreground">({{ group.files.length }})</span>
          </div>
        </div>
        <div class="mt-3 flex items-center justify-between border-t pt-3">
          <span class="text-sm text-muted-foreground">
            {{ $t(`${PT}.selectedCount`, { count: selectedEntities.length }) }}
          </span>
          <Button
            :disabled="selectedEntities.length === 0"
            :loading="isGenerating"
            type="primary"
            size="small"
            @click="confirmPartial"
          >
            {{ $t(`${PT}.generateSelected`) }}
          </Button>
        </div>
      </Card>

      <!-- Confirm buttons -->
      <div v-if="preview && !summary" class="flex items-center justify-between border-t pt-4">
        <div class="text-sm text-muted-foreground">
          {{ $t(`${T}.confirmHint`) }}
        </div>
        <div class="flex items-center gap-2">
          <Button
            size="small"
            @click="showPartialSelect = !showPartialSelect"
          >
            <template #icon>
              <span class="icon-[lucide--list-checks] size-3.5" />
            </template>
            {{ $t(`${PT}.partialGenerate`) }}
          </Button>
          <Button
            :loading="isGenerating"
            type="primary"
            @click="emit('confirm')"
          >
            <template #icon>
              <span class="icon-[lucide--play] size-4" />
            </template>
            {{ isGenerating ? $t(`${T}.generating`) : $t(`${T}.confirm`) }}
          </Button>
        </div>
      </div>

      <!-- ============ Generation Summary ============ -->
      <Card v-if="summary" size="small">
        <Result
          :status="summaryStatus"
          :title="summaryTitle"
          :sub-title="$t(`${T}.summary.duration`, { ms: summary.duration_ms })"
        >
          <template #extra>
            <div class="space-y-2 text-left">
              <!-- Global stats -->
              <div class="flex gap-4 text-sm">
                <span class="text-success">
                  {{ $t(`${T}.summary.totalWritten`, { count: summary.totalWritten }) }}
                </span>
                <span v-if="summary.totalSkipped > 0" class="text-muted-foreground">
                  {{ $t(`${T}.summary.totalSkipped`, { count: summary.totalSkipped }) }}
                </span>
                <span v-if="summary.totalErrors > 0" class="text-destructive">
                  {{ $t(`${T}.summary.totalErrors`, { count: summary.totalErrors }) }}
                </span>
              </div>

              <!-- Per-entity table -->
              <Table
                :columns="[
                  { title: $t(`${T}.summary.entity`), dataIndex: 'entity', width: 140 },
                  { title: $t(`${T}.summary.written`), dataIndex: 'written', width: 80, align: 'center' as const },
                  { title: $t(`${T}.summary.skipped`), dataIndex: 'skipped', width: 80, align: 'center' as const },
                  { title: $t(`${T}.summary.merged`), dataIndex: 'merged', width: 80, align: 'center' as const },
                  { title: $t(`${T}.summary.errors`), dataIndex: 'errors', width: 80, align: 'center' as const },
                ]"
                :data-source="summary.entities"
                :pagination="false"
                bordered
                row-key="entity"
                size="small"
              >
                <template #bodyCell="{ column, text }">
                  <template v-if="column.dataIndex === 'errors'">
                    <span :class="Number(text) > 0 ? 'text-destructive font-medium' : 'text-muted-foreground'">
                      {{ text }}
                    </span>
                  </template>
                  <template v-else-if="column.dataIndex === 'written'">
                    <span :class="Number(text) > 0 ? 'text-success' : 'text-muted-foreground'">
                      {{ text }}
                    </span>
                  </template>
                </template>
              </Table>

              <!-- Shared written -->
              <div v-if="summary.sharedWritten > 0" class="text-sm text-muted-foreground">
                {{ $t(`${T}.sharedFiles`) }}: {{ summary.sharedWritten }}
              </div>
            </div>
          </template>
        </Result>
      </Card>
    </div>
  </div>
</template>
