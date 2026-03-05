<script lang="ts" setup>
import type { NccProject, NccTableSchema } from '../types';

import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Breadcrumb,
  BreadcrumbItem,
  Button,
  Empty,
  Input,
  Modal,
  Spin,
  TabPane,
  Tabs,
  Textarea,
  message,
} from 'ant-design-vue';

import {
  createSchemaApi,
  deleteSchemaApi,
  getProjectApi,
  listSchemasApi,
  updateSchemaApi,
} from '../api';
import { FIELD_TYPE_COLORS, t } from '../data';

defineOptions({ name: 'NccProjectDetail' });

const route = useRoute();
const router = useRouter();

const projectId = ref(0);
const project = ref<NccProject | null>(null);
const schemas = ref<NccTableSchema[]>([]);
const loading = ref(false);
const activeTab = ref('schemas');
const showCreateSchema = ref(false);
const showEditSchema = ref(false);
const editSchemaId = ref<number | null>(null);
const schemaForm = ref({ name: '', display_name: '', description: '' });
const savingSchema = ref(false);

const totalFields = computed(() =>
  schemas.value.reduce((sum, s) => sum + (s.schema_config?.fields ?? []).length, 0),
);

async function loadData() {
  projectId.value = Number(route.params.projectId) || 0;
  if (!projectId.value) return;
  loading.value = true;
  try {
    const [p, s] = await Promise.all([
      getProjectApi(projectId.value),
      listSchemasApi(projectId.value),
    ]);
    project.value = p;
    schemas.value = s.items ?? [];
  } catch {
    // handled
  } finally {
    loading.value = false;
  }
}

function openCreateSchema() {
  editSchemaId.value = null;
  schemaForm.value = { name: '', display_name: '', description: '' };
  showCreateSchema.value = true;
}

function openEditSchema(s: NccTableSchema) {
  editSchemaId.value = s.id;
  schemaForm.value = {
    name: s.name,
    display_name: s.display_name || '',
    description: s.description ?? '',
  };
  showEditSchema.value = true;
}

async function saveCreateSchema() {
  savingSchema.value = true;
  try {
    await createSchemaApi(projectId.value, {
      ...schemaForm.value,
      schema_config: { fields: [] },
    });
    showCreateSchema.value = false;
    schemaForm.value = { name: '', display_name: '', description: '' };
    await loadData();
  } catch {
    // handled
  } finally {
    savingSchema.value = false;
  }
}

async function saveEditSchema() {
  if (!editSchemaId.value) return;
  savingSchema.value = true;
  try {
    await updateSchemaApi(projectId.value, editSchemaId.value, {
      display_name: schemaForm.value.display_name,
      description: schemaForm.value.description,
    });
    showEditSchema.value = false;
    await loadData();
  } catch {
    // handled
  } finally {
    savingSchema.value = false;
  }
}

function confirmDeleteSchema(id: number) {
  Modal.confirm({
    title: t('schema.confirmDelete'),
    okType: 'danger',
    okText: t('common.delete'),
    cancelText: t('common.cancel'),
    onOk: async () => {
      try {
        await deleteSchemaApi(projectId.value, id);
        message.success(t('common.delete'));
        await loadData();
      } catch {
        // handled
      }
    },
  });
}

function openDesigner() {
  router.push(`/admin/plugins/novus-crud-code/projects/${projectId.value}/schema`);
}

function openDataGrid(schemaId: number) {
  router.push(`/admin/plugins/novus-crud-code/projects/${projectId.value}/schemas/${schemaId}/data`);
}

function openFormBuilder(schemaId: number) {
  router.push(`/admin/plugins/novus-crud-code/projects/${projectId.value}/schemas/${schemaId}/form`);
}

onMounted(() => loadData());
</script>

<template>
  <Page auto-content-height>
    <div class="space-y-4">
      <!-- Breadcrumb -->
      <Breadcrumb>
        <BreadcrumbItem>
          <a class="text-primary" @click="router.push('/admin/plugins/novus-crud-code/projects')">
            DataForge Studio
          </a>
        </BreadcrumbItem>
        <BreadcrumbItem>
          <span class="font-medium text-foreground">{{ project?.display_name || project?.name || '...' }}</span>
        </BreadcrumbItem>
      </Breadcrumb>

      <Spin :spinning="loading">
        <!-- Project Header Card -->
        <div class="relative mb-4 overflow-hidden rounded-xl border bg-card shadow-sm">
          <div class="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent" />
          <div class="relative p-5">
            <div class="flex items-start justify-between">
              <div class="flex items-center gap-4">
                <div
                  class="flex h-12 w-12 items-center justify-center rounded-xl shadow-sm"
                  :style="{ backgroundColor: `${project?.color ?? '#6366f1'}18`, color: project?.color ?? '#6366f1' }"
                >
                  <IconifyIcon icon="lucide:database" class="h-6 w-6" />
                </div>
                <div>
                  <h2 class="text-lg font-bold text-foreground">
                    {{ project?.display_name || project?.name }}
                  </h2>
                  <p v-if="project?.description" class="mt-0.5 text-sm text-muted-foreground">
                    {{ project.description }}
                  </p>
                </div>
              </div>
              <Button type="primary" @click="openDesigner">
                <template #icon><IconifyIcon icon="lucide:pen-tool" /></template>
                {{ t('schema.openDesigner') }}
              </Button>
            </div>
            <!-- Quick Stats -->
            <div class="mt-4 flex gap-6 border-t pt-4">
              <div class="flex items-center gap-2">
                <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                  <IconifyIcon icon="lucide:layout-grid" class="h-4 w-4 text-primary" />
                </div>
                <div>
                  <div class="text-lg font-bold text-foreground">{{ schemas.length }}</div>
                  <div class="text-xs text-muted-foreground">{{ t('schema.count') }}</div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-success/10">
                  <IconifyIcon icon="lucide:columns-3" class="h-4 w-4 text-success" />
                </div>
                <div>
                  <div class="text-lg font-bold text-foreground">{{ totalFields }}</div>
                  <div class="text-xs text-muted-foreground">{{ t('schema.fields') }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tabs -->
        <Tabs v-model:active-key="activeTab">
          <TabPane key="schemas">
            <template #tab>
              <span class="inline-flex items-center gap-1.5">
                <IconifyIcon icon="lucide:layout-grid" class="h-3.5 w-3.5" />
                {{ t('tab.schemas') }}
              </span>
            </template>

            <!-- Tables Header -->
            <div class="mb-3 flex items-center justify-between">
              <span class="text-sm text-muted-foreground">{{ schemas.length }} {{ t('schema.count') }}</span>
              <Button type="primary" size="small" @click="openCreateSchema">
                <template #icon><IconifyIcon icon="lucide:plus" /></template>
                {{ t('schema.create') }}
              </Button>
            </div>

            <Empty
              v-if="schemas.length === 0"
              :description="t('schema.empty')"
              class="py-10"
            />

            <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <div
                v-for="s in schemas"
                :key="s.id"
                class="group overflow-hidden rounded-xl border bg-card transition-all hover:-translate-y-0.5 hover:shadow-md"
              >
                <!-- Card Header -->
                <div class="border-b bg-muted/30 px-4 py-3">
                  <div class="flex items-start justify-between">
                    <div class="min-w-0 flex-1">
                      <div class="truncate text-sm font-semibold text-foreground">{{ s.display_name || s.name }}</div>
                      <div class="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">{{ s.name }}</div>
                    </div>
                    <div class="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                        @click="openEditSchema(s)"
                      >
                        <IconifyIcon icon="lucide:pencil" class="h-3 w-3" />
                      </button>
                      <button
                        class="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                        @click="confirmDeleteSchema(s.id)"
                      >
                        <IconifyIcon icon="lucide:trash-2" class="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Card Body -->
                <div class="px-4 py-3">
                  <!-- Description -->
                  <p class="mb-3 text-xs text-muted-foreground">
                    {{ s.description || t('schema.noDescription') }}
                  </p>

                  <!-- Field type badges -->
                  <div class="mb-3 flex flex-wrap gap-1">
                    <span
                      v-for="ft in [...new Set((s.schema_config?.fields ?? []).map((f: { type: string }) => f.type))]"
                      :key="ft"
                      class="rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold"
                      :class="FIELD_TYPE_COLORS[ft] ?? 'bg-muted text-muted-foreground'"
                    >{{ ft }}</span>
                    <span class="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {{ (s.schema_config?.fields ?? []).length }} {{ t('schema.fields') }}
                    </span>
                  </div>

                  <!-- Action buttons -->
                  <div class="flex gap-2">
                    <button
                      class="flex flex-1 items-center justify-center gap-1.5 rounded-lg border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-primary/5 hover:text-primary"
                      @click="openDataGrid(s.id)"
                    >
                      <IconifyIcon icon="lucide:table" class="h-3.5 w-3.5" />
                      {{ t('schema.data') }}
                    </button>
                    <button
                      class="flex flex-1 items-center justify-center gap-1.5 rounded-lg border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-primary/5 hover:text-primary"
                      @click="openFormBuilder(s.id)"
                    >
                      <IconifyIcon icon="lucide:file-text" class="h-3.5 w-3.5" />
                      {{ t('schema.form') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </TabPane>

          <TabPane key="relations">
            <template #tab>
              <span class="inline-flex items-center gap-1.5">
                <IconifyIcon icon="lucide:link" class="h-3.5 w-3.5" />
                {{ t('tab.relations') }}
              </span>
            </template>

            <div class="py-10 text-center text-sm text-muted-foreground">
              {{ t('relations.hint') }}
              <div class="mt-4">
                <Button type="primary" @click="openDesigner">
                  {{ t('schema.openDesigner') }}
                </Button>
              </div>
            </div>
          </TabPane>
        </Tabs>
      </Spin>

      <!-- Create Schema Modal -->
      <Modal
        v-model:open="showCreateSchema"
        :title="t('schema.create')"
        :confirm-loading="savingSchema"
        :ok-text="t('common.save')"
        :cancel-text="t('common.cancel')"
        :ok-button-props="{ disabled: !schemaForm.name }"
        @ok="saveCreateSchema"
      >
        <div class="space-y-4 pt-2">
          <div>
            <div class="mb-1 text-sm font-medium text-foreground">
              {{ t('schema.field.name') }} <span class="text-destructive">*</span>
            </div>
            <Input v-model:value="schemaForm.name" placeholder="my_table" />
          </div>
          <div>
            <div class="mb-1 text-sm font-medium text-foreground">{{ t('schema.field.displayName') }}</div>
            <Input v-model:value="schemaForm.display_name" :placeholder="t('schema.field.displayNamePlaceholder')" />
          </div>
          <div>
            <div class="mb-1 text-sm font-medium text-foreground">{{ t('schema.field.description') }}</div>
            <Textarea v-model:value="schemaForm.description" :placeholder="t('schema.field.descriptionPlaceholder')" :rows="2" />
          </div>
        </div>
      </Modal>

      <!-- Edit Schema Modal -->
      <Modal
        v-model:open="showEditSchema"
        :title="t('schema.editName')"
        :confirm-loading="savingSchema"
        :ok-text="t('common.save')"
        :cancel-text="t('common.cancel')"
        @ok="saveEditSchema"
      >
        <div class="space-y-4 pt-2">
          <div>
            <div class="mb-1 text-sm font-medium text-foreground">
              {{ t('schema.field.name') }}
            </div>
            <Input :value="schemaForm.name" disabled class="bg-muted/50" />
          </div>
          <div>
            <div class="mb-1 text-sm font-medium text-foreground">{{ t('schema.field.displayName') }}</div>
            <Input v-model:value="schemaForm.display_name" :placeholder="t('schema.field.displayNamePlaceholder')" />
          </div>
          <div>
            <div class="mb-1 text-sm font-medium text-foreground">{{ t('schema.field.description') }}</div>
            <Textarea v-model:value="schemaForm.description" :placeholder="t('schema.field.descriptionPlaceholder')" :rows="2" />
          </div>
        </div>
      </Modal>
    </div>
  </Page>
</template>
