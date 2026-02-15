<script setup lang="ts">
/**
 * StepListConfig — Step 3: 列表配置
 *
 * 左侧: 列设置表格 (显示/隐藏、宽度、对齐、渲染预设、固定、排序) + 表格选项 + 操作列 + 搜索配置
 * 右侧: ListPreview 实时预览
 */
import { computed } from 'vue';

import {
  Card,
  Checkbox,
  Divider,
  Input,
  InputNumber,
  Select,
  Switch,
  Table,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, FieldConfig, SearchFieldConfig } from '../types';

import {
  getAlignOptions,
  getFixedOptions,
  getRenderPresetOptions,
  getSearchOperatorOptions,
  SEARCH_COMPONENT_OPTIONS,
} from '../constants';

import type { MockDataRow } from '../composables/use-mock-data';

import ListPreview from './ListPreview.vue';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
  mockData: MockDataRow[];
}>();

const emit = defineEmits<{
  (e: 'update:config', config: CrudConfig): void;
}>();

// ============================================================
// Column config helpers
// ============================================================

function updateField(name: string, key: keyof FieldConfig, value: unknown) {
  const fields = props.config.fields.map((f) => {
    if (f.name === name) {
      return { ...f, [key]: value };
    }
    return f;
  });
  emit('update:config', { ...props.config, fields });
}

function updateListConfig(key: string, value: unknown) {
  emit('update:config', {
    ...props.config,
    list_config: { ...props.config.list_config, [key]: value },
  });
}

function toggleOperation(op: string) {
  const ops = [...props.config.operations];
  const idx = ops.indexOf(op);
  if (idx >= 0) {
    ops.splice(idx, 1);
  } else {
    ops.push(op);
  }
  emit('update:config', { ...props.config, operations: ops });
}

// ============================================================
// Render preset options
// ============================================================

function getRenderPresetsWithNone() {
  return [
    { label: $t(`${T}.listConfig.renderPresetNone`), value: '' },
    ...getRenderPresetOptions(),
  ];
}

// ============================================================
// Column config table columns
// ============================================================

const columnConfigCols = computed(() => [
  { title: $t(`${T}.listConfig.columnName`), dataIndex: 'name', width: 100 },
  { title: $t(`${T}.listConfig.columnLabel`), dataIndex: 'label_zh', width: 100 },
  { title: $t(`${T}.listConfig.columnVisible`), dataIndex: 'in_list', width: 70, align: 'center' as const },
  { title: $t(`${T}.listConfig.columnWidth`), dataIndex: 'list_width', width: 80 },
  { title: $t(`${T}.listConfig.columnAlign`), dataIndex: 'list_align', width: 90 },
  { title: $t(`${T}.listConfig.renderPreset`), dataIndex: 'list_render', width: 130 },
  { title: $t(`${T}.listConfig.columnFixed`), dataIndex: 'list_fixed', width: 100 },
  { title: $t(`${T}.listConfig.columnSortable`), dataIndex: 'list_sortable', width: 70, align: 'center' as const },
]);

// ============================================================
// Search config helpers
// ============================================================

const SEARCH_COMPONENTS = SEARCH_COMPONENT_OPTIONS;

const searchFields = computed(() => {
  return props.config.search_config?.fields ?? [];
});

function addSearchField() {
  const searchable = props.config.fields.filter((f) => f.searchable);
  const existing = new Set(searchFields.value.map((sf) => sf.field));
  const next = searchable.find((f) => !existing.has(f.name));
  if (!next) return;

  const newField: SearchFieldConfig = {
    field: next.name,
    operator: next.search_op || 'ilike',
    component: 'Input',
    col_span: 6,
  };

  const fields = [...searchFields.value, newField];
  emit('update:config', {
    ...props.config,
    search_config: {
      ...props.config.search_config,
      fields,
      collapsed: props.config.search_config?.collapsed ?? false,
      max_visible: props.config.search_config?.max_visible ?? 3,
    },
  });
}

function removeSearchField(index: number) {
  const fields = [...searchFields.value];
  fields.splice(index, 1);
  emit('update:config', {
    ...props.config,
    search_config: {
      ...props.config.search_config,
      fields,
      collapsed: props.config.search_config?.collapsed ?? false,
      max_visible: props.config.search_config?.max_visible ?? 3,
    },
  });
}

function updateSearchField(index: number, key: keyof SearchFieldConfig, value: unknown) {
  const fields = searchFields.value.map((sf, i) => {
    if (i === index) {
      return { ...sf, [key]: value };
    }
    return sf;
  });
  emit('update:config', {
    ...props.config,
    search_config: {
      ...props.config.search_config,
      fields,
      collapsed: props.config.search_config?.collapsed ?? false,
      max_visible: props.config.search_config?.max_visible ?? 3,
    },
  });
}
</script>

<template>
  <div class="flex gap-4" style="min-height: 500px">
    <!-- Left: Config Panel -->
    <div class="w-[480px] flex-shrink-0 space-y-4 overflow-auto" style="max-height: 700px">
      <!-- Column Settings -->
      <Card :title="$t(`${T}.listConfig.columnSettings`)" size="small">
        <Table
          :columns="columnConfigCols"
          :data-source="config.fields"
          :pagination="false"
          :scroll="{ x: 740 }"
          bordered
          row-key="name"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'in_list'">
              <Checkbox
                :checked="(record as FieldConfig).in_list"
                @change="(e: { target: { checked: boolean } }) => updateField((record as FieldConfig).name, 'in_list', e.target.checked)"
              />
            </template>

            <template v-else-if="column.dataIndex === 'list_width'">
              <InputNumber
                :value="(record as FieldConfig).list_width ?? undefined"
                :min="40"
                :max="500"
                :step="10"
                :placeholder="$t(`${T}.listConfig.widthAuto`)"
                size="small"
                style="width: 70px"
                @change="(val: unknown) => updateField((record as FieldConfig).name, 'list_width', val)"
              />
            </template>

            <template v-else-if="column.dataIndex === 'list_align'">
              <Select
                :value="(record as FieldConfig).list_align || 'left'"
                :options="getAlignOptions()"
                size="small"
                style="width: 80px"
                @change="(val: unknown) => updateField((record as FieldConfig).name, 'list_align', val)"
              />
            </template>

            <template v-else-if="column.dataIndex === 'list_render'">
              <Select
                :value="(record as FieldConfig).list_render || ''"
                :options="getRenderPresetsWithNone()"
                size="small"
                style="width: 140px"
                @change="(val: unknown) => updateField((record as FieldConfig).name, 'list_render', val || null)"
              >
                <template #option="{ icon, label }">
                  <div class="flex items-center gap-1.5">
                    <span v-if="icon" :class="[icon, 'size-3.5 opacity-60']" />
                    <span>{{ label }}</span>
                  </div>
                </template>
              </Select>
            </template>

            <template v-else-if="column.dataIndex === 'list_fixed'">
              <Select
                :value="(record as FieldConfig).list_fixed || ''"
                :options="getFixedOptions()"
                size="small"
                style="width: 90px"
                @change="(val: unknown) => updateField((record as FieldConfig).name, 'list_fixed', val || null)"
              />
            </template>

            <template v-else-if="column.dataIndex === 'list_sortable'">
              <Checkbox
                :checked="(record as FieldConfig).list_sortable"
                @change="(e: { target: { checked: boolean } }) => updateField((record as FieldConfig).name, 'list_sortable', e.target.checked)"
              />
            </template>
          </template>
        </Table>
      </Card>

      <!-- Table Options -->
      <Card :title="$t(`${T}.listConfig.tableOptions`)" size="small">
        <div class="grid grid-cols-2 gap-3">
          <div class="flex items-center justify-between">
            <span class="text-sm">{{ $t(`${T}.listConfig.showCheckbox`) }}</span>
            <Switch
              :checked="config.list_config.show_checkbox"
              size="small"
              @change="(val: unknown) => updateListConfig('show_checkbox', val)"
            />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm">{{ $t(`${T}.listConfig.showIndex`) }}</span>
            <Switch
              :checked="config.list_config.show_index"
              size="small"
              @change="(val: unknown) => updateListConfig('show_index', val)"
            />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm">{{ $t(`${T}.listConfig.stripe`) }}</span>
            <Switch
              :checked="config.list_config.stripe"
              size="small"
              @change="(val: unknown) => updateListConfig('stripe', val)"
            />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm">{{ $t(`${T}.listConfig.pager`) }}</span>
            <Switch
              :checked="config.list_config.pager"
              size="small"
              @change="(val: unknown) => updateListConfig('pager', val)"
            />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm">{{ $t(`${T}.listConfig.toolbarSearch`) }}</span>
            <Switch
              :checked="config.list_config.toolbar_search"
              size="small"
              @change="(val: unknown) => updateListConfig('toolbar_search', val)"
            />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm">{{ $t(`${T}.listConfig.toolbarExport`) }}</span>
            <Switch
              :checked="config.list_config.toolbar_export"
              size="small"
              @change="(val: unknown) => updateListConfig('toolbar_export', val)"
            />
          </div>
        </div>

        <Divider class="!my-3" />

        <div class="flex items-center gap-2">
          <span class="text-sm whitespace-nowrap">{{ $t(`${T}.listConfig.defaultSort`) }}</span>
          <Input
            :value="config.list_config.default_sort"
            :placeholder="$t(`${T}.listConfig.defaultSortPlaceholder`)"
            size="small"
            @change="(e: Event) => updateListConfig('default_sort', (e.target as HTMLInputElement).value)"
          />
        </div>
      </Card>

      <!-- Operations Column -->
      <Card :title="$t(`${T}.listConfig.operationConfig`)" size="small">
        <div class="flex gap-4">
          <Checkbox
            :checked="config.operations.includes('edit')"
            @change="() => toggleOperation('edit')"
          >
            {{ $t(`${T}.listConfig.operationEdit`) }}
          </Checkbox>
          <Checkbox
            :checked="config.operations.includes('delete')"
            @change="() => toggleOperation('delete')"
          >
            {{ $t(`${T}.listConfig.operationDelete`) }}
          </Checkbox>
          <Checkbox
            :checked="config.operations.includes('view')"
            @change="() => toggleOperation('view')"
          >
            {{ $t(`${T}.listConfig.operationView`) }}
          </Checkbox>
        </div>
      </Card>

      <!-- Search Config -->
      <Card :title="$t(`${T}.listConfig.searchConfig`)" size="small">
        <div class="space-y-2">
          <div
            v-for="(sf, idx) in searchFields"
            :key="sf.field"
            class="flex items-center gap-2"
          >
            <span class="w-24 truncate text-sm">{{ sf.field }}</span>
            <Select
              :value="sf.operator"
              :options="getSearchOperatorOptions()"
              size="small"
              style="width: 90px"
              @change="(val: unknown) => updateSearchField(idx, 'operator', val)"
            />
            <Select
              :value="sf.component"
              :options="SEARCH_COMPONENTS"
              size="small"
              style="width: 110px"
              @change="(val: unknown) => updateSearchField(idx, 'component', val)"
            />
            <span
              class="icon-[lucide--x] text-muted-foreground size-4 cursor-pointer hover:text-red-500"
              @click="removeSearchField(idx)"
            />
          </div>

          <button
            class="text-primary mt-1 flex items-center gap-1 text-sm hover:underline"
            @click="addSearchField"
          >
            <span class="icon-[lucide--plus] size-3.5" />
            {{ $t(`${T}.listConfig.addSearchField`) }}
          </button>
        </div>
      </Card>
    </div>

    <!-- Right: Preview -->
    <div class="flex-1 overflow-auto">
      <Card :title="$t(`${T}.listPreview.title`)" size="small">
        <ListPreview :config="config" :data="mockData" />
      </Card>
    </div>
  </div>
</template>
