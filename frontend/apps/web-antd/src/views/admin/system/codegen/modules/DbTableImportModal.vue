<script lang="ts" setup>
/**
 * 从数据库表导入配置 / Import config from DB table
 *
 * 表选择 -> 列勾选 -> 导入（表/列注释、全选、搜索、后缀推断）
 */
import type { ColumnInfo, TableInfo } from '#/api/admin/codegen';

import { computed, ref, watch } from 'vue';

import { Button, Checkbox, Input, Modal, Radio, RadioGroup, Select, Spin } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';

import {
  getCodegenDbColumnsApi,
  getCodegenDbTablesApi,
  postCodegenDbImportApi,
} from '#/api/admin/codegen';
import { $t } from '#/locales';
import { message } from 'ant-design-vue';

import { SYSTEM_FIELDS, inferFieldConfigForMerge, parseCommentEnum, singularize } from './infer';

defineOptions({ name: 'DbTableImportModal' });

interface ImportPatch extends Record<string, unknown> {
  display_name?: string;
  fields?: Record<string, unknown>[];
  resource?: string;
}

const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:open', v: boolean): void;
  (e: 'applied', patch: Record<string, unknown>): void;
}>();

const openModel = computed({
  get: () => props.open,
  set: (v) => emit('update:open', v),
});

const tables = ref<TableInfo[]>([]);
const columns = ref<ColumnInfo[]>([]);
const selectedTable = ref<string | undefined>(undefined);
const selectedColumns = ref<Set<string>>(new Set());
const columnSearch = ref('');
const importMode = ref<'replace' | 'merge'>('replace');
const loading = ref(false);
const importing = ref(false);

const BASE_FIELDS = new Set([
  'id',
  'created_at',
  'updated_at',
  'is_deleted',
  'deleted_at',
  'remark',
  'sort_order',
  'tenant_id',
  'created_by',
  'updated_by',
  'dept_id',
  'version',
  ...Object.keys(SYSTEM_FIELDS),
]);

const isBaseField = (name: string) => BASE_FIELDS.has(name);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

const filteredColumns = computed(() => {
  const list = columns.value;
  const q = (columnSearch.value || '').trim().toLowerCase();
  if (!q) return list;
  return list.filter(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      (c.comment || '').toLowerCase().includes(q) ||
      (c.type || '').toLowerCase().includes(q),
  );
});

const tableOptions = computed(() =>
  tables.value.map((t) => ({
    label: t.comment ? `${t.name} — ${t.comment}` : t.name,
    value: t.name,
  })),
);

function selectAllColumns() {
  const next = new Set(columns.value.filter((c) => !isBaseField(c.name)).map((c) => c.name));
  selectedColumns.value = next;
}

function deselectAllColumns() {
  selectedColumns.value = new Set();
}

async function loadTables() {
  loading.value = true;
  try {
    tables.value = await getCodegenDbTablesApi();
  } catch (e) {
    tables.value = [];
    message.error($t('admin.system.codegen.dbImport.loadTablesError'));
    console.error(e);
  } finally {
    loading.value = false;
  }
}

async function loadColumns(tableName: string) {
  loading.value = true;
  try {
    columns.value = await getCodegenDbColumnsApi(tableName);
    selectedColumns.value = new Set(
      columns.value.filter((c) => !isBaseField(c.name)).map((c) => c.name),
    );
  } catch (e) {
    columns.value = [];
    selectedColumns.value = new Set();
    selectedTable.value = undefined;
    message.error($t('admin.system.codegen.dbImport.loadColumnsError'));
    console.error(e);
  } finally {
    loading.value = false;
  }
}

function toggleColumn(name: string, checked: boolean) {
  const next = new Set(selectedColumns.value);
  if (checked) next.add(name);
  else next.delete(name);
  selectedColumns.value = next;
}

function parseTypeLength(typeStr: string): { max_length?: number; precision?: number; scale?: number } {
  const s = (typeStr || '').toUpperCase();
  const mVar = s.match(/VARCHAR\s*\(\s*(\d+)\s*\)/);
  if (mVar?.[1]) return { max_length: parseInt(mVar[1], 10) };
  const mDec = s.match(/DECIMAL\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)|NUMERIC\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)/);
  if (mDec) {
    const precisionText = mDec[1] || mDec[3];
    const scaleText = mDec[2] || mDec[4];
    if (!precisionText || !scaleText) return {};
    const p = parseInt(precisionText, 10);
    const sc = parseInt(scaleText, 10);
    return { precision: p, scale: sc };
  }
  return {};
}

function enhanceFieldFromColumn(f: Record<string, unknown>, col: ColumnInfo | undefined): Record<string, unknown> {
  const inferred = inferFieldConfigForMerge((f.name as string) || '');
  let merged: Record<string, unknown> = { ...inferred, ...f };
  if (col) {
    if (col.comment) {
      const parsed = parseCommentEnum(col.comment);
      if (parsed) {
        merged.enum_values = parsed;
      } else {
        const simpleLabel = col.comment.split(/[:：(]/)[0]?.trim() ?? '';
        if (simpleLabel) merged.display_name = simpleLabel;
      }
    }
    const typeExt = parseTypeLength(col.type || '');
    if (typeExt.max_length) merged.max_length = typeExt.max_length;
    if (typeExt.precision != null) merged.precision = typeExt.precision;
    if (typeExt.scale != null) merged.scale = typeExt.scale;
  }
  merged.__key = merged.__key || `f_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
  return merged;
}

async function doImport() {
  if (!selectedTable.value || selectedColumns.value.size === 0) return;
  importing.value = true;
  try {
    const full = await postCodegenDbImportApi({ table_name: selectedTable.value });
    const rawPatch = isRecord(full.data) ? full.data : full;
    const patch: ImportPatch = isRecord(rawPatch) ? (rawPatch as ImportPatch) : {};
    let fields = Array.isArray(patch.fields) ? patch.fields : [];
    fields = fields.filter((f) => selectedColumns.value.has((f.name as string) || ''));
    const colMap = new Map(columns.value.map((c) => [c.name, c]));
    const tableName = selectedTable.value;
    const resource =
      (typeof patch.resource === 'string' ? patch.resource : '') ||
      singularize(tableName.replace(/^t_/, ''));
    const tableComment = tables.value.find((t) => t.name === tableName)?.comment;
    const enhanced = fields.map((f) => enhanceFieldFromColumn(f, colMap.get((f.name as string) || '')));
    const seen = new Set<string>();
    const enhancedFields = enhanced.filter((f) => {
      const n = (f.name as string) || '';
      if (seen.has(n)) return false;
      seen.add(n);
      return true;
    });
    emit('applied', {
      ...patch,
      resource,
      display_name:
        tableComment ||
        (typeof patch.display_name === 'string' ? patch.display_name : '') ||
        resource,
      fields: enhancedFields,
      _importMode: importMode.value,
    });
    message.success($t('admin.system.codegen.dbImport.importSuccess'));
    openModel.value = false;
  } catch (e) {
    message.error($t('admin.system.codegen.dbImport.importError'));
    console.error(e);
  } finally {
    importing.value = false;
  }
}

function handleCancel() {
  openModel.value = false;
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      loadTables();
      selectedTable.value = undefined;
      columns.value = [];
      selectedColumns.value = new Set();
    }
  },
);

watch(selectedTable, (v) => {
  if (v) loadColumns(v);
  else {
    columns.value = [];
    selectedColumns.value = new Set();
  }
});
</script>

<template>
  <Modal
    v-model:open="openModel"
    :title="$t('admin.system.codegen.dbImport.title')"
    width="520"
    :footer="null"
    @cancel="handleCancel"
  >
    <div class="flex flex-col gap-4">
      <div>
        <span class="text-muted-foreground mr-2 text-sm">
          {{ $t('admin.system.codegen.dbImport.selectTable') }}
        </span>
        <Select
          v-model:value="selectedTable"
          :options="tableOptions"
          :placeholder="$t('admin.system.codegen.dbImport.placeholder.table')"
          allow-clear
          class="!w-64"
          show-search
        />
      </div>

      <Spin :spinning="loading">
        <div
          v-if="!selectedTable"
          class="flex min-h-24 flex-col items-center justify-center rounded border border-dashed border-border p-6 text-muted-foreground"
        >
          <IconifyIcon icon="lucide:database" class="mb-2 size-8" />
          <p class="text-sm">{{ $t('admin.system.codegen.dbImport.selectTableFirst') }}</p>
        </div>
        <div
          v-else
          class="rounded border border-border p-3"
        >
          <div class="mb-2 flex items-center justify-between gap-2">
            <span class="text-muted-foreground text-xs">
              {{ $t('admin.system.codegen.dbImport.selectColumns') }}
            </span>
            <div class="flex gap-1">
              <Button size="small" @click="selectAllColumns">
                {{ $t('admin.system.codegen.dbImport.selectAll') }}
              </Button>
              <Button size="small" @click="deselectAllColumns">
                {{ $t('admin.system.codegen.dbImport.deselectAll') }}
              </Button>
            </div>
          </div>
          <Input
            v-if="columns.length > 8"
            v-model:value="columnSearch"
            :placeholder="$t('admin.system.codegen.dbImport.searchColumns')"
            allow-clear
            class="mb-2"
            size="small"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:search" class="size-4 text-muted-foreground" />
            </template>
          </Input>
          <div class="max-h-64 overflow-y-auto">
            <Checkbox.Group class="flex flex-col gap-1">
              <Checkbox
                v-for="col in filteredColumns"
                :key="col.name"
                :checked="selectedColumns.has(col.name)"
                :disabled="isBaseField(col.name)"
                class="!font-mono !text-xs"
                @change="() => toggleColumn(col.name, !selectedColumns.has(col.name))"
              >
                <span :class="{ 'text-muted-foreground': isBaseField(col.name) }">
                  {{ col.name }} ({{ col.type }})
                  <span v-if="col.comment" class="text-muted-foreground"> — {{ col.comment }}</span>
                </span>
              </Checkbox>
            </Checkbox.Group>
          </div>
        </div>
      </Spin>

      <div class="flex flex-col gap-2">
        <div class="flex items-center gap-2">
          <span class="text-muted-foreground shrink-0 text-sm">
            {{ $t('admin.system.codegen.dbImport.importMode') }}:
          </span>
          <RadioGroup v-model:value="importMode" size="small">
            <Radio value="replace">{{ $t('admin.system.codegen.dbImport.modeReplace') }}</Radio>
            <Radio value="merge">{{ $t('admin.system.codegen.dbImport.modeMerge') }}</Radio>
          </RadioGroup>
        </div>
      </div>

      <div class="flex justify-end gap-2">
        <Button @click="handleCancel">
          {{ $t('common.cancel') }}
        </Button>
        <Button
          type="primary"
          :disabled="!selectedTable || loading || selectedColumns.size === 0"
          :loading="importing"
          @click="doImport"
        >
          {{ $t('admin.system.codegen.dbImport.import') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>
