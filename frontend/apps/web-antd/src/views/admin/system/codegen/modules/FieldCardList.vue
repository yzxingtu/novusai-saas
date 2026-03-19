<script lang="ts" setup>
/**
 * 字段卡片列表 / Field Card List
 *
 * RuoYi 风格：卡片视图 + 表格视图，Sortable.js 拖拽排序 / Card + table view, Sortable.js drag sort
 */
import type { Recordable } from '@vben/types';

import Sortable from 'sortablejs';
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import { Button, Checkbox } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import type { PaletteItem } from './ComponentPalette.vue';
import {
  createFieldFromPalette,
  ensureFieldKeys,
  genKey,
  ensureUniqueName,
  getComponent,
} from './field-utils';
import FieldCard from './FieldCard.vue';

defineOptions({ name: 'FieldCardList' });

/** 表格视图列数，divider 行 colspan 与之对齐 / Table view column count for divider colspan */
const TABLE_VIEW_COLUMNS = 12;

const store = useCodegenBuilderStore();
const listRef = ref<HTMLElement | null>(null);
const tableBodyRef = ref<HTMLElement | null>(null);
const viewMode = ref<'card' | 'table'>('card');
const sortableInstance = shallowRef<ReturnType<typeof Sortable.create> | null>(null);
const tableSortableInstance = shallowRef<ReturnType<typeof Sortable.create> | null>(null);

type BatchToggleField =
  | 'editable'
  | 'filterable'
  | 'insertable'
  | 'list_visible'
  | 'required';

const fields = computed<Recordable[]>({
  get: () => {
    const arr = (store.configJson.fields as Recordable[]) || [];
    return ensureFieldKeys(arr);
  },
  set: (v) => {
    store.updateConfig({ fields: ensureFieldKeys(v) });
  },
});

const dataFields = computed(() =>
  fields.value.filter((f) => f.type !== '__divider__' && !f.divider),
);

const fieldCount = computed(() => dataFields.value.length);

function updateField(key: string, patch: Partial<Recordable>) {
  const arr = fields.value.map((f) => (f.__key === key ? { ...f, ...patch } : f));
  fields.value = arr;
}

function toggleBatch(col: BatchToggleField) {
  const arr = [...fields.value];
  const dataOnly = arr.filter((f) => f.type !== '__divider__' && !f.divider);
  if (dataOnly.length === 0) return;
  const count = dataOnly.filter((f) => Boolean(f[col])).length;
  const nextVal = count < dataOnly.length;
  for (let i = 0; i < arr.length; i++) {
    const current = arr[i];
    if (!current || current.type === '__divider__' || current.divider) continue;
    arr[i] = { ...current, [col]: nextVal };
  }
  fields.value = arr;
}

function isBatchAll(col: BatchToggleField): boolean {
  const dataOnly = dataFields.value;
  if (dataOnly.length === 0) return false;
  return dataOnly.every((f) => Boolean(f[col]));
}

function isBatchSome(col: BatchToggleField): boolean {
  const dataOnly = dataFields.value;
  if (dataOnly.length === 0) return false;
  const count = dataOnly.filter((f) => Boolean(f[col])).length;
  return count > 0 && count < dataOnly.length;
}

function createField(item: PaletteItem): Recordable {
  return createFieldFromPalette(item, fields.value);
}

function onDrop(e: DragEvent) {
  e.preventDefault();
  const raw = e.dataTransfer?.getData('application/json');
  if (!raw) return;
  try {
    const item = JSON.parse(raw) as PaletteItem;
    if (!item?.type || !item?.component) {
      console.warn('[FieldCardList] onDrop: invalid PaletteItem', item);
      return;
    }
    const newField = createField(item);
    const next = [...fields.value, newField];
    fields.value = next;
    store.selectedFieldKey = newField.__key as string;
  } catch (err) {
    console.warn('[FieldCardList] onDrop failed', err);
  }
}

function onDragOver(e: DragEvent) {
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
}

function addFromPalette(item: PaletteItem) {
  const newField = createField(item);
  const next = [...fields.value, newField];
  fields.value = next;
  store.selectedFieldKey = newField.__key as string;
}

defineExpose({ addFromPalette });

function addEmptyField() {
  const baseName = `field_${Date.now()}`;
  const newField: Recordable = {
    __key: genKey(),
    name: ensureUniqueName(baseName, fields.value),
    type: 'String',
    insertable: true,
    editable: true,
    list_visible: true,
  };
  const next = [...fields.value, newField];
  fields.value = next;
  store.selectedFieldKey = newField.__key as string;
}

function removeField(key: string) {
  const idx = fields.value.findIndex((f) => f.__key === key);
  if (idx < 0) return;
  if (store.selectedFieldKey === key) store.selectedFieldKey = null;
  const next = fields.value.filter((f) => f.__key !== key);
  fields.value = next;
}

function updateDividerTitle(key: string, title: string) {
  const arr = [...fields.value];
  const idx = arr.findIndex((f) => f.__key === key);
  if (idx >= 0) {
    arr[idx] = { ...arr[idx], divider_title: title, title };
    fields.value = arr;
  }
}

function selectField(key: string) {
  store.selectedFieldKey = key;
}

function getComponentName(f: Recordable): string {
  return getComponent(f);
}

function getQueryType(f: Recordable): string {
  const form = f.form as Record<string, unknown> | undefined;
  return (form?.queryType as string) || 'eq';
}

function initSortable() {
  destroySortable();
  if (viewMode.value === 'card' && listRef.value && fields.value.length > 0) {
    sortableInstance.value = Sortable.create(listRef.value, {
      animation: 150,
      handle: '.drag-handle',
      ghostClass: 'opacity-50',
      onEnd(evt) {
        if (evt.oldIndex == null || evt.newIndex == null || evt.oldIndex === evt.newIndex) return;
        const arr = [...fields.value];
        const removed = arr.splice(evt.oldIndex, 1)[0];
        if (!removed) return;
        arr.splice(evt.newIndex, 0, removed);
        fields.value = arr.map((f, i) => ({ ...f, sort_order: i }));
      },
    });
  } else if (viewMode.value === 'table' && tableBodyRef.value && fields.value.length > 0) {
    tableSortableInstance.value = Sortable.create(tableBodyRef.value, {
      animation: 150,
      handle: '.table-drag-handle',
      filter: '.codegen-divider-row',
      ghostClass: 'opacity-50',
      onEnd(evt) {
        if (evt.oldIndex == null || evt.newIndex == null || evt.oldIndex === evt.newIndex) return;
        const arr = [...fields.value];
        const removed = arr.splice(evt.oldIndex, 1)[0];
        if (!removed) return;
        arr.splice(evt.newIndex, 0, removed);
        fields.value = arr.map((f, i) => ({ ...f, sort_order: i }));
      },
    });
  }
}

function destroySortable() {
  if (sortableInstance.value) {
    sortableInstance.value.destroy();
    sortableInstance.value = null;
  }
  if (tableSortableInstance.value) {
    tableSortableInstance.value.destroy();
    tableSortableInstance.value = null;
  }
}

onMounted(() => nextTick(initSortable));
watch(
  () => [fields.value.length, viewMode.value],
  () => nextTick(initSortable),
);
onUnmounted(destroySortable);
</script>

<template>
  <div class="flex min-w-80 flex-1 flex-col overflow-y-auto">
    <!-- 顶部工具条 -->
    <div class="flex shrink-0 flex-col gap-1 border-b border-border px-3 py-2">
      <div class="flex items-center justify-between gap-2">
        <span class="text-muted-foreground text-sm">
          {{ $t('admin.system.codegen.fieldConfig.fieldCount', { count: fieldCount }) }}
        </span>
        <div class="flex gap-1">
          <Button
            :type="viewMode === 'card' ? 'primary' : 'default'"
            size="small"
            @click="viewMode = 'card'"
          >
            <IconifyIcon icon="lucide:layout-grid" class="mr-1 size-4" />
            {{ $t('admin.system.codegen.fieldConfig.cardView') }}
          </Button>
          <Button
            :type="viewMode === 'table' ? 'primary' : 'default'"
            size="small"
            @click="viewMode = 'table'"
          >
            <IconifyIcon icon="lucide:table" class="mr-1 size-4" />
            {{ $t('admin.system.codegen.fieldConfig.tableView') }}
          </Button>
        </div>
      </div>
      <p class="text-muted-foreground text-xs">{{ $t('admin.system.codegen.fieldConfig.systemFieldsHint') }}</p>
    </div>

    <!-- 卡片视图 -->
    <div
      v-if="viewMode === 'card'"
      class="min-h-32 flex-1 rounded-lg border-2 border-dashed border-border p-4 transition-colors"
      :class="fields.length === 0 ? 'flex flex-col items-center justify-center gap-2' : ''"
      @dragover="onDragOver"
      @drop="onDrop"
    >
      <template v-if="fields.length === 0">
        <IconifyIcon icon="lucide:layers" class="size-12 text-muted-foreground" />
        <p class="text-sm text-muted-foreground">{{ $t('admin.system.codegen.palette.dropHint') }}</p>
      </template>
      <div v-else ref="listRef" class="flex flex-col gap-2">
        <FieldCard
          v-for="(f, idx) in fields"
          :key="(f.__key as string) || (f.name as string) || `fld-${idx}`"
          :field="f"
          :selected="store.selectedFieldKey === f.__key"
          @click="selectField(f.__key as string)"
          @remove="removeField(f.__key as string)"
          @update:divider-title="updateDividerTitle(f.__key as string, $event)"
        />
      </div>
    </div>

    <!-- 表格视图 -->
    <div v-else class="flex-1 overflow-auto">
      <div
        v-if="fields.length === 0"
        class="flex min-h-32 flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border"
        @dragover="onDragOver"
        @drop="onDrop"
      >
        <IconifyIcon icon="lucide:layers" class="size-12 text-muted-foreground" />
        <p class="text-sm text-muted-foreground">{{ $t('admin.system.codegen.palette.dropHint') }}</p>
      </div>
      <div
        v-else
        class="min-h-32 border border-border"
        @dragover="onDragOver"
        @drop="onDrop"
      >
        <table class="w-full text-left text-sm">
          <thead class="bg-muted/50">
            <tr>
              <th class="w-8 px-2 py-1.5"></th>
              <th class="px-2 py-1.5 font-medium">{{ $t('admin.system.codegen.property.fieldName') }}</th>
              <th class="px-2 py-1.5 font-medium">{{ $t('admin.system.codegen.property.displayNameZh') }}</th>
              <th class="px-2 py-1.5 font-medium">{{ $t('admin.system.codegen.property.type') }}</th>
              <th class="px-2 py-1.5 font-medium">{{ $t('admin.system.codegen.property.component') }}</th>
              <th class="w-12 px-2 py-1.5 text-center">
                <Checkbox
                  :checked="isBatchAll('required')"
                  :indeterminate="isBatchSome('required')"
                  @change="toggleBatch('required')"
                />
                <span class="ml-1 text-xs">{{ $t('admin.system.codegen.property.required') }}</span>
              </th>
              <th class="w-12 px-2 py-1.5 text-center">
                <Checkbox
                  :checked="isBatchAll('insertable')"
                  :indeterminate="isBatchSome('insertable')"
                  @change="toggleBatch('insertable')"
                />
                <span class="ml-1 text-xs">{{ $t('admin.system.codegen.property.insertable') }}</span>
              </th>
              <th class="w-12 px-2 py-1.5 text-center">
                <Checkbox
                  :checked="isBatchAll('editable')"
                  :indeterminate="isBatchSome('editable')"
                  @change="toggleBatch('editable')"
                />
                <span class="ml-1 text-xs">{{ $t('admin.system.codegen.property.editable') }}</span>
              </th>
              <th class="w-12 px-2 py-1.5 text-center">
                <Checkbox
                  :checked="isBatchAll('list_visible')"
                  :indeterminate="isBatchSome('list_visible')"
                  @change="toggleBatch('list_visible')"
                />
                <span class="ml-1 text-xs">{{ $t('admin.system.codegen.property.listVisible') }}</span>
              </th>
              <th class="w-12 px-2 py-1.5 text-center">
                <Checkbox
                  :checked="isBatchAll('filterable')"
                  :indeterminate="isBatchSome('filterable')"
                  @change="toggleBatch('filterable')"
                />
                <span class="ml-1 text-xs">{{ $t('admin.system.codegen.property.filterable') }}</span>
              </th>
              <th class="px-2 py-1.5 font-medium">{{ $t('admin.system.codegen.property.queryType') }}</th>
              <th class="w-16 px-2 py-1.5"></th>
            </tr>
          </thead>
          <tbody ref="tableBodyRef">
            <tr
              v-for="(f, idx) in fields"
              :key="(f.__key as string) || (f.name as string) || `fld-${idx}`"
              class="border-t border-border transition-colors hover:bg-muted/30"
              :class="{
                'bg-primary/10': store.selectedFieldKey === f.__key,
                'codegen-divider-row': f.type === '__divider__' || f.divider,
              }"
              @click="(f.type !== '__divider__' && !f.divider) && selectField(f.__key as string)"
            >
              <template v-if="f.type === '__divider__' || f.divider">
                <td :colspan="TABLE_VIEW_COLUMNS" class="bg-muted/30 px-2 py-1 font-medium">
                  <span class="text-muted-foreground">—</span>
                  {{ f.divider_title || f.title || '' }}
                </td>
              </template>
              <template v-else>
                <td class="cursor-grab px-2 py-1 table-drag-handle">
                  <IconifyIcon icon="lucide:grip-vertical" class="size-4 text-muted-foreground" />
                </td>
                <td class="px-2 py-1 font-mono text-xs">{{ f.name || '-' }}</td>
                <td class="px-2 py-1">{{ f.display_name || f.title || '-' }}</td>
                <td class="px-2 py-1 text-xs">{{ f.type || '-' }}</td>
                <td class="px-2 py-1 text-xs">{{ getComponentName(f) }}</td>
                <td class="px-2 py-1 text-center">
                  <Checkbox :checked="!!f.required" @click.stop @change="updateField(f.__key as string, { required: !f.required })" />
                </td>
                <td class="px-2 py-1 text-center">
                  <Checkbox :checked="f.insertable !== false" @click.stop @change="updateField(f.__key as string, { insertable: f.insertable === false })" />
                </td>
                <td class="px-2 py-1 text-center">
                  <Checkbox :checked="f.editable !== false" @click.stop @change="updateField(f.__key as string, { editable: f.editable === false })" />
                </td>
                <td class="px-2 py-1 text-center">
                  <Checkbox :checked="!!f.list_visible" @click.stop @change="updateField(f.__key as string, { list_visible: !f.list_visible })" />
                </td>
                <td class="px-2 py-1 text-center">
                  <Checkbox :checked="!!f.filterable" @click.stop @change="updateField(f.__key as string, { filterable: !f.filterable })" />
                </td>
                <td class="px-2 py-1 text-xs">{{ getQueryType(f) }}</td>
                <td class="px-2 py-1">
                  <Button type="text" size="small" danger class="!p-1" @click.stop="removeField(f.__key as string)">
                    <IconifyIcon icon="lucide:trash-2" class="size-4" />
                  </Button>
                </td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="shrink-0 border-t border-border p-2">
      <Button block @click="addEmptyField">
        <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
        {{ $t('admin.system.codegen.fieldConfig.addEmptyField') }}
      </Button>
    </div>
  </div>
</template>
