<script setup lang="ts">
import { computed, ref } from 'vue';

import {
  Alert,
  Button,
  Card,
  Checkbox,
  Drawer,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Table,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { UseBatchEditorReturn } from '../composables/use-batch-editor';
import type { UseTemplatesReturn } from '../composables/use-templates';
import type {
  CrudTemplate,
  TemplateApplyChange,
  TemplateModule,
} from '../types';

const props = defineProps<{
  editor: UseBatchEditorReturn;
  templateManager: UseTemplatesReturn;
}>();

const emit = defineEmits<{
  close: [];
}>();

const T = 'admin.dev.crudGenerator.templates';

// ---- Template list tab ----
const activeTab = ref<'entity' | 'project'>('entity');

const displayedTemplates = computed<CrudTemplate[]>(() => {
  return activeTab.value === 'entity'
    ? props.templateManager.entityTemplates.value
    : props.templateManager.projectTemplates.value;
});

// ---- Apply template ----
const showApplyDrawer = ref(false);
const applyingTemplate = ref<CrudTemplate | null>(null);
const selectedModules = ref<TemplateModule[]>([
  'fields',
  'enums',
  'relations',
  'indexes',
]);
const forceUnlock = ref(false);
const applyChanges = ref<TemplateApplyChange[]>([]);

const moduleOptions: { value: TemplateModule; labelKey: string }[] = [
  { value: 'fields', labelKey: 'moduleFields' },
  { value: 'enums', labelKey: 'moduleEnums' },
  { value: 'relations', labelKey: 'moduleRelations' },
  { value: 'indexes', labelKey: 'moduleIndexes' },
  { value: 'list', labelKey: 'moduleList' },
  { value: 'form', labelKey: 'moduleForm' },
  { value: 'search', labelKey: 'moduleSearch' },
  { value: 'slots', labelKey: 'moduleSlots' },
];

function openApply(template: CrudTemplate) {
  applyingTemplate.value = template;
  selectedModules.value = ['fields', 'enums', 'relations', 'indexes'];
  forceUnlock.value = false;
  updateApplyChanges();
  showApplyDrawer.value = true;
}

function updateApplyChanges() {
  const entity = props.editor.selectedEntity.value;
  const template = applyingTemplate.value;
  if (!entity || !template) {
    applyChanges.value = [];
    return;
  }
  const locked = props.editor.getLockedPaths(entity.module);
  applyChanges.value = props.templateManager.computeApplyChanges(
    template,
    entity,
    selectedModules.value,
    locked,
  );
}

function toggleModule(mod: TemplateModule) {
  const idx = selectedModules.value.indexOf(mod);
  if (idx >= 0) {
    selectedModules.value.splice(idx, 1);
  } else {
    selectedModules.value.push(mod);
  }
  updateApplyChanges();
}

function confirmApply() {
  const entity = props.editor.selectedEntity.value;
  const template = applyingTemplate.value;
  if (!entity || !template) return;

  const locked = props.editor.getLockedPaths(entity.module);
  props.templateManager.applyEntityTemplate(
    template,
    entity,
    selectedModules.value,
    forceUnlock.value,
    locked,
  );
  showApplyDrawer.value = false;
}

// ---- Save as template ----
const showSaveDialog = ref(false);
const saveName = ref('');
const saveDesc = ref('');
const saveVersion = ref('1.0.0');

function openSaveDialog() {
  const entity = props.editor.selectedEntity.value;
  if (!entity) return;
  saveName.value = `${entity.display_name || entity.module} Template`;
  saveDesc.value = '';
  saveVersion.value = '1.0.0';
  showSaveDialog.value = true;
}

function confirmSave() {
  const entity = props.editor.selectedEntity.value;
  if (!entity) return;
  props.templateManager.saveEntityAsTemplate(
    entity,
    saveName.value,
    saveDesc.value,
    saveVersion.value,
  );
  showSaveDialog.value = false;
}

// ---- Table columns ----
const columns = computed(() => [
  { title: $t(`${T}.templateName`), dataIndex: 'name', ellipsis: true },
  { title: $t(`${T}.templateVersion`), dataIndex: 'version', width: 80, align: 'center' as const },
  { title: '', dataIndex: 'actions', width: 120, align: 'center' as const },
]);

// ---- Change summary columns ----
const changeColumns = computed(() => [
  { title: $t(`${T}.applyScope`), dataIndex: 'module', width: 120 },
  { title: '', dataIndex: 'action', width: 160 },
  { title: '', dataIndex: 'count', width: 80, align: 'center' as const },
]);
</script>

<template>
  <Card size="small">
    <template #title>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="icon-[lucide--layout-template] size-4 text-primary" />
          <span class="text-sm font-medium">{{ $t(`${T}.title`) }}</span>
        </div>
        <div class="flex items-center gap-2">
          <Button size="small" type="text" @click="emit('close')">
            <template #icon>
              <span class="icon-[lucide--x] size-3.5" />
            </template>
          </Button>
        </div>
      </div>
    </template>

    <!-- Tab selector -->
    <div class="mb-3 flex items-center gap-2 border-b pb-2">
      <Button
        :type="activeTab === 'entity' ? 'primary' : 'default'"
        size="small"
        @click="activeTab = 'entity'"
      >
        {{ $t(`${T}.entityTemplate`) }}
      </Button>
      <Button
        :type="activeTab === 'project' ? 'primary' : 'default'"
        size="small"
        @click="activeTab = 'project'"
      >
        {{ $t(`${T}.projectTemplate`) }}
      </Button>
      <div class="flex-1" />
      <Button
        v-if="editor.selectedEntity.value"
        size="small"
        type="dashed"
        @click="openSaveDialog"
      >
        <template #icon>
          <span class="icon-[lucide--save] size-3.5" />
        </template>
        {{ $t(`${T}.saveAsTemplate`) }}
      </Button>
    </div>

    <!-- Search -->
    <Input
      v-model:value="templateManager.searchQuery.value"
      :placeholder="$t(`${T}.searchTemplate`)"
      allow-clear
      size="small"
      class="mb-3"
    >
      <template #prefix>
        <span class="icon-[lucide--search] size-3.5 text-muted-foreground" />
      </template>
    </Input>

    <!-- Template list -->
    <div v-if="displayedTemplates.length > 0">
      <Table
        :columns="columns"
        :data-source="displayedTemplates"
        :pagination="false"
        :scroll="{ y: 300 }"
        bordered
        row-key="id"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'name'">
            <div>
              <div class="text-sm font-medium">{{ (record as CrudTemplate).name }}</div>
              <div v-if="(record as CrudTemplate).description" class="text-xs text-muted-foreground">
                {{ (record as CrudTemplate).description }}
              </div>
            </div>
          </template>
          <template v-else-if="column.dataIndex === 'version'">
            <Tag size="small">v{{ (record as CrudTemplate).version }}</Tag>
          </template>
          <template v-else-if="column.dataIndex === 'actions'">
            <div class="flex items-center justify-center gap-1">
              <Tooltip :title="$t(`${T}.applyTemplate`)">
                <Button
                  size="small"
                  type="link"
                  @click="openApply(record as CrudTemplate)"
                >
                  <template #icon>
                    <span class="icon-[lucide--download] size-3.5" />
                  </template>
                </Button>
              </Tooltip>
              <Popconfirm
                :title="$t(`${T}.deleteConfirm`)"
                @confirm="templateManager.deleteTemplate((record as CrudTemplate).id)"
              >
                <Button danger size="small" type="link">
                  <template #icon>
                    <span class="icon-[lucide--trash-2] size-3.5" />
                  </template>
                </Button>
              </Popconfirm>
            </div>
          </template>
        </template>
      </Table>
    </div>
    <Empty v-else :description="$t(`${T}.noTemplates`)" />
  </Card>

  <!-- ============ Apply Drawer ============ -->
  <Drawer
    v-model:open="showApplyDrawer"
    :title="$t(`${T}.applyTemplate`)"
    :width="480"
    placement="right"
  >
    <div v-if="applyingTemplate" class="space-y-4">
      <!-- Template info -->
      <div class="rounded-md bg-accent/50 p-3">
        <div class="font-medium">{{ applyingTemplate.name }}</div>
        <div v-if="applyingTemplate.description" class="mt-1 text-xs text-muted-foreground">
          {{ applyingTemplate.description }}
        </div>
        <Tag size="small" class="mt-1">v{{ applyingTemplate.version }}</Tag>
      </div>

      <!-- Module selection -->
      <div>
        <label class="mb-2 block text-sm font-medium">{{ $t(`${T}.applyScope`) }}</label>
        <div class="grid grid-cols-2 gap-2">
          <div
            v-for="opt in moduleOptions"
            :key="opt.value"
            class="flex items-center gap-2"
          >
            <Checkbox
              :checked="selectedModules.includes(opt.value)"
              @change="toggleModule(opt.value)"
            />
            <span class="text-sm">{{ $t(`${T}.${opt.labelKey}`) }}</span>
          </div>
        </div>
      </div>

      <!-- Change summary -->
      <div v-if="applyChanges.length > 0">
        <label class="mb-2 block text-sm font-medium">{{ $t(`${T}.changeSummary`) }}</label>
        <Table
          :columns="changeColumns"
          :data-source="applyChanges"
          :pagination="false"
          bordered
          row-key="module"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'module'">
              <span class="text-sm">{{ (record as TemplateApplyChange).module }}</span>
            </template>
            <template v-else-if="column.dataIndex === 'action'">
              <Tag
                :color="(record as TemplateApplyChange).action === 'add' ? 'green' : (record as TemplateApplyChange).action === 'replace' ? 'orange' : 'default'"
                size="small"
              >
                {{ (record as TemplateApplyChange).action === 'add'
                  ? $t(`${T}.changeAdd`, { count: (record as TemplateApplyChange).itemCount })
                  : (record as TemplateApplyChange).action === 'replace'
                    ? $t(`${T}.changeReplace`, { count: (record as TemplateApplyChange).itemCount })
                    : $t(`${T}.changeSkip`, { count: (record as TemplateApplyChange).lockedCount })
                }}
              </Tag>
            </template>
            <template v-else-if="column.dataIndex === 'count'">
              <span class="text-sm">{{ (record as TemplateApplyChange).itemCount }}</span>
            </template>
          </template>
        </Table>
      </div>

      <!-- Locked paths warning -->
      <Alert
        v-if="applyChanges.some((c) => c.lockedCount > 0)"
        :message="$t(`${T}.lockedWarning`)"
        show-icon
        type="warning"
      >
        <template #action>
          <Checkbox
            v-model:checked="forceUnlock"
            @change="updateApplyChanges"
          >
            {{ $t(`${T}.unlockAndApply`) }}
          </Checkbox>
        </template>
      </Alert>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button @click="showApplyDrawer = false">
          {{ $t('common.cancel') }}
        </Button>
        <Button
          :disabled="selectedModules.length === 0"
          type="primary"
          @click="confirmApply"
        >
          {{ $t(`${T}.confirmApply`) }}
        </Button>
      </div>
    </template>
  </Drawer>

  <!-- ============ Save Template Dialog ============ -->
  <Modal
    v-model:open="showSaveDialog"
    :title="$t(`${T}.saveAsTemplate`)"
    @ok="confirmSave"
  >
    <div class="space-y-4 py-2">
      <div>
        <label class="mb-1 block text-sm">{{ $t(`${T}.templateName`) }}</label>
        <Input
          v-model:value="saveName"
          :placeholder="$t(`${T}.templateNamePlaceholder`)"
        />
      </div>
      <div>
        <label class="mb-1 block text-sm">{{ $t(`${T}.templateDesc`) }}</label>
        <Input.TextArea
          v-model:value="saveDesc"
          :placeholder="$t(`${T}.templateDescPlaceholder`)"
          :rows="3"
        />
      </div>
      <div>
        <label class="mb-1 block text-sm">{{ $t(`${T}.templateVersion`) }}</label>
        <Input
          v-model:value="saveVersion"
          :placeholder="$t(`${T}.templateVersionPlaceholder`)"
          class="w-32"
        />
      </div>
    </div>
  </Modal>
</template>
