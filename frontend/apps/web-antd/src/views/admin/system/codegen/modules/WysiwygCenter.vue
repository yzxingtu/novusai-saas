<script lang="ts" setup>
import type { PaletteItem } from './ComponentPalette.vue';

import { computed, onMounted, ref } from 'vue';

import { Segmented } from 'ant-design-vue';

import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import { createFieldFromPalette, ensureFieldKeys } from './field-utils';
import FieldCardList from './FieldCardList.vue';
import WysiwygDetailView from './WysiwygDetailView.vue';
import WysiwygFormView from './WysiwygFormView.vue';
import WysiwygListView from './WysiwygListView.vue';

defineOptions({ name: 'WysiwygCenter' });

type WorkspaceMode = 'detail' | 'fields' | 'form' | 'list';

const store = useCodegenBuilderStore();
const fieldCardListRef = ref<InstanceType<typeof FieldCardList> | null>(null);
const isDragOver = ref(false);
let dragEnterCount = 0;

const fields = computed(() => {
  const arr = (store.configJson.fields as Record<string, unknown>[]) || [];
  return ensureFieldKeys(arr);
});

const selectedFieldName = computed(() => {
  const selected = fields.value.find(
    (field) =>
      field.__key === store.selectedFieldKey ||
      field.name === store.selectedFieldKey,
  );
  return String(selected?.display_name || selected?.name || '').trim();
});
const endpointOptions = computed(() => {
  const endpoints =
    (store.configJson.endpoints as Array<Record<string, unknown>>) || [];
  return endpoints.map((endpoint, index) => ({
    label: $t(`admin.system.codegen.enum.${String(endpoint.scope || 'admin')}`),
    value: index,
  }));
});
const activeEndpointIdx = computed({
  get: () => store.activeEndpointIdx,
  set: (value: number) => {
    store.activeEndpointIdx = value;
  },
});

const workspaceMode = computed<WorkspaceMode>({
  get: () => (store.showFieldManager ? 'fields' : store.wysiwygViewMode),
  set: (value) => {
    if (value === 'fields') {
      store.showFieldManager = true;
      return;
    }
    store.showFieldManager = false;
    store.wysiwygViewMode = value;
  },
});

const workspaceMeta = computed(() => {
  const mode = workspaceMode.value;
  if (mode === 'fields')
    return { title: $t('admin.system.codegen.wysiwyg.fieldsView') };
  if (mode === 'form')
    return { title: $t('admin.system.codegen.wysiwyg.formView') };
  if (mode === 'detail')
    return { title: $t('admin.system.codegen.wysiwyg.detailView') };
  return { title: $t('admin.system.codegen.wysiwyg.listView') };
});

const showWorkspaceSummary = computed(() => workspaceMode.value !== 'fields');

function onDrop(event: DragEvent) {
  dragEnterCount = 0;
  isDragOver.value = false;
  event.preventDefault();
  const raw = event.dataTransfer?.getData('application/json');
  if (!raw) return;
  try {
    const item = JSON.parse(raw) as PaletteItem;
    if (!item?.type || !item?.component) {
      console.warn('[WysiwygCenter] onDrop: invalid PaletteItem', item);
      return;
    }
    const newField = createFieldFromPalette(item, fields.value);
    store.updateConfig({ fields: [...fields.value, newField] });
    store.selectedFieldKey = newField.__key as string;
  } catch (error) {
    console.warn('[WysiwygCenter] onDrop failed', error);
  }
}

function onDragEnter(event: DragEvent) {
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
  dragEnterCount += 1;
  isDragOver.value = true;
}

function onDragOver(event: DragEvent) {
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
}

function onDragLeave(event: DragEvent) {
  const current = event.currentTarget as HTMLElement;
  const related = event.relatedTarget as Node | null;
  if (related && current.contains(related)) return;
  dragEnterCount -= 1;
  if (dragEnterCount <= 0) {
    dragEnterCount = 0;
    isDragOver.value = false;
  }
}

function addFromPalette(item: PaletteItem) {
  if (store.showFieldManager) {
    fieldCardListRef.value?.addFromPalette(item);
    return;
  }
  const newField = createFieldFromPalette(item, fields.value);
  store.updateConfig({ fields: [...fields.value, newField] });
  store.selectedFieldKey = newField.__key as string;
}

defineExpose({ addFromPalette });

onMounted(() => {
  if (!store.selectedFieldKey) {
    store.showFieldManager = true;
  }
});
</script>

<template>
  <div
    class="flex min-h-[620px] min-w-80 flex-1 flex-col overflow-hidden rounded-[18px] bg-background transition-all"
    :class="[isDragOver && 'ring-2 ring-primary/50 ring-offset-2']"
    @dragenter="onDragEnter"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div class="border-b border-border px-3 py-2">
      <div class="flex flex-col gap-2">
        <div
          class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"
        >
          <div v-if="showWorkspaceSummary" class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-semibold text-foreground">
                {{ workspaceMeta.title }}
              </span>
              <span
                class="rounded-full bg-muted px-2.5 py-0.5 text-[11px] text-muted-foreground"
              >
                {{
                  $t('admin.system.codegen.fieldConfig.fieldCount', {
                    count: fields.length,
                  })
                }}
              </span>
              <span
                v-if="selectedFieldName"
                class="max-w-full truncate rounded-full border border-primary/20 bg-primary/5 px-2.5 py-0.5 text-[11px] text-primary"
              >
                {{ selectedFieldName }}
              </span>
            </div>
          </div>

          <div class="w-full xl:w-auto xl:min-w-[320px]">
            <div class="flex flex-col gap-2">
              <Segmented
                v-model:value="workspaceMode"
                block
                :options="[
                  {
                    label: $t('admin.system.codegen.wysiwyg.fieldsView'),
                    value: 'fields',
                  },
                  {
                    label: $t('admin.system.codegen.wysiwyg.listView'),
                    value: 'list',
                  },
                  {
                    label: $t('admin.system.codegen.wysiwyg.formView'),
                    value: 'form',
                  },
                  {
                    label: $t('admin.system.codegen.wysiwyg.detailView'),
                    value: 'detail',
                  },
                ]"
                size="small"
              />
              <Segmented
                v-if="endpointOptions.length > 1"
                v-model:value="activeEndpointIdx"
                block
                :options="endpointOptions"
                size="small"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto bg-muted/10 p-2">
      <FieldCardList
        v-if="workspaceMode === 'fields'"
        ref="fieldCardListRef"
        class="min-h-full"
      />

      <div v-else class="min-h-full">
        <WysiwygListView v-show="store.wysiwygViewMode === 'list'" />
        <WysiwygFormView v-show="store.wysiwygViewMode === 'form'" />
        <WysiwygDetailView v-show="store.wysiwygViewMode === 'detail'" />
      </div>
    </div>
  </div>
</template>
