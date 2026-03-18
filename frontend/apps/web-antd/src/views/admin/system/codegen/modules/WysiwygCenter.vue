<script lang="ts" setup>
/**
 * WYSIWYG 中央预览主容器 / WYSIWYG Center Preview
 *
 * 列表页 | 新建表单 | 详情 三视图切换 + 字段管理入口
 */

import { computed, ref } from 'vue';
import { Button, Segmented } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';
import { createFieldFromPalette, ensureFieldKeys } from './field-utils';
import type { PaletteItem } from './ComponentPalette.vue';

import FieldCardList from './FieldCardList.vue';
import WysiwygDetailView from './WysiwygDetailView.vue';
import WysiwygFormView from './WysiwygFormView.vue';
import WysiwygListView from './WysiwygListView.vue';

defineOptions({ name: 'WysiwygCenter' });

const store = useCodegenBuilderStore();
const fieldCardListRef = ref<InstanceType<typeof FieldCardList> | null>(null);
const isDragOver = ref(false);
/** 防误触发：dragleave 在进入子元素时也会触发，用计数仅在完全离开时清除 */
let dragEnterCount = 0;

const fields = computed(() => {
  const arr = (store.configJson.fields as Record<string, unknown>[]) || [];
  return ensureFieldKeys(arr);
});

function onDrop(e: DragEvent) {
  dragEnterCount = 0;
  isDragOver.value = false;
  e.preventDefault();
  const raw = e.dataTransfer?.getData('application/json');
  if (!raw) return;
  try {
    const item = JSON.parse(raw) as PaletteItem;
    if (!item?.type || !item?.component) {
      console.warn('[WysiwygCenter] onDrop: invalid PaletteItem', item);
      return;
    }
    const newField = createFieldFromPalette(item, fields.value);
    const next = [...fields.value, newField];
    store.updateConfig({ fields: next });
    store.selectedFieldKey = newField.__key as string;
  } catch (err) {
    console.warn('[WysiwygCenter] onDrop failed', err);
  }
}

function onDragEnter(e: DragEvent) {
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
  dragEnterCount += 1;
  isDragOver.value = true;
}

function onDragOver(e: DragEvent) {
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
}

function onDragLeave(e: DragEvent) {
  const el = e.currentTarget as HTMLElement;
  const next = e.relatedTarget as Node | null;
  if (next && el.contains(next)) return;
  dragEnterCount -= 1;
  if (dragEnterCount <= 0) {
    dragEnterCount = 0;
    isDragOver.value = false;
  }
}

function toggleFieldManager() {
  store.showFieldManager = !store.showFieldManager;
}

function addFromPalette(item: PaletteItem) {
  if (store.showFieldManager) {
    fieldCardListRef.value?.addFromPalette(item);
  } else {
    const newField = createFieldFromPalette(item, fields.value);
    const next = [...fields.value, newField];
    store.updateConfig({ fields: next });
    store.selectedFieldKey = newField.__key as string;
  }
}

defineExpose({ addFromPalette });
</script>

<template>
  <div
    :class="['flex min-h-0 min-w-80 flex-1 flex-col overflow-hidden bg-muted/20 transition-all', isDragOver && 'ring-2 ring-primary/50 ring-offset-2']"
    @dragenter="onDragEnter"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <!-- 顶部：视图切换 + 字段管理 -->
    <div class="flex items-center justify-between border-b border-border px-3 py-2">
      <Segmented
        v-model:value="store.wysiwygViewMode"
        :options="[
          { label: $t('admin.system.codegen.wysiwyg.listView'), value: 'list' },
          { label: $t('admin.system.codegen.wysiwyg.formView'), value: 'form' },
          { label: $t('admin.system.codegen.wysiwyg.detailView'), value: 'detail' },
        ]"
        size="small"
      />
      <Button size="small" type="text" @click="toggleFieldManager">
        <IconifyIcon
          :icon="store.showFieldManager ? 'lucide:layout-grid' : 'lucide:list'"
          class="mr-1 size-4"
        />
        {{ store.showFieldManager ? $t('admin.system.codegen.wysiwyg.backToPreview') : $t('admin.system.codegen.wysiwyg.fieldManager') }}
      </Button>
    </div>

    <!-- 内容区 -->
    <div class="min-h-0 flex-1 overflow-y-auto p-4">
      <!-- 字段管理模式：覆盖展示 FieldCardList -->
      <FieldCardList
        v-if="store.showFieldManager"
        ref="fieldCardListRef"
        class="min-h-full"
      />

      <!-- WYSIWYG 预览：v-show 保留表单状态，避免切换时 formValues 丢失 -->
      <div v-else class="min-h-full">
        <WysiwygListView v-show="store.wysiwygViewMode === 'list'" />
        <WysiwygFormView v-show="store.wysiwygViewMode === 'form'" />
        <WysiwygDetailView v-show="store.wysiwygViewMode === 'detail'" />
      </div>
    </div>
  </div>
</template>
