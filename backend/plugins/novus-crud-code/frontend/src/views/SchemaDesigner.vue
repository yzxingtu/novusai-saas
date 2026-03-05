<script lang="ts" setup>
import type { Edge, Node } from '@vue-flow/core';
import type { NccField, NccRelation, NccTableSchema } from '../types';

import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Handle, Position, VueFlow, useVueFlow } from '@vue-flow/core';
import { Background } from '@vue-flow/background';
import { Controls } from '@vue-flow/controls';
import { MiniMap } from '@vue-flow/minimap';
import {
  Button,
  Checkbox,
  Dropdown,
  Empty,
  Input,
  Menu,
  MenuItem,
  Modal,
  Select,
  SelectOption,
  Spin,
  Textarea,
  Tooltip,
  message,
} from 'ant-design-vue';

import { createSchemaApi, deleteSchemaApi, listRelationsApi, listSchemasApi, updateSchemaApi } from '../api';
import { FIELD_TYPE_COLORS, t } from '../data';

defineOptions({ name: 'NccSchemaDesigner' });

const route = useRoute();
const router = useRouter();

const FIELD_TYPES = ['string', 'integer', 'boolean', 'datetime', 'text', 'json'] as const;

const loading = ref(false);
const schemas = ref<NccTableSchema[]>([]);
const relations = ref<NccRelation[]>([]);
const projectId = ref(0);
const selectedSchema = ref<NccTableSchema | null>(null);
const editingField = ref<NccField | null>(null);
const editingFieldIdx = ref(-1);
const saving = ref(false);
const showCreateModal = ref(false);
const showPropsModal = ref(false);
const createForm = ref({ name: '', display_name: '', description: '' });
const propsForm = ref({ display_name: '', description: '' });
const creatingSaving = ref(false);
const propsSaving = ref(false);

const FIELD_TEMPLATES: Record<string, NccField[]> = {
  basic: [
    { name: 'id', type: 'integer', label: 'ID', required: true, default: null },
    { name: 'created_at', type: 'datetime', label: 'Created At', required: false, default: null },
    { name: 'updated_at', type: 'datetime', label: 'Updated At', required: false, default: null },
  ],
  user: [
    { name: 'username', type: 'string', label: 'Username', required: true, default: null },
    { name: 'email', type: 'string', label: 'Email', required: true, default: null },
    { name: 'active', type: 'boolean', label: 'Active', required: false, default: true },
  ],
};

const nodes = computed<Node[]>(() =>
  schemas.value.map((s, i) => ({
    id: String(s.id),
    type: 'erTable',
    label: s.display_name || s.name,
    position: (s.ui_config as Record<string, { x: number; y: number }>)?.[`node_${s.id}`]
      ?? { x: 80 + (i % 3) * 260, y: 80 + Math.floor(i / 3) * 280 },
    data: { schema: s },
  })),
);

const edges = computed<Edge[]>(() =>
  relations.value.map((r) => ({
    id: `rel-${r.id}`,
    source: String(r.from_schema_id),
    target: String(r.to_schema_id),
    label: r.label || `${r.from_field} → ${r.to_field}`,
    type: 'smoothstep',
    animated: true,
    style: { stroke: 'hsl(var(--primary))' },
  })),
);

async function loadData() {
  projectId.value = Number(route.params.projectId) || 0;
  if (!projectId.value) return;
  loading.value = true;
  try {
    const [s, r] = await Promise.all([
      listSchemasApi(projectId.value),
      listRelationsApi(projectId.value),
    ]);
    schemas.value = s.items ?? [];
    relations.value = r.items ?? [];
    if (schemas.value.length > 0) selectedSchema.value = schemas.value[0]!;
  } catch {
    // handled
  } finally {
    loading.value = false;
  }
}

const { onNodeDragStop } = useVueFlow();
onNodeDragStop(async ({ node }) => {
  const s = schemas.value.find((x) => String(x.id) === node.id);
  if (!s) return;
  const newUiConfig = { ...(s.ui_config ?? {}), [`node_${s.id}`]: node.position };
  try {
    await updateSchemaApi(projectId.value, s.id, { ui_config: newUiConfig });
    s.ui_config = newUiConfig;
  } catch {
    // handled
  }
});

function selectSchema(s: NccTableSchema) {
  selectedSchema.value = s;
  editingField.value = null;
  editingFieldIdx.value = -1;
}

function addField() {
  if (!selectedSchema.value) return;
  editingField.value = { name: '', type: 'string', label: '', required: false, default: null };
  editingFieldIdx.value = -1;
}

function editField(field: NccField, idx: number) {
  editingField.value = { ...field };
  editingFieldIdx.value = idx;
}

function moveField(idx: number, direction: -1 | 1) {
  if (!selectedSchema.value) return;
  const fields = [...(selectedSchema.value.schema_config?.fields ?? [])];
  const newIdx = idx + direction;
  if (newIdx < 0 || newIdx >= fields.length) return;
  [fields[idx], fields[newIdx]] = [fields[newIdx]!, fields[idx]!];
  selectedSchema.value = {
    ...selectedSchema.value,
    schema_config: { ...selectedSchema.value.schema_config, fields },
  };
}

function deleteField(idx: number) {
  if (!selectedSchema.value) return;
  const fields = [...(selectedSchema.value.schema_config?.fields ?? [])];
  fields.splice(idx, 1);
  selectedSchema.value = {
    ...selectedSchema.value,
    schema_config: { ...selectedSchema.value.schema_config, fields },
  };
}

function saveField() {
  if (!selectedSchema.value || !editingField.value) return;
  const fields = [...(selectedSchema.value.schema_config?.fields ?? [])];
  if (editingFieldIdx.value >= 0) {
    fields[editingFieldIdx.value] = { ...editingField.value };
  } else {
    fields.push({ ...editingField.value });
  }
  selectedSchema.value = {
    ...selectedSchema.value,
    schema_config: { ...selectedSchema.value.schema_config, fields },
  };
  editingField.value = null;
  editingFieldIdx.value = -1;
}

async function saveSchema() {
  if (!selectedSchema.value) return;
  saving.value = true;
  try {
    const updated = await updateSchemaApi(projectId.value, selectedSchema.value.id, {
      schema_config: selectedSchema.value.schema_config,
    });
    const idx = schemas.value.findIndex((s) => s.id === selectedSchema.value!.id);
    if (idx >= 0) schemas.value[idx] = updated;
    selectedSchema.value = updated;
  } catch {
    // handled
  } finally {
    saving.value = false;
  }
}

function openCreateTable() {
  createForm.value = { name: '', display_name: '', description: '' };
  showCreateModal.value = true;
}

async function createTable() {
  if (!createForm.value.name) return;
  creatingSaving.value = true;
  try {
    const newSchema = await createSchemaApi(projectId.value, {
      name: createForm.value.name,
      display_name: createForm.value.display_name || createForm.value.name,
      description: createForm.value.description,
    });
    schemas.value.push(newSchema);
    selectedSchema.value = newSchema;
    showCreateModal.value = false;
  } catch {
    // handled
  } finally {
    creatingSaving.value = false;
  }
}

function confirmDeleteTable() {
  if (!selectedSchema.value) return;
  const schemaName = selectedSchema.value.display_name || selectedSchema.value.name;
  Modal.confirm({
    title: `${t('designer.deleteTable')}: ${schemaName}`,
    content: t('designer.confirmDeleteTable'),
    okType: 'danger',
    okText: t('common.delete'),
    cancelText: t('common.cancel'),
    onOk: async () => {
      try {
        await deleteSchemaApi(projectId.value, selectedSchema.value!.id);
        schemas.value = schemas.value.filter((s) => s.id !== selectedSchema.value!.id);
        selectedSchema.value = schemas.value.length > 0 ? schemas.value[0]! : null;
        message.success(t('common.delete'));
      } catch {
        // handled
      }
    },
  });
}

function openEditProps() {
  if (!selectedSchema.value) return;
  propsForm.value = {
    display_name: selectedSchema.value.display_name || '',
    description: selectedSchema.value.description || '',
  };
  showPropsModal.value = true;
}

async function saveTableProps() {
  if (!selectedSchema.value) return;
  propsSaving.value = true;
  try {
    const updated = await updateSchemaApi(projectId.value, selectedSchema.value.id, {
      display_name: propsForm.value.display_name,
      description: propsForm.value.description,
    });
    const idx = schemas.value.findIndex((s) => s.id === selectedSchema.value!.id);
    if (idx >= 0) schemas.value[idx] = updated;
    selectedSchema.value = updated;
    showPropsModal.value = false;
  } catch {
    // handled
  } finally {
    propsSaving.value = false;
  }
}

function applyFieldTemplate(key: string) {
  if (!selectedSchema.value) return;
  const templateFields = FIELD_TEMPLATES[key];
  if (!templateFields) return;
  const existing = selectedSchema.value.schema_config?.fields ?? [];
  const existingNames = new Set(existing.map((f) => f.name));
  const newFields = templateFields.filter((f) => !existingNames.has(f.name));
  if (newFields.length === 0) return;
  selectedSchema.value = {
    ...selectedSchema.value,
    schema_config: { ...selectedSchema.value.schema_config, fields: [...existing, ...newFields] },
  };
}

onMounted(() => loadData());
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
        <IconifyIcon icon="lucide:pen-tool" class="h-4 w-4 text-primary" />
        {{ t('designer.title') }}
      </span>
      <span class="text-border">|</span>
      <span class="text-xs text-muted-foreground">{{ schemas.length }} {{ t('schema.count') }}</span>
      <div class="ml-auto flex gap-2">
        <Button v-if="selectedSchema" type="primary" :loading="saving" @click="saveSchema">
          <template #icon><IconifyIcon icon="lucide:save" /></template>
          {{ t('common.save') }}
        </Button>
      </div>
    </div>

    <!-- Main Layout -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left: Table List -->
      <div class="w-[260px] shrink-0 overflow-y-auto border-r bg-card">
        <div class="flex items-center justify-between border-b bg-muted/50 px-4 py-2.5">
          <span class="inline-flex items-center gap-1.5 text-xs font-semibold text-foreground">
            <IconifyIcon icon="lucide:layout-grid" class="h-3.5 w-3.5" />
            {{ t('tab.schemas') }}
          </span>
          <Tooltip :title="t('designer.createTable')">
            <button
              class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
              @click="openCreateTable"
            >
              <IconifyIcon icon="lucide:plus" class="h-3.5 w-3.5" />
            </button>
          </Tooltip>
        </div>
        <div v-if="schemas.length === 0" class="py-5 text-center text-xs text-muted-foreground">
          {{ t('schema.empty') }}
        </div>
        <div
          v-for="s in schemas"
          :key="s.id"
          class="cursor-pointer border-b px-4 py-2.5 transition-colors"
          :class="selectedSchema?.id === s.id ? 'border-l-[3px] border-l-primary bg-primary/5' : 'border-l-[3px] border-l-transparent hover:bg-muted/30'"
          @click="selectSchema(s)"
        >
          <div class="text-sm font-medium text-foreground">{{ s.display_name || s.name }}</div>
          <div class="mt-0.5 font-mono text-[11px] text-muted-foreground">
            {{ s.name }} · {{ (s.schema_config?.fields ?? []).length }} {{ t('schema.fields') }}
          </div>
        </div>
      </div>

      <!-- Center: ER Diagram -->
      <div class="relative flex-1 bg-muted/30">
        <Spin v-if="loading" class="absolute inset-0 flex items-center justify-center" />
        <VueFlow v-else :nodes="nodes" :edges="edges" fit-view-on-init>
          <Background />
          <Controls />
          <MiniMap />
          <template #node-erTable="{ data }">
            <div class="min-w-[180px] overflow-hidden rounded-lg border-2 border-primary bg-card shadow-sm">
              <div class="flex items-center gap-1.5 bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground">
                <IconifyIcon icon="lucide:database" class="h-3.5 w-3.5" />
                {{ data.schema.display_name || data.schema.name }}
              </div>
              <div
                v-for="f in (data.schema.schema_config?.fields ?? []).slice(0, 8)"
                :key="f.name"
                class="flex items-center justify-between border-b px-3 py-1 text-xs"
              >
                <span class="text-foreground">{{ f.label || f.name }}</span>
                <span
                  class="rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold"
                  :class="FIELD_TYPE_COLORS[f.type] ?? 'bg-muted text-muted-foreground'"
                >{{ f.type }}</span>
                <Handle type="source" :position="Position.Right" :id="`${data.schema.id}-${f.name}-source`" />
                <Handle type="target" :position="Position.Left" :id="`${data.schema.id}-${f.name}-target`" />
              </div>
              <div
                v-if="(data.schema.schema_config?.fields ?? []).length > 8"
                class="py-1 text-center text-[11px] text-muted-foreground"
              >
                +{{ (data.schema.schema_config?.fields ?? []).length - 8 }} {{ t('schema.moreFields') }}
              </div>
            </div>
          </template>
        </VueFlow>
      </div>

      <!-- Right: Field Properties -->
      <div class="w-[280px] shrink-0 overflow-y-auto border-l bg-card">
        <div v-if="!selectedSchema" class="py-10 text-center text-xs text-muted-foreground">
          {{ t('designer.selectTable') }}
        </div>
        <template v-else>
          <div class="border-b bg-muted/50 px-4 py-2.5">
            <div class="flex items-center justify-between">
              <span class="inline-flex items-center gap-1.5 text-xs font-semibold text-foreground">
                <IconifyIcon icon="lucide:file-text" class="h-3.5 w-3.5" />
                {{ selectedSchema.display_name || selectedSchema.name }}
              </span>
              <div class="flex items-center gap-1">
                <Tooltip :title="t('designer.editTableProps')">
                  <button
                    class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                    @click="openEditProps"
                  >
                    <IconifyIcon icon="lucide:settings" class="h-3 w-3" />
                  </button>
                </Tooltip>
                <Tooltip :title="t('designer.deleteTable')">
                  <button
                    class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                    @click="confirmDeleteTable"
                  >
                    <IconifyIcon icon="lucide:trash-2" class="h-3 w-3" />
                  </button>
                </Tooltip>
              </div>
            </div>
            <div v-if="selectedSchema.description" class="mt-1 text-[11px] text-muted-foreground">
              {{ selectedSchema.description }}
            </div>
            <div class="mt-2 flex items-center gap-1.5">
              <Button size="small" type="primary" @click="addField">
                <template #icon><IconifyIcon icon="lucide:plus" class="h-3 w-3" /></template>
                {{ t('field.add') }}
              </Button>
              <Dropdown>
                <Button size="small">
                  <template #icon><IconifyIcon icon="lucide:copy-plus" class="h-3 w-3" /></template>
                  {{ t('designer.fieldTemplate') }}
                </Button>
                <template #overlay>
                  <Menu>
                    <MenuItem key="basic" @click="applyFieldTemplate('basic')">
                      <div class="text-xs font-medium">{{ t('designer.templateBasic') }}</div>
                      <div class="text-[11px] text-muted-foreground">{{ t('designer.templateBasicDesc') }}</div>
                    </MenuItem>
                    <MenuItem key="user" @click="applyFieldTemplate('user')">
                      <div class="text-xs font-medium">{{ t('designer.templateUser') }}</div>
                      <div class="text-[11px] text-muted-foreground">{{ t('designer.templateUserDesc') }}</div>
                    </MenuItem>
                  </Menu>
                </template>
              </Dropdown>
            </div>
          </div>

          <!-- Field List -->
          <div v-if="!editingField">
            <Empty
              v-if="(selectedSchema.schema_config?.fields ?? []).length === 0"
              :description="t('field.empty')"
              class="py-5"
            />
            <div
              v-for="(f, idx) in (selectedSchema.schema_config?.fields ?? [])"
              :key="idx"
              class="group flex items-center gap-2 border-b px-3 py-2"
            >
              <!-- Move buttons -->
              <div class="flex flex-col gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                <Tooltip :title="t('field.moveUp')" placement="left">
                  <button
                    class="inline-flex h-4 w-4 items-center justify-center rounded text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                    :disabled="idx === 0"
                    @click="moveField(idx, -1)"
                  >
                    <IconifyIcon icon="lucide:chevron-up" class="h-3 w-3" />
                  </button>
                </Tooltip>
                <Tooltip :title="t('field.moveDown')" placement="left">
                  <button
                    class="inline-flex h-4 w-4 items-center justify-center rounded text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                    :disabled="idx === (selectedSchema.schema_config?.fields ?? []).length - 1"
                    @click="moveField(idx, 1)"
                  >
                    <IconifyIcon icon="lucide:chevron-down" class="h-3 w-3" />
                  </button>
                </Tooltip>
              </div>
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm font-medium text-foreground">{{ f.label || f.name }}</div>
                <div class="mt-0.5 flex items-center gap-1.5">
                  <span
                    class="rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold"
                    :class="FIELD_TYPE_COLORS[f.type] ?? 'bg-muted text-muted-foreground'"
                  >{{ f.type }}</span>
                  <span v-if="f.required" class="text-[10px] font-semibold text-destructive">{{ t('field.required') }}</span>
                  <span v-if="f.default !== null && f.default !== undefined && f.default !== ''" class="text-[10px] text-muted-foreground">= {{ f.default }}</span>
                </div>
              </div>
              <button
                class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground opacity-0 transition-all hover:bg-primary/10 hover:text-primary group-hover:opacity-100"
                @click="editField(f, idx)"
              >
                <IconifyIcon icon="lucide:pencil" class="h-3 w-3" />
              </button>
              <button
                class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                @click="deleteField(idx)"
              >
                <IconifyIcon icon="lucide:trash-2" class="h-3 w-3" />
              </button>
            </div>
          </div>

          <!-- Field Editor -->
          <div v-else class="space-y-3 p-4">
            <div class="text-sm font-semibold text-foreground">
              {{ editingFieldIdx >= 0 ? t('field.edit') : t('field.add') }}
            </div>
            <div>
              <div class="mb-1 text-xs font-medium text-foreground">
                {{ t('field.name') }} <span class="text-destructive">*</span>
              </div>
              <Input v-model:value="editingField!.name" placeholder="field_name" size="small" />
            </div>
            <div>
              <div class="mb-1 text-xs font-medium text-foreground">{{ t('field.label') }}</div>
              <Input v-model:value="editingField!.label" :placeholder="t('field.labelPlaceholder')" size="small" />
            </div>
            <div>
              <div class="mb-1 text-xs font-medium text-foreground">{{ t('field.fieldType') }}</div>
              <Select v-model:value="editingField!.type" size="small" class="w-full">
                <SelectOption v-for="ft in FIELD_TYPES" :key="ft" :value="ft">{{ t(`field.type.${ft}`) }}</SelectOption>
              </Select>
            </div>
            <div>
              <div class="mb-1 text-xs font-medium text-foreground">{{ t('field.default') }}</div>
              <Input v-model:value="(editingField as Record<string, unknown>).default" :placeholder="t('field.defaultPlaceholder')" size="small" allow-clear />
            </div>
            <Checkbox v-model:checked="editingField!.required">{{ t('field.required') }}</Checkbox>
            <div class="flex gap-2 pt-2">
              <Button class="flex-1" @click="editingField = null">{{ t('common.cancel') }}</Button>
              <Button class="flex-1" type="primary" :disabled="!editingField?.name" @click="saveField">
                {{ t('common.save') }}
              </Button>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Create Table Modal -->
    <Modal
      v-model:open="showCreateModal"
      :title="t('designer.createTable')"
      :confirm-loading="creatingSaving"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      :ok-button-props="{ disabled: !createForm.name }"
      @ok="createTable"
    >
      <div class="space-y-4 pt-2">
        <div>
          <div class="mb-1 text-sm font-medium text-foreground">
            {{ t('schema.field.name') }} <span class="text-destructive">*</span>
          </div>
          <Input v-model:value="createForm.name" placeholder="my_table" />
        </div>
        <div>
          <div class="mb-1 text-sm font-medium text-foreground">{{ t('schema.field.displayName') }}</div>
          <Input v-model:value="createForm.display_name" :placeholder="t('schema.field.displayNamePlaceholder')" />
        </div>
        <div>
          <div class="mb-1 text-sm font-medium text-foreground">{{ t('schema.field.description') }}</div>
          <Textarea v-model:value="createForm.description" :placeholder="t('schema.field.descriptionPlaceholder')" :rows="2" />
        </div>
      </div>
    </Modal>

    <!-- Edit Table Properties Modal -->
    <Modal
      v-model:open="showPropsModal"
      :title="t('designer.editTableProps')"
      :confirm-loading="propsSaving"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      @ok="saveTableProps"
    >
      <div class="space-y-4 pt-2">
        <div>
          <div class="mb-1 text-sm font-medium text-foreground">{{ t('schema.field.displayName') }}</div>
          <Input v-model:value="propsForm.display_name" :placeholder="t('schema.field.displayNamePlaceholder')" />
        </div>
        <div>
          <div class="mb-1 text-sm font-medium text-foreground">{{ t('schema.field.description') }}</div>
          <Textarea v-model:value="propsForm.description" :placeholder="t('schema.field.descriptionPlaceholder')" :rows="3" />
        </div>
      </div>
    </Modal>
  </div>
</template>
