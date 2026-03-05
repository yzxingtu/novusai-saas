<script lang="ts" setup>
import type { FormField, FormWidgetType, NccField, NccTableSchema } from '../types';

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import Sortable from 'sortablejs';
import {
  Button,
  Checkbox,
  CheckboxGroup,
  Collapse,
  CollapsePanel,
  DatePicker,
  Input,
  InputNumber,
  Radio,
  RadioGroup,
  Rate,
  Select,
  SelectOption,
  Slider,
  Switch,
  Tabs,
  TabPane,
  Textarea,
  TimePicker,
  Tooltip,
} from 'ant-design-vue';

import { getSchemaApi, updateSchemaApi } from '../api';
import { PALETTE_CATEGORIES, WIDGET_COLORS, WIDGET_DATA_TYPE, WIDGET_ICONS, t } from '../data';

defineOptions({ name: 'NccFormBuilder' });

const route = useRoute();
const router = useRouter();

const projectId = ref(0);
const schemaId = ref(0);
const schema = ref<NccTableSchema | null>(null);
const formFields = ref<FormField[]>([]);
const selectedField = ref<FormField | null>(null);
const saving = ref(false);
const isDragOver = ref(false);
const previewMode = ref(false);
const newOptionText = ref('');
const searchQuery = ref('');
const activeLocale = ref('default');
const formLocales = ref(['zh-CN', 'en-US']);
const activePropSections = ref(['basic', 'state', 'layout', 'options', 'validation', 'validation-num', 'display']);
const canvasWidth = ref<'desktop' | 'mobile'>('desktop');
let applyTimer: ReturnType<typeof setTimeout> | null = null;

const selectedFieldIndex = computed(() => {
  if (!selectedField.value) return -1;
  return formFields.value.findIndex((f) => f.id === selectedField.value!.id);
});

const fieldPositionText = computed(() => {
  if (selectedFieldIndex.value < 0) return '';
  return `${selectedFieldIndex.value + 1} / ${formFields.value.length}`;
});

const matchedFieldIds = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return new Set<string>();
  return new Set(
    formFields.value
      .filter((f) => f.label.toLowerCase().includes(q) || f.name.toLowerCase().includes(q) || f.widget.includes(q))
      .map((f) => f.id),
  );
});

let sortable: Sortable | null = null;
const canvasRef = ref<HTMLElement | null>(null);

const MAX_HISTORY = 50;
const history = ref<string[]>([]);
const historyIndex = ref(-1);
const canUndo = computed(() => historyIndex.value > 0);
const canRedo = computed(() => historyIndex.value < history.value.length - 1);

function pushHistory() {
  const snap = JSON.stringify(formFields.value);
  if (historyIndex.value >= 0 && history.value[historyIndex.value] === snap) return;
  history.value = history.value.slice(0, historyIndex.value + 1);
  history.value.push(snap);
  if (history.value.length > MAX_HISTORY) history.value.shift();
  historyIndex.value = history.value.length - 1;
}

function undo() {
  if (!canUndo.value) return;
  historyIndex.value--;
  formFields.value = JSON.parse(history.value[historyIndex.value]!);
  selectedField.value = null;
}

function redo() {
  if (!canRedo.value) return;
  historyIndex.value++;
  formFields.value = JSON.parse(history.value[historyIndex.value]!);
  selectedField.value = null;
}

const hasOptions = computed(() => {
  const w = selectedField.value?.widget;
  return w === 'select' || w === 'radio' || w === 'checkbox-group';
});

const hasMinMax = computed(() => {
  const w = selectedField.value?.widget;
  return w === 'number' || w === 'slider' || w === 'rate';
});

const hasTextLength = computed(() => {
  const w = selectedField.value?.widget;
  return w === 'input' || w === 'textarea' || w === 'password' || w === 'email' || w === 'url';
});

function schemaTypeToWidget(type: NccField['type']): FormWidgetType {
  const map: Record<string, FormWidgetType> = {
    string: 'input', integer: 'number', boolean: 'switch',
    datetime: 'date', text: 'textarea', json: 'json-editor',
  };
  return map[type] ?? 'input';
}

async function loadData() {
  projectId.value = Number(route.params.projectId) || 0;
  schemaId.value = Number(route.params.schemaId) || 0;
  if (!projectId.value || !schemaId.value) return;
  try {
    const s = await getSchemaApi(projectId.value, schemaId.value);
    schema.value = s;

    const existingForm = s.form_config?.fields as FormField[] | undefined;
    if (existingForm && existingForm.length > 0) {
      formFields.value = existingForm.map((f) => ({
        ...f,
        widget: f.widget || schemaTypeToWidget(f.type),
        defaultValue: f.defaultValue ?? '',
        disabled: f.disabled ?? false,
      }));
    } else {
      formFields.value = (s.schema_config?.fields ?? []).map((f: NccField): FormField => ({
        id: `${f.name}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        name: f.name,
        label: f.label || f.name,
        type: f.type,
        widget: schemaTypeToWidget(f.type),
        required: f.required,
        placeholder: '',
        helpText: '',
        options: f.options ?? [],
        span: 24,
        defaultValue: '',
        disabled: false,
      }));
    }
    await nextTick();
    initSortable();
    pushHistory();
  } catch {
    // handled
  }
}

function initSortable() {
  if (canvasRef.value && !sortable) {
    sortable = Sortable.create(canvasRef.value, {
      animation: 150,
      ghostClass: 'ncc-fb-ghost',
      chosenClass: 'ncc-fb-chosen',
      onEnd: (evt) => {
        const { oldIndex, newIndex } = evt;
        if (oldIndex === undefined || newIndex === undefined || oldIndex === newIndex) return;
        const fields = [...formFields.value];
        const [moved] = fields.splice(oldIndex, 1);
        if (moved) fields.splice(newIndex, 0, moved);
        formFields.value = fields;
        pushHistory();
      },
    });
  }
}

function addWidget(widget: string) {
  const dataType = (WIDGET_DATA_TYPE[widget] ?? 'string') as NccField['type'];
  const newField: FormField = {
    id: `field-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    name: `field_${Date.now()}`,
    label: t(`widget.${widget === 'checkbox-group' ? 'checkboxGroup' : widget === 'json-editor' ? 'jsonEditor' : widget}`),
    type: dataType,
    widget: widget as FormWidgetType,
    required: false,
    placeholder: '',
    helpText: '',
    options: hasOptionsForWidget(widget) ? [t('formBuilder.option') + ' 1', t('formBuilder.option') + ' 2'] : [],
    span: 24,
    defaultValue: '',
    disabled: false,
    rows: widget === 'textarea' ? 3 : undefined,
    step: widget === 'number' || widget === 'slider' ? 1 : undefined,
    max: widget === 'rate' ? 5 : undefined,
  };
  formFields.value.push(newField);
  selectedField.value = newField;
  pushHistory();
}

function addWidgetAt(widget: string, index: number) {
  const dataType = (WIDGET_DATA_TYPE[widget] ?? 'string') as NccField['type'];
  const widgetKey = widget === 'checkbox-group' ? 'checkboxGroup' : widget === 'json-editor' ? 'jsonEditor' : widget;
  const newField: FormField = {
    id: `field-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    name: `field_${Date.now()}`,
    label: t(`widget.${widgetKey}`),
    type: dataType,
    widget: widget as FormWidgetType,
    required: false,
    placeholder: '',
    helpText: '',
    options: hasOptionsForWidget(widget) ? [t('formBuilder.option') + ' 1', t('formBuilder.option') + ' 2'] : [],
    span: 24,
    defaultValue: '',
    disabled: false,
    rows: widget === 'textarea' ? 3 : undefined,
    step: widget === 'number' || widget === 'slider' ? 1 : undefined,
    max: widget === 'rate' ? 5 : undefined,
  };
  formFields.value.splice(index, 0, newField);
  selectedField.value = newField;
  pushHistory();
}

function onCanvasDrop(e: DragEvent) {
  isDragOver.value = false;
  const widget = e.dataTransfer?.getData('ncc-widget');
  if (!widget) return;
  const canvasEl = canvasRef.value;
  if (!canvasEl) { addWidget(widget); return; }
  const children = Array.from(canvasEl.children) as HTMLElement[];
  let insertIdx = children.length;
  for (let i = 0; i < children.length; i++) {
    const rect = children[i]!.getBoundingClientRect();
    if (e.clientY < rect.top + rect.height / 2) { insertIdx = i; break; }
  }
  addWidgetAt(widget, insertIdx);
}

function onPaletteDragStart(e: DragEvent, widget: string) {
  e.dataTransfer?.setData('ncc-widget', widget);
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy';
}

function hasOptionsForWidget(w: string) {
  return w === 'select' || w === 'radio' || w === 'checkbox-group';
}

function selectField(f: FormField) {
  selectedField.value = { ...f, locales: f.locales ? { ...f.locales } : {} };
  activeLocale.value = 'default';
}

function applyFieldEdit() {
  if (!selectedField.value) return;
  const idx = formFields.value.findIndex((f) => f.id === selectedField.value!.id);
  if (idx >= 0) {
    formFields.value[idx] = { ...selectedField.value };
    pushHistory();
  }
}

watch(
  () => selectedField.value,
  () => {
    if (!selectedField.value) return;
    if (applyTimer) clearTimeout(applyTimer);
    applyTimer = setTimeout(() => applyFieldEdit(), 200);
  },
  { deep: true },
);

function widgetLabelKey(w: string): string {
  if (w === 'checkbox-group') return 'widget.checkboxGroup';
  if (w === 'json-editor') return 'widget.jsonEditor';
  return `widget.${w}`;
}

const COMPATIBLE_WIDGETS: Record<string, FormWidgetType[]> = {
  string: ['input', 'password', 'email', 'url', 'select', 'radio'],
  integer: ['number', 'slider', 'rate'],
  boolean: ['switch', 'checkbox'],
  datetime: ['date', 'datetime', 'time'],
  text: ['textarea'],
  json: ['checkbox-group', 'json-editor', 'upload'],
};

const compatibleWidgets = computed(() => {
  if (!selectedField.value) return [];
  return COMPATIBLE_WIDGETS[selectedField.value.type] ?? [];
});

function changeWidget(newWidget: FormWidgetType) {
  if (!selectedField.value) return;
  selectedField.value.widget = newWidget;
}

function getLocaleField(field: 'label' | 'placeholder' | 'helpText'): string {
  if (!selectedField.value) return '';
  if (activeLocale.value === 'default') return selectedField.value[field];
  return selectedField.value.locales?.[activeLocale.value]?.[field] ?? '';
}

function setLocaleField(field: 'label' | 'placeholder' | 'helpText', value: string) {
  if (!selectedField.value) return;
  if (activeLocale.value === 'default') {
    selectedField.value[field] = value;
  } else {
    if (!selectedField.value.locales) selectedField.value.locales = {};
    if (!selectedField.value.locales[activeLocale.value]) {
      selectedField.value.locales[activeLocale.value] = {};
    }
    selectedField.value.locales[activeLocale.value]![field] = value;
  }
}

function removeField(id: string) {
  formFields.value = formFields.value.filter((f) => f.id !== id);
  if (selectedField.value?.id === id) selectedField.value = null;
  pushHistory();
}

function addOption() {
  if (!selectedField.value || !newOptionText.value.trim()) return;
  selectedField.value.options = [...selectedField.value.options, newOptionText.value.trim()];
  newOptionText.value = '';
}

function removeOption(idx: number) {
  if (!selectedField.value) return;
  const opts = [...selectedField.value.options];
  opts.splice(idx, 1);
  selectedField.value.options = opts;
}

function moveFieldUp() {
  const idx = selectedFieldIndex.value;
  if (idx <= 0) return;
  const fields = [...formFields.value];
  [fields[idx - 1], fields[idx]] = [fields[idx]!, fields[idx - 1]!];
  formFields.value = fields;
  pushHistory();
  if (formFields.value[idx - 1]) selectField(formFields.value[idx - 1]!);
}

function moveFieldDown() {
  const idx = selectedFieldIndex.value;
  if (idx < 0 || idx >= formFields.value.length - 1) return;
  const fields = [...formFields.value];
  [fields[idx], fields[idx + 1]] = [fields[idx + 1]!, fields[idx]!];
  formFields.value = fields;
  pushHistory();
  if (formFields.value[idx + 1]) selectField(formFields.value[idx + 1]!);
}

function clearAllFields() {
  formFields.value = [];
  selectedField.value = null;
  pushHistory();
}

function exportFormConfig() {
  const json = JSON.stringify({ fields: formFields.value }, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${schema.value?.name || 'form'}-config.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function importFormConfig() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';
  input.onchange = async () => {
    const file = input.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      if (data.fields && Array.isArray(data.fields)) {
        formFields.value = data.fields;
        selectedField.value = null;
        pushHistory();
      }
    } catch {
      // invalid JSON
    }
  };
  input.click();
}

function applyQuickTemplate(tpl: 'contact' | 'feedback' | 'registration') {
  const templates: Record<string, Array<{ widget: FormWidgetType; labelKey: string; name: string; required?: boolean; rows?: number; options?: string[] }>> = {
    contact: [
      { widget: 'input', labelKey: 'widget.input', name: 'name', required: true },
      { widget: 'email', labelKey: 'widget.email', name: 'email', required: true },
      { widget: 'input', labelKey: 'widget.input', name: 'subject' },
      { widget: 'textarea', labelKey: 'widget.textarea', name: 'message', required: true, rows: 5 },
    ],
    feedback: [
      { widget: 'rate', labelKey: 'widget.rate', name: 'rating', required: true },
      { widget: 'select', labelKey: 'widget.select', name: 'category', options: ['Bug', 'Feature', 'UX', 'Other'] },
      { widget: 'textarea', labelKey: 'widget.textarea', name: 'comments', rows: 4 },
      { widget: 'switch', labelKey: 'widget.switch', name: 'anonymous' },
    ],
    registration: [
      { widget: 'input', labelKey: 'widget.input', name: 'username', required: true },
      { widget: 'email', labelKey: 'widget.email', name: 'email', required: true },
      { widget: 'password', labelKey: 'widget.password', name: 'password', required: true },
      { widget: 'date', labelKey: 'widget.date', name: 'birthday' },
      { widget: 'radio', labelKey: 'widget.radio', name: 'gender', options: ['Male', 'Female', 'Other'] },
      { widget: 'checkbox', labelKey: 'widget.checkbox', name: 'agree_terms', required: true },
    ],
  };
  const items = templates[tpl];
  if (!items) return;
  const newFields: FormField[] = items.map((item) => ({
    id: `field-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    name: item.name,
    label: t(item.labelKey) + ' - ' + item.name,
    type: (WIDGET_DATA_TYPE[item.widget] ?? 'string') as NccField['type'],
    widget: item.widget,
    required: item.required ?? false,
    placeholder: '',
    helpText: '',
    options: item.options ?? [],
    span: 24,
    defaultValue: '',
    disabled: false,
    rows: item.rows,
  }));
  formFields.value = [...formFields.value, ...newFields];
  pushHistory();
}

function duplicateField(f: FormField) {
  const copy: FormField = {
    ...f,
    id: `field-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    name: `${f.name}_copy`,
    label: `${f.label} (copy)`,
  };
  const idx = formFields.value.findIndex((x) => x.id === f.id);
  formFields.value.splice(idx + 1, 0, copy);
  selectedField.value = copy;
  pushHistory();
}

async function saveFormConfig() {
  if (!schema.value) return;
  saving.value = true;
  try {
    await updateSchemaApi(projectId.value, schemaId.value, {
      form_config: { fields: formFields.value },
    });
  } catch {
    // handled
  } finally {
    saving.value = false;
  }
}

function onKeyDown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement).tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
  if (previewMode.value) return;

  const ctrl = e.ctrlKey || e.metaKey;
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedField.value) { e.preventDefault(); removeField(selectedField.value.id); }
  } else if (ctrl && e.key === 'd') {
    if (selectedField.value) {
      e.preventDefault();
      const f = formFields.value.find((x) => x.id === selectedField.value!.id);
      if (f) duplicateField(f);
    }
  } else if (ctrl && e.key === 'z') {
    e.preventDefault();
    if (e.shiftKey) redo(); else undo();
  } else if (ctrl && e.key === 'y') {
    e.preventDefault(); redo();
  } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    if (selectedField.value) {
      e.preventDefault();
      const idx = formFields.value.findIndex((f) => f.id === selectedField.value!.id);
      if (idx < 0) return;
      const next = e.key === 'ArrowUp' ? Math.max(0, idx - 1) : Math.min(formFields.value.length - 1, idx + 1);
      if (next !== idx && formFields.value[next]) selectField(formFields.value[next]!);
    }
  } else if (e.key === 'Escape') {
    selectedField.value = null;
  }
}

onMounted(() => { loadData(); document.addEventListener('keydown', onKeyDown); });
onBeforeUnmount(() => { sortable?.destroy(); sortable = null; document.removeEventListener('keydown', onKeyDown); });
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden">
    <!-- Toolbar -->
    <div class="flex shrink-0 items-center gap-3 border-b bg-card px-5 py-2.5">
      <button
        class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        @click="router.push(`/admin/plugins/novus-crud-code/projects/${projectId}`)"
      >
        <IconifyIcon icon="lucide:arrow-left" class="h-3.5 w-3.5" />
        {{ t('record.backToProject') }}
      </button>
      <span class="text-border">|</span>
      <span class="inline-flex items-center gap-1.5 text-sm font-bold text-foreground">
        <IconifyIcon icon="lucide:layout-template" class="h-4 w-4 text-primary" />
        {{ t('formBuilder.title') }}
      </span>
      <span class="text-border">|</span>
      <span class="text-xs text-muted-foreground">
        {{ schema?.display_name || schema?.name }} · {{ formFields.length }} {{ t('schema.fields') }}
      </span>
      <div v-if="!previewMode && formFields.length > 3" class="ml-2 flex items-center">
        <Input
          v-model:value="searchQuery"
          size="small"
          :placeholder="t('formBuilder.searchFields')"
          allow-clear
          class="w-[160px]"
        >
          <template #prefix><IconifyIcon icon="lucide:search" class="h-3 w-3 text-muted-foreground" /></template>
        </Input>
        <span v-if="searchQuery && matchedFieldIds.size > 0" class="ml-1.5 text-[11px] text-primary">{{ matchedFieldIds.size }}</span>
      </div>
      <div class="ml-auto flex items-center gap-2">
        <Tooltip :title="t('formBuilder.importConfig')">
          <Button size="small" @click="importFormConfig">
            <template #icon><IconifyIcon icon="lucide:upload" class="h-3.5 w-3.5" /></template>
          </Button>
        </Tooltip>
        <Tooltip :title="t('formBuilder.exportConfig')">
          <Button size="small" :disabled="formFields.length === 0" @click="exportFormConfig">
            <template #icon><IconifyIcon icon="lucide:download" class="h-3.5 w-3.5" /></template>
          </Button>
        </Tooltip>
        <span class="text-border">|</span>
        <Tooltip :title="t('formBuilder.undo') + ' (Ctrl+Z)'">
          <Button size="small" :disabled="!canUndo" @click="undo">
            <template #icon><IconifyIcon icon="lucide:undo-2" class="h-3.5 w-3.5" /></template>
          </Button>
        </Tooltip>
        <Tooltip :title="t('formBuilder.redo') + ' (Ctrl+Y)'">
          <Button size="small" :disabled="!canRedo" @click="redo">
            <template #icon><IconifyIcon icon="lucide:redo-2" class="h-3.5 w-3.5" /></template>
          </Button>
        </Tooltip>
        <span class="text-border">|</span>
        <Tooltip :title="canvasWidth === 'desktop' ? t('formBuilder.mobilePreview') : t('formBuilder.desktopPreview')">
          <Button size="small" @click="canvasWidth = canvasWidth === 'desktop' ? 'mobile' : 'desktop'">
            <template #icon><IconifyIcon :icon="canvasWidth === 'desktop' ? 'lucide:smartphone' : 'lucide:monitor'" class="h-3.5 w-3.5" /></template>
          </Button>
        </Tooltip>
        <Button
          :type="previewMode ? 'primary' : 'default'"
          size="small"
          @click="previewMode = !previewMode"
        >
          <template #icon>
            <IconifyIcon :icon="previewMode ? 'lucide:pencil' : 'lucide:eye'" class="h-3.5 w-3.5" />
          </template>
          {{ previewMode ? t('common.edit') : t('formBuilder.preview') }}
        </Button>
        <Button type="primary" :loading="saving" @click="saveFormConfig">
          <template #icon><IconifyIcon icon="lucide:save" /></template>
          {{ t('common.save') }}
        </Button>
      </div>
    </div>

    <!-- Main Layout -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left: Component Palette (categorized) -->
      <div v-if="!previewMode" class="w-[240px] shrink-0 overflow-y-auto border-r bg-card">
        <div class="flex items-center gap-1.5 border-b bg-muted/50 px-4 py-3 text-xs font-semibold text-foreground">
          <IconifyIcon icon="lucide:puzzle" class="h-3.5 w-3.5" />
          {{ t('formBuilder.components') }}
        </div>
        <div class="p-2">
          <div v-for="cat in PALETTE_CATEGORIES" :key="cat.labelKey" class="mb-2">
            <div class="flex items-center gap-1.5 px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              <IconifyIcon :icon="cat.icon" class="h-3 w-3" />
              {{ t(cat.labelKey) }}
            </div>
            <div
              v-for="item in cat.items"
              :key="item.widget"
              draggable="true"
              class="mb-0.5 flex cursor-grab items-center gap-2.5 rounded-md border border-transparent px-3 py-2 text-sm transition-all hover:border-primary/40 hover:bg-primary/5 active:scale-[0.98] active:cursor-grabbing"
              @click="addWidget(item.widget)"
              @dragstart="(e) => onPaletteDragStart(e, item.widget)"
            >
              <span
                class="flex h-6 w-6 shrink-0 items-center justify-center rounded"
                :class="WIDGET_COLORS[item.widget] ?? 'bg-muted text-muted-foreground'"
              >
                <IconifyIcon :icon="WIDGET_ICONS[item.widget] ?? 'lucide:type'" class="h-3 w-3" />
              </span>
              <span class="text-foreground">{{ t(item.labelKey) }}</span>
            </div>
          </div>
        </div>
        <div class="border-t px-4 py-3">
          <div class="text-[11px] leading-relaxed text-muted-foreground">
            <IconifyIcon icon="lucide:info" class="mr-1 inline h-3 w-3" />
            {{ t('formBuilder.tip') }}
          </div>
        </div>
      </div>

      <!-- Center: Form Canvas -->
      <div class="flex-1 overflow-y-auto bg-muted/20">
        <div
          class="mx-auto p-6 transition-all"
          :class="[isDragOver ? 'bg-primary/5' : '', canvasWidth === 'mobile' ? 'max-w-[375px]' : 'max-w-[720px]']"
          @dragover.prevent="isDragOver = true"
          @dragleave="isDragOver = false"
          @drop.prevent="onCanvasDrop"
        >
          <!-- Form title preview -->
          <div class="mb-5 rounded-lg border bg-card px-6 py-4 shadow-sm">
            <h3 class="text-base font-semibold text-foreground">
              {{ schema?.display_name || schema?.name || t('formBuilder.title') }}
            </h3>
            <p class="mt-0.5 text-xs text-muted-foreground">
              <span class="text-destructive">*</span> {{ t('formBuilder.requiredHint') }}
            </p>
          </div>

          <!-- Empty state with quick templates -->
          <div v-if="formFields.length === 0" class="flex flex-col items-center gap-4 py-12">
            <IconifyIcon icon="lucide:file-plus-2" class="h-12 w-12 text-muted-foreground/30" />
            <p class="text-sm text-muted-foreground">{{ t('formBuilder.empty') }}</p>
            <div class="flex flex-col items-center gap-2">
              <span class="text-xs font-medium text-muted-foreground">{{ t('formBuilder.quickTemplates') }}</span>
              <div class="flex gap-2">
                <Button size="small" @click="applyQuickTemplate('contact')">
                  <template #icon><IconifyIcon icon="lucide:mail" class="h-3 w-3" /></template>
                  {{ t('formBuilder.tplContact') }}
                </Button>
                <Button size="small" @click="applyQuickTemplate('feedback')">
                  <template #icon><IconifyIcon icon="lucide:message-square" class="h-3 w-3" /></template>
                  {{ t('formBuilder.tplFeedback') }}
                </Button>
                <Button size="small" @click="applyQuickTemplate('registration')">
                  <template #icon><IconifyIcon icon="lucide:user-plus" class="h-3 w-3" /></template>
                  {{ t('formBuilder.tplRegistration') }}
                </Button>
              </div>
            </div>
          </div>

          <!-- Form fields grid -->
          <div ref="canvasRef" class="grid grid-cols-2 gap-3">
            <div
              v-for="f in formFields"
              :key="f.id"
              :class="[
                f.span === 12 ? 'col-span-1' : 'col-span-2',
                f.widget === 'divider' ? '' : 'rounded-lg border bg-card p-4',
                'group relative transition-all',
                selectedField?.id === f.id
                  ? 'border-primary ring-2 ring-primary/20'
                  : searchQuery && matchedFieldIds.has(f.id)
                    ? 'border-warning ring-2 ring-warning/30'
                    : f.widget !== 'divider' ? 'hover:border-primary/30 hover:shadow-sm' : '',
                !previewMode ? 'cursor-move' : '',
              ]"
              @click="!previewMode && selectField(f)"
            >
              <!-- Drag handle + actions (edit mode only) -->
              <div v-if="!previewMode" class="absolute -top-px right-2 z-10 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                <Tooltip :title="t('formBuilder.duplicate')">
                  <button
                    class="rounded-b-md bg-primary/10 px-1.5 py-0.5 text-primary transition-colors hover:bg-primary/20"
                    @click.stop="duplicateField(f)"
                  >
                    <IconifyIcon icon="lucide:copy" class="h-3 w-3" />
                  </button>
                </Tooltip>
                <span class="rounded-b-md bg-muted px-1.5 py-0.5">
                  <IconifyIcon icon="lucide:grip-vertical" class="h-3 w-3 text-muted-foreground" />
                </span>
                <button
                  class="rounded-b-md bg-destructive/10 px-1.5 py-0.5 text-destructive transition-colors hover:bg-destructive/20"
                  @click.stop="removeField(f.id)"
                >
                  <IconifyIcon icon="lucide:x" class="h-3 w-3" />
                </button>
              </div>

              <!-- Divider widget -->
              <template v-if="f.widget === 'divider'">
                <div class="flex items-center gap-3 py-2">
                  <div class="h-px flex-1 bg-border" />
                  <span v-if="f.label" class="text-xs font-medium text-muted-foreground">{{ f.label }}</span>
                  <div class="h-px flex-1 bg-border" />
                </div>
              </template>

              <!-- Normal field -->
              <template v-else>
                <!-- Field label -->
                <label class="mb-1.5 flex items-center gap-1 text-sm font-medium text-foreground">
                  {{ f.label || f.name }}
                  <span v-if="f.required" class="text-destructive">*</span>
                  <span
                    v-if="!previewMode"
                    class="ml-auto rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold"
                    :class="WIDGET_COLORS[f.widget] ?? 'bg-muted text-muted-foreground'"
                  >{{ f.widget }}</span>
                </label>

                <!-- Widget previews -->
                <template v-if="f.widget === 'input' || f.widget === 'email' || f.widget === 'url'">
                  <Input :placeholder="f.placeholder || f.label || f.name" :disabled="!previewMode" size="middle">
                    <template v-if="f.widget === 'email'" #prefix><IconifyIcon icon="lucide:mail" class="h-3.5 w-3.5 text-muted-foreground" /></template>
                    <template v-if="f.widget === 'url'" #prefix><IconifyIcon icon="lucide:link" class="h-3.5 w-3.5 text-muted-foreground" /></template>
                  </Input>
                </template>
                <template v-else-if="f.widget === 'password'">
                  <Input type="password" :placeholder="f.placeholder || '••••••'" :disabled="!previewMode" size="middle">
                    <template #prefix><IconifyIcon icon="lucide:lock" class="h-3.5 w-3.5 text-muted-foreground" /></template>
                  </Input>
                </template>
                <template v-else-if="f.widget === 'number'">
                  <InputNumber :placeholder="f.placeholder || '0'" :disabled="!previewMode" :min="f.min" :max="f.max" :step="f.step" class="w-full" size="middle" />
                </template>
                <template v-else-if="f.widget === 'slider'">
                  <Slider :disabled="!previewMode" :min="f.min ?? 0" :max="f.max ?? 100" :step="f.step ?? 1" />
                </template>
                <template v-else-if="f.widget === 'rate'">
                  <Rate :disabled="!previewMode" :count="f.max ?? 5" />
                </template>
                <template v-else-if="f.widget === 'select'">
                  <Select :placeholder="f.placeholder || f.label" :disabled="!previewMode" :mode="f.multiple ? 'multiple' : undefined" class="w-full" size="middle">
                    <SelectOption v-for="opt in f.options" :key="opt" :value="opt">{{ opt }}</SelectOption>
                  </Select>
                </template>
                <template v-else-if="f.widget === 'radio'">
                  <RadioGroup :disabled="!previewMode">
                    <Radio v-for="opt in f.options" :key="opt" :value="opt">{{ opt }}</Radio>
                  </RadioGroup>
                </template>
                <template v-else-if="f.widget === 'checkbox-group'">
                  <CheckboxGroup :disabled="!previewMode" :options="f.options" />
                </template>
                <template v-else-if="f.widget === 'switch'">
                  <div class="flex items-center gap-2 py-1">
                    <Switch :disabled="!previewMode" />
                    <span class="text-sm text-muted-foreground">{{ f.label || f.name }}</span>
                  </div>
                </template>
                <template v-else-if="f.widget === 'checkbox'">
                  <div class="flex items-center gap-2 py-1">
                    <Checkbox :disabled="!previewMode" />
                    <span class="text-sm text-muted-foreground">{{ f.label || f.name }}</span>
                  </div>
                </template>
                <template v-else-if="f.widget === 'date'">
                  <DatePicker :placeholder="f.placeholder || f.label" :disabled="!previewMode" class="w-full" size="middle" />
                </template>
                <template v-else-if="f.widget === 'datetime'">
                  <DatePicker show-time :placeholder="f.placeholder || f.label" :disabled="!previewMode" class="w-full" size="middle" />
                </template>
                <template v-else-if="f.widget === 'time'">
                  <TimePicker :placeholder="f.placeholder || f.label" :disabled="!previewMode" class="w-full" size="middle" />
                </template>
                <template v-else-if="f.widget === 'textarea'">
                  <Textarea :placeholder="f.placeholder || f.label" :disabled="!previewMode" :rows="f.rows ?? 3" size="middle" />
                </template>
                <template v-else-if="f.widget === 'upload'">
                  <div class="flex items-center gap-2 rounded-md border border-dashed bg-muted/20 px-4 py-3 text-muted-foreground">
                    <IconifyIcon icon="lucide:upload-cloud" class="h-5 w-5" />
                    <span class="text-sm">{{ t('formBuilder.uploadHint') }}</span>
                  </div>
                </template>
                <template v-else-if="f.widget === 'json-editor'">
                  <div class="rounded-md border bg-muted/30 px-3 py-2 font-mono text-xs text-muted-foreground">
                    { "key": "value" }
                  </div>
                </template>
                <template v-else>
                  <Input :placeholder="f.placeholder || f.label || f.name" :disabled="!previewMode" size="middle" />
                </template>

                <!-- Help text -->
                <div v-if="f.helpText" class="mt-1 text-xs text-muted-foreground">
                  {{ f.helpText }}
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Properties Panel (refactored) -->
      <div v-if="!previewMode" class="w-[300px] shrink-0 overflow-y-auto border-l bg-card">
        <div class="flex items-center gap-1.5 border-b bg-muted/50 px-4 py-3 text-xs font-semibold text-foreground">
          <IconifyIcon icon="lucide:sliders-horizontal" class="h-3.5 w-3.5" />
          {{ t('formBuilder.properties') }}
        </div>
        <div v-if="!selectedField" class="flex flex-col items-center gap-3 py-12 text-center">
          <IconifyIcon icon="lucide:mouse-pointer-click" class="h-10 w-10 text-muted-foreground/30" />
          <span class="text-xs text-muted-foreground">{{ t('formBuilder.selectField') }}</span>
        </div>
        <div v-else class="ncc-prop-panel">
          <!-- Widget type header + position + move -->
          <div class="border-b px-4 py-3">
            <div class="mb-2 flex items-center gap-2">
              <span
                class="flex h-7 w-7 items-center justify-center rounded-md"
                :class="WIDGET_COLORS[selectedField.widget] ?? 'bg-muted text-muted-foreground'"
              >
                <IconifyIcon :icon="WIDGET_ICONS[selectedField.widget] ?? 'lucide:type'" class="h-3.5 w-3.5" />
              </span>
              <div class="flex-1">
                <div class="text-sm font-medium text-foreground">{{ t(widgetLabelKey(selectedField.widget)) }}</div>
                <div class="font-mono text-[10px] text-muted-foreground">{{ selectedField.type }}</div>
              </div>
              <div class="flex items-center gap-1">
                <span class="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">{{ fieldPositionText }}</span>
                <Tooltip :title="t('formBuilder.moveUp')">
                  <button
                    class="rounded p-1 transition-colors hover:bg-muted disabled:opacity-30"
                    :disabled="selectedFieldIndex <= 0"
                    @click="moveFieldUp"
                  >
                    <IconifyIcon icon="lucide:chevron-up" class="h-3.5 w-3.5" />
                  </button>
                </Tooltip>
                <Tooltip :title="t('formBuilder.moveDown')">
                  <button
                    class="rounded p-1 transition-colors hover:bg-muted disabled:opacity-30"
                    :disabled="selectedFieldIndex >= formFields.length - 1"
                    @click="moveFieldDown"
                  >
                    <IconifyIcon icon="lucide:chevron-down" class="h-3.5 w-3.5" />
                  </button>
                </Tooltip>
              </div>
            </div>
            <div v-if="compatibleWidgets.length > 1">
              <div class="mb-1 text-[11px] text-muted-foreground">{{ t('formBuilder.switchWidget') }}</div>
              <div class="flex flex-wrap gap-1">
                <button
                  v-for="cw in compatibleWidgets"
                  :key="cw"
                  class="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] transition-colors"
                  :class="selectedField.widget === cw ? 'border-primary bg-primary/10 text-primary' : 'hover:bg-muted'"
                  @click="changeWidget(cw)"
                >
                  <IconifyIcon :icon="WIDGET_ICONS[cw] ?? 'lucide:type'" class="h-3 w-3" />
                  {{ t(widgetLabelKey(cw)) }}
                </button>
              </div>
            </div>
          </div>

          <!-- Collapsible sections -->
          <Collapse v-model:activeKey="activePropSections" :bordered="false" expand-icon-position="end" class="ncc-prop-collapse">
            <!-- Basic -->
            <CollapsePanel key="basic" :header="t('formBuilder.propBasic')">
              <div class="space-y-2.5">
                <!-- Language tabs for label/placeholder/helpText -->
                <Tabs v-model:activeKey="activeLocale" size="small" class="ncc-locale-tabs">
                  <TabPane key="default" :tab="t('formBuilder.localeDefault')" />
                  <TabPane v-for="loc in formLocales" :key="loc" :tab="loc" />
                </Tabs>

                <div>
                  <div class="mb-1 text-xs font-medium text-foreground">{{ t('field.label') }}</div>
                  <Input
                    :value="getLocaleField('label')"
                    size="small"
                    :placeholder="activeLocale !== 'default' ? selectedField.label : ''"
                    @update:value="(v: string) => setLocaleField('label', v)"
                  />
                </div>
                <div v-if="selectedField.widget !== 'divider' && selectedField.widget !== 'switch' && selectedField.widget !== 'checkbox'">
                  <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.placeholder') }}</div>
                  <Input
                    :value="getLocaleField('placeholder')"
                    size="small"
                    :placeholder="activeLocale !== 'default' ? selectedField.placeholder : ''"
                    @update:value="(v: string) => setLocaleField('placeholder', v)"
                  />
                </div>
                <div>
                  <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.helpText') }}</div>
                  <Input
                    :value="getLocaleField('helpText')"
                    size="small"
                    :placeholder="activeLocale !== 'default' ? selectedField.helpText : ''"
                    @update:value="(v: string) => setLocaleField('helpText', v)"
                  />
                </div>

                <div>
                  <div class="mb-1 text-xs font-medium text-foreground">{{ t('field.name') }}</div>
                  <Input v-model:value="selectedField.name" size="small" class="font-mono" />
                </div>
                <div v-if="selectedField.widget !== 'divider'">
                  <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.defaultValue') }}</div>
                  <Input v-model:value="selectedField.defaultValue" size="small" />
                </div>
              </div>
            </CollapsePanel>

            <!-- State -->
            <CollapsePanel v-if="selectedField.widget !== 'divider'" key="state" :header="t('formBuilder.propState')">
              <div class="space-y-2">
                <div class="flex items-center justify-between rounded-md border px-3 py-2">
                  <span class="text-xs text-foreground">{{ t('field.required') }}</span>
                  <Switch v-model:checked="selectedField.required" size="small" />
                </div>
                <div class="flex items-center justify-between rounded-md border px-3 py-2">
                  <span class="text-xs text-foreground">{{ t('formBuilder.disabled') }}</span>
                  <Switch v-model:checked="selectedField.disabled" size="small" />
                </div>
              </div>
            </CollapsePanel>

            <!-- Layout -->
            <CollapsePanel key="layout" :header="t('formBuilder.propLayout')">
              <div>
                <div class="mb-1.5 text-xs font-medium text-foreground">{{ t('formBuilder.width') }}</div>
                <div class="flex gap-2">
                  <button
                    class="flex flex-1 flex-col items-center gap-1 rounded-md border-2 px-3 py-2 text-xs transition-colors"
                    :class="selectedField.span === 24 ? 'border-primary bg-primary/5 text-primary' : 'border-border hover:bg-muted'"
                    @click="selectedField!.span = 24"
                  >
                    <div class="h-2 w-full rounded bg-current opacity-30" />
                    {{ t('formBuilder.fullWidth') }}
                  </button>
                  <button
                    class="flex flex-1 flex-col items-center gap-1 rounded-md border-2 px-3 py-2 text-xs transition-colors"
                    :class="selectedField.span === 12 ? 'border-primary bg-primary/5 text-primary' : 'border-border hover:bg-muted'"
                    @click="selectedField!.span = 12"
                  >
                    <div class="flex w-full gap-1">
                      <div class="h-2 flex-1 rounded bg-current opacity-30" />
                      <div class="h-2 flex-1 rounded bg-current opacity-10" />
                    </div>
                    {{ t('formBuilder.halfWidth') }}
                  </button>
                </div>
              </div>
            </CollapsePanel>

            <!-- Options (select/radio/checkbox-group) -->
            <CollapsePanel v-if="hasOptions" key="options" :header="t('formBuilder.propOptions')">
              <div class="space-y-2">
                <div v-for="(opt, idx) in selectedField.options" :key="idx" class="flex items-center gap-1.5">
                  <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-muted text-[10px] font-bold text-muted-foreground">{{ idx + 1 }}</span>
                  <Input
                    :value="opt"
                    size="small"
                    class="flex-1"
                    @update:value="(v: string) => { selectedField!.options[idx] = v; }"
                  />
                  <button class="shrink-0 rounded p-1 text-destructive/60 transition-colors hover:bg-destructive/10 hover:text-destructive" @click="removeOption(idx)">
                    <IconifyIcon icon="lucide:trash-2" class="h-3 w-3" />
                  </button>
                </div>
                <div class="flex items-center gap-1.5">
                  <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-primary/10 text-[10px] font-bold text-primary">+</span>
                  <Input v-model:value="newOptionText" size="small" class="flex-1" :placeholder="t('formBuilder.newOption')" @press-enter="addOption" />
                  <Button size="small" type="primary" :disabled="!newOptionText.trim()" @click="addOption">
                    <template #icon><IconifyIcon icon="lucide:plus" class="h-3 w-3" /></template>
                  </Button>
                </div>
                <div v-if="selectedField.widget === 'select'" class="flex items-center justify-between rounded-md border px-3 py-2">
                  <span class="text-xs text-foreground">{{ t('formBuilder.multiSelect') }}</span>
                  <Switch v-model:checked="selectedField.multiple" size="small" />
                </div>
              </div>
            </CollapsePanel>

            <!-- Validation (text) -->
            <CollapsePanel v-if="hasTextLength" key="validation" :header="t('formBuilder.propValidation')">
              <div class="space-y-2.5">
                <div class="grid grid-cols-2 gap-2">
                  <div>
                    <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.minLength') }}</div>
                    <InputNumber v-model:value="selectedField.minLength" size="small" :min="0" class="w-full" />
                  </div>
                  <div>
                    <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.maxLength') }}</div>
                    <InputNumber v-model:value="selectedField.maxLength" size="small" :min="0" class="w-full" />
                  </div>
                </div>
                <div>
                  <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.pattern') }}</div>
                  <Input v-model:value="selectedField.pattern" size="small" class="font-mono" :placeholder="t('formBuilder.patternHint')" />
                </div>
              </div>
            </CollapsePanel>

            <!-- Validation (number) -->
            <CollapsePanel v-if="hasMinMax" key="validation-num" :header="t('formBuilder.propValidation')">
              <div class="space-y-2.5">
                <div class="grid grid-cols-2 gap-2">
                  <div>
                    <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.min') }}</div>
                    <InputNumber v-model:value="selectedField.min" size="small" class="w-full" />
                  </div>
                  <div>
                    <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.max') }}</div>
                    <InputNumber v-model:value="selectedField.max" size="small" class="w-full" />
                  </div>
                </div>
                <div>
                  <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.step') }}</div>
                  <InputNumber v-model:value="selectedField.step" size="small" :min="1" class="w-full" />
                </div>
              </div>
            </CollapsePanel>

            <!-- Display (textarea) -->
            <CollapsePanel v-if="selectedField.widget === 'textarea'" key="display" :header="t('formBuilder.propDisplay')">
              <div>
                <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.rows') }}</div>
                <InputNumber v-model:value="selectedField.rows" size="small" :min="1" :max="20" class="w-full" />
              </div>
            </CollapsePanel>
          </Collapse>

          <!-- Actions footer -->
          <div class="space-y-2 border-t px-4 py-3">
            <Button class="w-full" @click="duplicateField(selectedField!)">
              <template #icon><IconifyIcon icon="lucide:copy" class="h-3.5 w-3.5" /></template>
              {{ t('formBuilder.duplicate') }}
            </Button>
            <Button danger class="w-full" @click="removeField(selectedField!.id)">
              <template #icon><IconifyIcon icon="lucide:trash-2" /></template>
              {{ t('common.delete') }}
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ncc-prop-collapse :deep(.ant-collapse-header) {
  padding: 8px 16px !important;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.ncc-prop-collapse :deep(.ant-collapse-content-box) {
  padding: 8px 16px 12px !important;
}
.ncc-prop-collapse :deep(.ant-collapse-item) {
  border-bottom: 1px solid hsl(var(--border));
}
.ncc-locale-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 8px;
}
.ncc-locale-tabs :deep(.ant-tabs-tab) {
  padding: 4px 8px;
  font-size: 11px;
}
</style>
