<script lang="ts" setup>
import type { Recordable } from '@vben/types';

import type { PaletteItem } from './component-palette.types';

import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  shallowRef,
  watch,
} from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Checkbox } from 'ant-design-vue';
import Sortable from 'sortablejs';

import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import {
  createFieldFromPalette,
  ensureFieldKeys,
  ensureUniqueName,
  genKey,
  getComponent,
} from './field-utils';
import FieldCard from './FieldCard.vue';

defineOptions({ name: 'FieldCardList' });

const TABLE_VIEW_COLUMNS = 12;

type BatchToggleField =
  | 'editable'
  | 'filterable'
  | 'insertable'
  | 'list_visible'
  | 'required';

const store = useCodegenBuilderStore();
const listRef = ref<HTMLElement | null>(null);
const tableBodyRef = ref<HTMLElement | null>(null);
const viewMode = ref<'card' | 'table'>('table');
const sortableInstance = shallowRef<null | ReturnType<typeof Sortable.create>>(
  null,
);
const tableSortableInstance = shallowRef<null | ReturnType<
  typeof Sortable.create
>>(null);

const fields = computed<Recordable[]>({
  get: () => {
    const arr = (store.configJson.fields as Recordable[]) || [];
    return ensureFieldKeys(arr);
  },
  set: (value) => {
    store.updateConfig({ fields: ensureFieldKeys(value) });
  },
});

const dataFields = computed(() =>
  fields.value.filter(
    (field) => field.type !== '__divider__' && !field.divider,
  ),
);

const fieldCount = computed(() => dataFields.value.length);
const requiredCount = computed(
  () => dataFields.value.filter((field) => Boolean(field.required)).length,
);
const listVisibleCount = computed(
  () => dataFields.value.filter((field) => field.list_visible !== false).length,
);
const filterableCount = computed(
  () => dataFields.value.filter((field) => Boolean(field.filterable)).length,
);
const editableCount = computed(
  () => dataFields.value.filter((field) => field.editable !== false).length,
);

const summaryCards = computed(() => [
  {
    key: 'required',
    label: $t('admin.system.codegen.property.required'),
    value: requiredCount.value,
  },
  {
    key: 'visible',
    label: $t('admin.system.codegen.property.listVisible'),
    value: listVisibleCount.value,
  },
  {
    key: 'query',
    label: $t('admin.system.codegen.property.filterable'),
    value: filterableCount.value,
  },
  {
    key: 'edit',
    label: $t('admin.system.codegen.property.editable'),
    value: editableCount.value,
  },
]);

function isToggleFieldEnabled(
  field: Recordable,
  column: BatchToggleField,
): boolean {
  if (['editable', 'insertable', 'list_visible'].includes(column)) {
    return field[column] !== false;
  }
  return Boolean(field[column]);
}

function updateField(key: string, patch: Partial<Recordable>) {
  const normalizedPatch = { ...patch };
  if (patch.required === true) {
    normalizedPatch.nullable = false;
  }
  if (patch.nullable === true) {
    normalizedPatch.required = false;
  }
  fields.value = fields.value.map((field) =>
    field.__key === key ? { ...field, ...normalizedPatch } : field,
  );
}

function toggleBatch(column: BatchToggleField) {
  const arr = [...fields.value];
  const dataOnly = arr.filter(
    (field) => field.type !== '__divider__' && !field.divider,
  );
  if (dataOnly.length === 0) return;
  const count = dataOnly.filter((field) =>
    isToggleFieldEnabled(field, column),
  ).length;
  const nextValue = count < dataOnly.length;
  for (let index = 0; index < arr.length; index += 1) {
    const current = arr[index];
    if (!current || current.type === '__divider__' || current.divider) continue;
    const patch: Record<string, unknown> = { [column]: nextValue };
    if (column === 'required' && nextValue === true) {
      patch.nullable = false;
    }
    arr[index] = { ...current, ...patch };
  }
  fields.value = arr;
}

function isBatchAll(column: BatchToggleField): boolean {
  if (dataFields.value.length === 0) return false;
  return dataFields.value.every((field) => isToggleFieldEnabled(field, column));
}

function isBatchSome(column: BatchToggleField): boolean {
  if (dataFields.value.length === 0) return false;
  const count = dataFields.value.filter((field) =>
    isToggleFieldEnabled(field, column),
  ).length;
  return count > 0 && count < dataFields.value.length;
}

function createField(item: PaletteItem): Recordable {
  return createFieldFromPalette(item, fields.value);
}

function addFromPalette(item: PaletteItem) {
  const newField = createField(item);
  fields.value = [...fields.value, newField];
  store.selectedFieldKey = newField.__key as string;
}

function addEmptyField() {
  const baseName = `field_${Date.now()}`;
  const newField: Recordable = {
    __key: genKey(),
    editable: true,
    insertable: true,
    list_visible: true,
    name: ensureUniqueName(baseName, fields.value),
    type: 'String',
  };
  fields.value = [...fields.value, newField];
  store.selectedFieldKey = newField.__key as string;
}

function addDivider() {
  const divider = createFieldFromPalette(
    {
      component: 'divider',
      defaultName: '',
      icon: 'lucide:minus',
      label: 'admin.system.codegen.palette.divider',
      type: '__divider__',
    },
    fields.value,
  );
  fields.value = [...fields.value, divider];
  store.selectedFieldKey = divider.__key as string;
}

function removeField(key: string) {
  if (store.selectedFieldKey === key) {
    store.selectedFieldKey = null;
  }
  fields.value = fields.value.filter((field) => field.__key !== key);
}

function updateDividerTitle(key: string, title: string) {
  const next = [...fields.value];
  const index = next.findIndex((field) => field.__key === key);
  if (index === -1) return;
  next[index] = { ...next[index], divider_title: title, title };
  fields.value = next;
}

function selectField(key: string) {
  store.selectedFieldKey = key;
}

function getComponentName(field: Recordable): string {
  return getComponent(field);
}

function getQueryType(field: Recordable): string {
  const form = field.form as Record<string, unknown> | undefined;
  return (form?.queryType as string) || 'eq';
}

function onDrop(event: DragEvent) {
  event.preventDefault();
  const raw = event.dataTransfer?.getData('application/json');
  if (!raw) return;
  try {
    const item = JSON.parse(raw) as PaletteItem;
    if (!item?.type || !item?.component) {
      console.warn('[FieldCardList] onDrop: invalid PaletteItem', item);
      return;
    }
    const newField = createField(item);
    fields.value = [...fields.value, newField];
    store.selectedFieldKey = newField.__key as string;
  } catch (error) {
    console.warn('[FieldCardList] onDrop failed', error);
  }
}

function onDragOver(event: DragEvent) {
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
}

function initSortable() {
  destroySortable();

  if (viewMode.value === 'card' && listRef.value && fields.value.length > 0) {
    sortableInstance.value = Sortable.create(listRef.value, {
      animation: 150,
      ghostClass: 'opacity-50',
      handle: '.drag-handle',
      onEnd(event) {
        if (
          event.oldIndex === null ||
          event.oldIndex === undefined ||
          event.newIndex === null ||
          event.newIndex === undefined ||
          event.oldIndex === event.newIndex
        ) {
          return;
        }
        const next = [...fields.value];
        const removed = next.splice(event.oldIndex, 1)[0];
        if (!removed) return;
        next.splice(event.newIndex, 0, removed);
        fields.value = next.map((field, index) => ({
          ...field,
          sort_order: index,
        }));
      },
    });
    return;
  }

  if (
    viewMode.value === 'table' &&
    tableBodyRef.value &&
    fields.value.length > 0
  ) {
    tableSortableInstance.value = Sortable.create(tableBodyRef.value, {
      animation: 150,
      filter: '.codegen-divider-row',
      ghostClass: 'opacity-50',
      handle: '.table-drag-handle',
      onEnd(event) {
        if (
          event.oldIndex === null ||
          event.oldIndex === undefined ||
          event.newIndex === null ||
          event.newIndex === undefined ||
          event.oldIndex === event.newIndex
        ) {
          return;
        }
        const next = [...fields.value];
        const removed = next.splice(event.oldIndex, 1)[0];
        if (!removed) return;
        next.splice(event.newIndex, 0, removed);
        fields.value = next.map((field, index) => ({
          ...field,
          sort_order: index,
        }));
      },
    });
  }
}

function destroySortable() {
  sortableInstance.value?.destroy();
  sortableInstance.value = null;
  tableSortableInstance.value?.destroy();
  tableSortableInstance.value = null;
}

defineExpose({ addFromPalette });

onMounted(() => nextTick(initSortable));
watch(
  () => [fields.value.length, viewMode.value],
  () => nextTick(initSortable),
);
onUnmounted(destroySortable);
</script>

<template>
  <div
    class="flex min-w-80 flex-1 flex-col overflow-hidden rounded-[18px] border border-border bg-background shadow-sm"
  >
    <div class="border-b border-border px-3 py-2">
      <div
        class="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between"
      >
        <div class="flex min-w-0 flex-wrap items-center gap-1.5">
          <span
            class="rounded-full bg-muted px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground"
          >
            {{ $t('admin.system.codegen.builder.metricFields') }}
            {{ fieldCount }}
          </span>
          <span
            v-for="item in summaryCards"
            :key="item.key"
            class="rounded-full border border-border/70 bg-background px-2.5 py-0.5 text-[11px] text-muted-foreground"
          >
            {{ item.label }} {{ item.value }}
          </span>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <Button size="small" @click="addEmptyField">
            <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
            {{ $t('admin.system.codegen.fieldConfig.addEmptyField') }}
          </Button>
          <Button size="small" @click="addDivider">
            <IconifyIcon icon="lucide:minus" class="mr-1 size-4" />
            {{ $t('admin.system.codegen.palette.divider') }}
          </Button>
          <div class="flex items-center gap-1 rounded-full bg-muted p-0.5">
            <Button
              :type="viewMode === 'card' ? 'primary' : 'text'"
              size="small"
              class="!rounded-full"
              @click="viewMode = 'card'"
            >
              <IconifyIcon icon="lucide:layout-grid" class="mr-1 size-4" />
              {{ $t('admin.system.codegen.fieldConfig.cardView') }}
            </Button>
            <Button
              :type="viewMode === 'table' ? 'primary' : 'text'"
              size="small"
              class="!rounded-full"
              @click="viewMode = 'table'"
            >
              <IconifyIcon icon="lucide:table" class="mr-1 size-4" />
              {{ $t('admin.system.codegen.fieldConfig.tableView') }}
            </Button>
          </div>
        </div>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto bg-muted/10 p-2">
      <div
        v-if="viewMode === 'card'"
        class="min-h-full rounded-[18px] border border-dashed border-border/70 bg-background/90 p-2.5"
        @dragover="onDragOver"
        @drop="onDrop"
      >
        <div
          v-if="fields.length === 0"
          class="flex min-h-[180px] flex-col items-center justify-center rounded-[16px] border border-dashed border-border bg-muted/15 px-4 text-center"
        >
          <IconifyIcon
            icon="lucide:layers"
            class="size-8 text-muted-foreground"
          />
          <div class="mt-3 text-sm font-medium text-foreground">
            {{ $t('admin.system.codegen.builder.schemaEmptyTitle') }}
          </div>
          <div class="mt-1 max-w-md text-xs leading-5 text-muted-foreground">
            {{ $t('admin.system.codegen.builder.schemaEmptyDesc') }}
          </div>
          <div class="mt-4 flex flex-wrap gap-2">
            <Button type="primary" @click="addEmptyField">
              <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
              {{ $t('admin.system.codegen.fieldConfig.addEmptyField') }}
            </Button>
            <Button @click="addDivider">
              <IconifyIcon icon="lucide:minus" class="mr-1 size-4" />
              {{ $t('admin.system.codegen.palette.divider') }}
            </Button>
          </div>
        </div>

        <div v-else ref="listRef" class="flex flex-col gap-3">
          <FieldCard
            v-for="(field, index) in fields"
            :key="
              (field.__key as string) ||
              (field.name as string) ||
              `field-${index}`
            "
            :field="field"
            :selected="store.selectedFieldKey === field.__key"
            @click="selectField(field.__key as string)"
            @remove="removeField(field.__key as string)"
            @update:divider-title="
              updateDividerTitle(field.__key as string, $event)
            "
          />
        </div>
      </div>

      <div
        v-else
        class="min-h-full overflow-hidden rounded-[18px] border border-border/80 bg-background"
        @dragover="onDragOver"
        @drop="onDrop"
      >
        <div
          v-if="fields.length === 0"
          class="flex min-h-[180px] flex-col items-center justify-center px-4 text-center"
        >
          <IconifyIcon
            icon="lucide:layers"
            class="size-8 text-muted-foreground"
          />
          <div class="mt-3 text-sm font-medium text-foreground">
            {{ $t('admin.system.codegen.builder.schemaEmptyTitle') }}
          </div>
          <div class="mt-1 max-w-md text-xs leading-5 text-muted-foreground">
            {{ $t('admin.system.codegen.builder.schemaEmptyDesc') }}
          </div>
        </div>

        <div v-else class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="sticky top-0 z-10 bg-muted/40 backdrop-blur">
              <tr>
                <th class="w-10 px-3 py-3"></th>
                <th class="px-3 py-3 font-medium text-foreground">
                  {{ $t('admin.system.codegen.property.fieldName') }}
                </th>
                <th class="px-3 py-3 font-medium text-foreground">
                  {{ $t('admin.system.codegen.property.displayNameZh') }}
                </th>
                <th class="px-3 py-3 font-medium text-foreground">
                  {{ $t('admin.system.codegen.property.type') }}
                </th>
                <th class="px-3 py-3 font-medium text-foreground">
                  {{ $t('admin.system.codegen.property.component') }}
                </th>
                <th class="w-[96px] px-3 py-3 text-center">
                  <Checkbox
                    :checked="isBatchAll('required')"
                    :indeterminate="isBatchSome('required')"
                    @change="toggleBatch('required')"
                  />
                  <span class="ml-1 text-xs">{{
                    $t('admin.system.codegen.property.required')
                  }}</span>
                </th>
                <th class="w-[96px] px-3 py-3 text-center">
                  <Checkbox
                    :checked="isBatchAll('insertable')"
                    :indeterminate="isBatchSome('insertable')"
                    @change="toggleBatch('insertable')"
                  />
                  <span class="ml-1 text-xs">{{
                    $t('admin.system.codegen.property.insertable')
                  }}</span>
                </th>
                <th class="w-[96px] px-3 py-3 text-center">
                  <Checkbox
                    :checked="isBatchAll('editable')"
                    :indeterminate="isBatchSome('editable')"
                    @change="toggleBatch('editable')"
                  />
                  <span class="ml-1 text-xs">{{
                    $t('admin.system.codegen.property.editable')
                  }}</span>
                </th>
                <th class="w-[96px] px-3 py-3 text-center">
                  <Checkbox
                    :checked="isBatchAll('list_visible')"
                    :indeterminate="isBatchSome('list_visible')"
                    @change="toggleBatch('list_visible')"
                  />
                  <span class="ml-1 text-xs">{{
                    $t('admin.system.codegen.property.listVisible')
                  }}</span>
                </th>
                <th class="w-[96px] px-3 py-3 text-center">
                  <Checkbox
                    :checked="isBatchAll('filterable')"
                    :indeterminate="isBatchSome('filterable')"
                    @change="toggleBatch('filterable')"
                  />
                  <span class="ml-1 text-xs">{{
                    $t('admin.system.codegen.property.filterable')
                  }}</span>
                </th>
                <th class="px-3 py-3 font-medium text-foreground">
                  {{ $t('admin.system.codegen.property.queryType') }}
                </th>
                <th class="w-16 px-3 py-3"></th>
              </tr>
            </thead>
            <tbody ref="tableBodyRef">
              <tr
                v-for="(field, index) in fields"
                :key="
                  (field.__key as string) ||
                  (field.name as string) ||
                  `table-field-${index}`
                "
                class="border-t border-border/70 transition-colors hover:bg-muted/20"
                :class="{
                  'bg-primary/8': store.selectedFieldKey === field.__key,
                  'codegen-divider-row':
                    field.type === '__divider__' || field.divider,
                }"
                @click="
                  field.type !== '__divider__' &&
                  !field.divider &&
                  selectField(field.__key as string)
                "
              >
                <template v-if="field.type === '__divider__' || field.divider">
                  <td
                    :colspan="TABLE_VIEW_COLUMNS"
                    class="bg-muted/25 px-3 py-3"
                  >
                    <div
                      class="flex items-center gap-2 text-sm font-medium text-foreground"
                    >
                      <IconifyIcon
                        icon="lucide:minus"
                        class="size-4 text-muted-foreground"
                      />
                      <span>{{
                        field.divider_title ||
                        field.title ||
                        $t('admin.system.codegen.palette.divider')
                      }}</span>
                    </div>
                  </td>
                </template>

                <template v-else>
                  <td
                    class="table-drag-handle cursor-grab px-3 py-3 text-muted-foreground"
                  >
                    <IconifyIcon icon="lucide:grip-vertical" class="size-4" />
                  </td>
                  <td class="px-3 py-3 font-mono text-xs text-foreground">
                    {{ field.name || '-' }}
                  </td>
                  <td class="px-3 py-3 text-foreground">
                    {{ field.display_name || field.title || '-' }}
                  </td>
                  <td class="px-3 py-3 text-xs text-muted-foreground">
                    {{ field.type || '-' }}
                  </td>
                  <td class="px-3 py-3 text-xs text-muted-foreground">
                    {{ getComponentName(field) }}
                  </td>
                  <td class="px-3 py-3 text-center">
                    <Checkbox
                      :checked="Boolean(field.required)"
                      @click.stop
                      @change="
                        updateField(field.__key as string, {
                          required: !field.required,
                        })
                      "
                    />
                  </td>
                  <td class="px-3 py-3 text-center">
                    <Checkbox
                      :checked="field.insertable !== false"
                      @click.stop
                      @change="
                        updateField(field.__key as string, {
                          insertable: field.insertable === false,
                        })
                      "
                    />
                  </td>
                  <td class="px-3 py-3 text-center">
                    <Checkbox
                      :checked="field.editable !== false"
                      @click.stop
                      @change="
                        updateField(field.__key as string, {
                          editable: field.editable === false,
                        })
                      "
                    />
                  </td>
                  <td class="px-3 py-3 text-center">
                    <Checkbox
                      :checked="field.list_visible !== false"
                      @click.stop
                      @change="
                        updateField(field.__key as string, {
                          list_visible: field.list_visible === false,
                        })
                      "
                    />
                  </td>
                  <td class="px-3 py-3 text-center">
                    <Checkbox
                      :checked="Boolean(field.filterable)"
                      @click.stop
                      @change="
                        updateField(field.__key as string, {
                          filterable: !field.filterable,
                        })
                      "
                    />
                  </td>
                  <td class="px-3 py-3 text-xs text-muted-foreground">
                    {{ getQueryType(field) }}
                  </td>
                  <td class="px-3 py-3 text-right">
                    <Button
                      type="text"
                      size="small"
                      danger
                      class="!p-1"
                      @click.stop="removeField(field.__key as string)"
                    >
                      <IconifyIcon icon="lucide:trash-2" class="size-4" />
                    </Button>
                  </td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
