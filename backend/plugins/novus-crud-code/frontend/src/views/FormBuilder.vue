<script lang="ts" setup>
import type { NccField, NccTableSchema } from '../types';

import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import Sortable from 'sortablejs';
import {
  Button,
  Checkbox,
  DatePicker,
  Empty,
  Input,
  InputNumber,
  Select,
  SelectOption,
  Switch,
  Textarea,
} from 'ant-design-vue';

import { getSchemaApi, updateSchemaApi } from '../api';
import { FIELD_TYPE_COLORS, FIELD_TYPE_ICONS, t } from '../data';

defineOptions({ name: 'NccFormBuilder' });

const route = useRoute();
const router = useRouter();

interface FormField {
  id: string;
  name: string;
  label: string;
  type: NccField['type'];
  required: boolean;
  placeholder: string;
  helpText: string;
  options: string[];
  span: 12 | 24;
}

const PALETTE_ITEMS: { type: NccField['type']; labelKey: string }[] = [
  { type: 'string', labelKey: 'field.type.string' },
  { type: 'integer', labelKey: 'field.type.integer' },
  { type: 'boolean', labelKey: 'field.type.boolean' },
  { type: 'datetime', labelKey: 'field.type.datetime' },
  { type: 'text', labelKey: 'field.type.text' },
  { type: 'json', labelKey: 'field.type.json' },
];

const projectId = ref(0);
const schemaId = ref(0);
const schema = ref<NccTableSchema | null>(null);
const formFields = ref<FormField[]>([]);
const selectedField = ref<FormField | null>(null);
const saving = ref(false);
const isDragOver = ref(false);
const previewMode = ref(false);

let sortable: Sortable | null = null;
const canvasRef = ref<HTMLElement | null>(null);

async function loadData() {
  projectId.value = Number(route.params.projectId) || 0;
  schemaId.value = Number(route.params.schemaId) || 0;
  if (!projectId.value || !schemaId.value) return;
  try {
    const s = await getSchemaApi(projectId.value, schemaId.value);
    schema.value = s;

    const existingForm = s.form_config?.fields as FormField[] | undefined;
    if (existingForm && existingForm.length > 0) {
      formFields.value = existingForm;
    } else {
      formFields.value = (s.schema_config?.fields ?? []).map((f: NccField): FormField => ({
        id: `${f.name}-${Date.now()}`,
        name: f.name,
        label: f.label || f.name,
        type: f.type,
        required: f.required,
        placeholder: '',
        helpText: '',
        options: [],
        span: 24,
      }));
    }
    await nextTick();
    initSortable();
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
      },
    });
  }
}

function addFieldFromPalette(type: NccField['type'], label: string) {
  const newField: FormField = {
    id: `field-${Date.now()}`,
    name: `field_${Date.now()}`,
    label,
    type,
    required: false,
    placeholder: '',
    helpText: '',
    options: [],
    span: 24,
  };
  formFields.value.push(newField);
  selectedField.value = newField;
}

function selectField(f: FormField) {
  selectedField.value = { ...f };
}

function applyFieldEdit() {
  if (!selectedField.value) return;
  const idx = formFields.value.findIndex((f) => f.id === selectedField.value!.id);
  if (idx >= 0) {
    formFields.value[idx] = { ...selectedField.value };
  }
}

function removeField(id: string) {
  formFields.value = formFields.value.filter((f) => f.id !== id);
  if (selectedField.value?.id === id) selectedField.value = null;
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

onMounted(() => loadData());
onBeforeUnmount(() => { sortable?.destroy(); sortable = null; });
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
      <div class="ml-auto flex items-center gap-2">
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
      <!-- Left: Component Palette -->
      <div v-if="!previewMode" class="w-[220px] shrink-0 overflow-y-auto border-r bg-card">
        <div class="flex items-center gap-1.5 border-b bg-muted/50 px-4 py-3 text-xs font-semibold text-foreground">
          <IconifyIcon icon="lucide:puzzle" class="h-3.5 w-3.5" />
          {{ t('formBuilder.components') }}
        </div>
        <div class="p-2">
          <div
            v-for="item in PALETTE_ITEMS"
            :key="item.type"
            draggable="true"
            class="mb-1 flex cursor-grab items-center gap-2.5 rounded-md border border-transparent px-3 py-2.5 text-sm transition-all hover:border-primary/40 hover:bg-primary/5 hover:shadow-sm active:scale-[0.98]"
            @click="addFieldFromPalette(item.type, t(item.labelKey))"
          >
            <span
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
              :class="FIELD_TYPE_COLORS[item.type] ?? 'bg-muted text-muted-foreground'"
            >
              <IconifyIcon :icon="FIELD_TYPE_ICONS[item.type] ?? 'lucide:type'" class="h-3.5 w-3.5" />
            </span>
            <span class="text-foreground">{{ t(item.labelKey) }}</span>
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
          class="mx-auto max-w-[720px] p-6 transition-colors"
          :class="isDragOver ? 'bg-primary/5' : ''"
          @dragover.prevent="isDragOver = true"
          @dragleave="isDragOver = false"
          @drop.prevent="isDragOver = false"
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

          <!-- Empty state -->
          <Empty
            v-if="formFields.length === 0"
            :description="t('formBuilder.empty')"
            class="mt-16"
          />

          <!-- Form fields grid -->
          <div ref="canvasRef" class="grid grid-cols-2 gap-3">
            <div
              v-for="f in formFields"
              :key="f.id"
              :class="[
                f.span === 12 ? 'col-span-1' : 'col-span-2',
                'group relative rounded-lg border bg-card p-4 transition-all',
                selectedField?.id === f.id
                  ? 'border-primary ring-2 ring-primary/20'
                  : 'hover:border-primary/30 hover:shadow-sm',
                !previewMode ? 'cursor-move' : '',
              ]"
              @click="!previewMode && selectField(f)"
            >
              <!-- Drag handle + actions (edit mode only) -->
              <div v-if="!previewMode" class="absolute -top-px right-2 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
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

              <!-- Field label -->
              <label class="mb-1.5 flex items-center gap-1 text-sm font-medium text-foreground">
                {{ f.label || f.name }}
                <span v-if="f.required" class="text-destructive">*</span>
                <span
                  v-if="!previewMode"
                  class="ml-auto rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold"
                  :class="FIELD_TYPE_COLORS[f.type] ?? 'bg-muted text-muted-foreground'"
                >{{ f.type }}</span>
              </label>

              <!-- Form control preview -->
              <template v-if="f.type === 'string'">
                <Input
                  :placeholder="f.placeholder || f.label || f.name"
                  disabled
                  size="middle"
                />
              </template>
              <template v-else-if="f.type === 'integer'">
                <InputNumber
                  :placeholder="f.placeholder || '0'"
                  disabled
                  class="w-full"
                  size="middle"
                />
              </template>
              <template v-else-if="f.type === 'boolean'">
                <div class="flex items-center gap-2 py-1">
                  <Switch disabled />
                  <span class="text-sm text-muted-foreground">{{ f.label || f.name }}</span>
                </div>
              </template>
              <template v-else-if="f.type === 'datetime'">
                <DatePicker
                  :placeholder="f.placeholder || f.label || f.name"
                  disabled
                  class="w-full"
                  size="middle"
                />
              </template>
              <template v-else-if="f.type === 'text'">
                <Textarea
                  :placeholder="f.placeholder || f.label || f.name"
                  disabled
                  :rows="3"
                  size="middle"
                />
              </template>
              <template v-else-if="f.type === 'json'">
                <div class="rounded-md border bg-muted/30 px-3 py-2 font-mono text-xs text-muted-foreground">
                  { "key": "value" }
                </div>
              </template>
              <template v-else>
                <Input
                  :placeholder="f.placeholder || f.label || f.name"
                  disabled
                  size="middle"
                />
              </template>

              <!-- Help text -->
              <div v-if="f.helpText" class="mt-1 text-xs text-muted-foreground">
                {{ f.helpText }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Properties Panel -->
      <div v-if="!previewMode" class="w-[260px] shrink-0 overflow-y-auto border-l bg-card">
        <div class="flex items-center gap-1.5 border-b bg-muted/50 px-4 py-3 text-xs font-semibold text-foreground">
          <IconifyIcon icon="lucide:sliders-horizontal" class="h-3.5 w-3.5" />
          {{ t('formBuilder.properties') }}
        </div>
        <div v-if="!selectedField" class="flex flex-col items-center gap-2 py-10 text-center">
          <IconifyIcon icon="lucide:mouse-pointer-click" class="h-8 w-8 text-muted-foreground/40" />
          <span class="text-xs text-muted-foreground">{{ t('formBuilder.selectField') }}</span>
        </div>
        <div v-else class="space-y-3 p-4">
          <!-- Field type indicator -->
          <div class="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2">
            <span
              class="flex h-6 w-6 items-center justify-center rounded"
              :class="FIELD_TYPE_COLORS[selectedField.type] ?? 'bg-muted text-muted-foreground'"
            >
              <IconifyIcon :icon="FIELD_TYPE_ICONS[selectedField.type] ?? 'lucide:type'" class="h-3 w-3" />
            </span>
            <span class="text-xs font-medium text-foreground">{{ t(`field.type.${selectedField.type}`) }}</span>
          </div>

          <div>
            <div class="mb-1 text-xs font-medium text-foreground">{{ t('field.label') }}</div>
            <Input v-model:value="selectedField.label" size="small" @change="applyFieldEdit" />
          </div>
          <div>
            <div class="mb-1 text-xs font-medium text-foreground">{{ t('field.name') }}</div>
            <Input v-model:value="selectedField.name" size="small" class="font-mono" @change="applyFieldEdit" />
          </div>
          <div>
            <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.placeholder') }}</div>
            <Input v-model:value="selectedField.placeholder" size="small" @change="applyFieldEdit" />
          </div>
          <div>
            <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.helpText') }}</div>
            <Input v-model:value="selectedField.helpText" size="small" @change="applyFieldEdit" />
          </div>
          <div class="flex items-center gap-2 rounded-md border px-3 py-2">
            <Checkbox v-model:checked="selectedField.required" @change="applyFieldEdit" />
            <span class="text-xs text-foreground">{{ t('field.required') }}</span>
          </div>
          <div>
            <div class="mb-1 text-xs font-medium text-foreground">{{ t('formBuilder.width') }}</div>
            <Select v-model:value="selectedField.span" size="small" class="w-full" @change="applyFieldEdit">
              <SelectOption :value="24">{{ t('formBuilder.fullWidth') }}</SelectOption>
              <SelectOption :value="12">{{ t('formBuilder.halfWidth') }}</SelectOption>
            </Select>
          </div>
          <div class="border-t pt-3">
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
