<script lang="ts" setup>
import type { NccProject } from '../types';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  Input,
  Modal,
  Spin,
  Textarea,
  message,
} from 'ant-design-vue';

import {
  createProjectApi,
  deleteProjectApi,
  listProjectsApi,
  updateProjectApi,
} from '../api';
import { COLOR_PRESETS, formatDate, t } from '../data';

defineOptions({ name: 'NccProjectList' });

const router = useRouter();

const projects = ref<NccProject[]>([]);
const total = ref(0);
const loading = ref(false);
const searchText = ref('');
const showModal = ref(false);
const editItem = ref<NccProject | null>(null);
const form = ref({ name: '', display_name: '', description: '', color: '#6366f1', icon: 'lucide:database' });
const saving = ref(false);

const filteredProjects = computed(() =>
  projects.value.filter((p) =>
    !searchText.value
    || p.name.toLowerCase().includes(searchText.value.toLowerCase())
    || p.display_name.toLowerCase().includes(searchText.value.toLowerCase()),
  ),
);

async function loadProjects() {
  loading.value = true;
  try {
    const res = await listProjectsApi();
    projects.value = res.items ?? [];
    total.value = res.total ?? 0;
  } catch {
    // handled by request interceptor
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editItem.value = null;
  form.value = { name: '', display_name: '', description: '', color: '#6366f1', icon: 'lucide:database' };
  showModal.value = true;
}

function openEdit(p: NccProject) {
  editItem.value = p;
  form.value = {
    name: p.name,
    display_name: p.display_name,
    description: p.description ?? '',
    color: p.color ?? '#6366f1',
    icon: p.icon ?? 'lucide:database',
  };
  showModal.value = true;
}

async function saveProject() {
  saving.value = true;
  try {
    if (editItem.value) {
      await updateProjectApi(editItem.value.id, form.value);
    } else {
      await createProjectApi(form.value);
    }
    showModal.value = false;
    await loadProjects();
  } catch {
    // handled
  } finally {
    saving.value = false;
  }
}

function confirmDelete(id: number) {
  Modal.confirm({
    title: t('project.confirmDelete'),
    okType: 'danger',
    okText: t('common.delete'),
    cancelText: t('common.cancel'),
    onOk: async () => {
      try {
        await deleteProjectApi(id);
        message.success(t('common.delete'));
        await loadProjects();
      } catch {
        // handled
      }
    },
  });
}

function openProject(p: NccProject) {
  router.push(`/admin/plugins/novus-crud-code/projects/${p.id}`);
}

onMounted(() => loadProjects());
</script>

<template>
  <Page auto-content-height>
    <div class="space-y-4">
      <!-- Header -->
      <section class="relative overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div class="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-primary/5" />
        <div class="relative flex items-center justify-between p-5">
          <div>
            <div class="mb-2 inline-flex items-center gap-1.5 rounded-full border bg-background/80 px-3 py-1 text-xs text-muted-foreground">
              <IconifyIcon icon="lucide:database-zap" class="h-3.5 w-3.5" />
              DataForge Studio
            </div>
            <h1 class="text-xl font-semibold text-foreground md:text-2xl">
              {{ t('project.subtitle') }}
            </h1>
          </div>
          <div class="flex items-center gap-3">
            <div class="hidden items-center gap-2 rounded-lg bg-background/60 px-3 py-1.5 sm:flex">
              <div class="flex h-6 w-6 items-center justify-center rounded bg-primary/10">
                <IconifyIcon icon="lucide:folder" class="h-3.5 w-3.5 text-primary" />
              </div>
              <span class="text-sm font-bold text-foreground">{{ total }}</span>
              <span class="text-xs text-muted-foreground">{{ t('project.totalProjects') }}</span>
            </div>
            <Button type="primary" @click="openCreate">
              <template #icon><IconifyIcon icon="lucide:plus" /></template>
              {{ t('project.create') }}
            </Button>
          </div>
        </div>
      </section>

      <!-- Search -->
      <div>
        <Input
          v-model:value="searchText"
          :placeholder="t('project.search')"
          allow-clear
          class="max-w-xs"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:search" class="h-4 w-4 text-muted-foreground" />
          </template>
        </Input>
      </div>

      <!-- Content -->
      <Spin :spinning="loading">
        <Empty
          v-if="!loading && filteredProjects.length === 0"
          :description="t('project.empty')"
          class="py-16"
        >
          <Button type="primary" @click="openCreate">{{ t('project.create') }}</Button>
        </Empty>

        <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <div
            v-for="p in filteredProjects"
            :key="p.id"
            class="group cursor-pointer overflow-hidden rounded-xl border bg-card transition-all hover:-translate-y-0.5 hover:shadow-md"
            @click="openProject(p)"
          >
            <!-- Card Header -->
            <div class="border-b px-4 py-3">
              <div class="flex items-center gap-3">
                <div
                  class="flex h-10 w-10 items-center justify-center rounded-xl shadow-sm"
                  :style="{ backgroundColor: `${p.color ?? '#6366f1'}18`, color: p.color ?? '#6366f1' }"
                >
                  <IconifyIcon icon="lucide:database" class="h-5 w-5" />
                </div>
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-semibold text-foreground">{{ p.display_name || p.name }}</div>
                  <div class="truncate font-mono text-[11px] text-muted-foreground">{{ p.name }}</div>
                </div>
                <div class="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100" @click.stop>
                  <button
                    class="inline-flex h-7 w-7 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                    @click="openEdit(p)"
                  >
                    <IconifyIcon icon="lucide:pencil" class="h-3.5 w-3.5" />
                  </button>
                  <button
                    class="inline-flex h-7 w-7 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                    @click="confirmDelete(p.id)"
                  >
                    <IconifyIcon icon="lucide:trash-2" class="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
            <!-- Card Body -->
            <div class="px-4 py-3">
              <p v-if="p.description" class="mb-3 line-clamp-2 text-xs text-muted-foreground">{{ p.description }}</p>
              <div class="flex items-center gap-3 text-[11px] text-muted-foreground">
                <span class="inline-flex items-center gap-1">
                  <IconifyIcon icon="lucide:calendar" class="h-3 w-3" />
                  {{ formatDate(p.created_at) }}
                </span>
                <span v-if="p.updated_at !== p.created_at" class="inline-flex items-center gap-1">
                  <IconifyIcon icon="lucide:clock" class="h-3 w-3" />
                  {{ t('project.updated') }}: {{ formatDate(p.updated_at) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </Spin>

      <!-- Create/Edit Modal -->
      <Modal
        v-model:open="showModal"
        :title="editItem ? t('project.edit') : t('project.create')"
        :confirm-loading="saving"
        :ok-text="t('common.save')"
        :cancel-text="t('common.cancel')"
        :ok-button-props="{ disabled: !form.name }"
        @ok="saveProject"
      >
        <div class="space-y-4 pt-2">
          <div>
            <div class="mb-1 text-sm font-medium text-foreground">
              {{ t('project.field.name') }} <span class="text-destructive">*</span>
            </div>
            <Input v-model:value="form.name" :placeholder="t('project.field.namePlaceholder')" />
          </div>
          <div>
            <div class="mb-1 text-sm font-medium text-foreground">{{ t('project.field.displayName') }}</div>
            <Input v-model:value="form.display_name" :placeholder="t('project.field.displayNamePlaceholder')" />
          </div>
          <div>
            <div class="mb-1 text-sm font-medium text-foreground">{{ t('project.field.description') }}</div>
            <Textarea v-model:value="form.description" :rows="2" />
          </div>
          <div>
            <div class="mb-1.5 text-sm font-medium text-foreground">{{ t('project.field.color') }}</div>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="c in COLOR_PRESETS"
                :key="c"
                type="button"
                class="h-7 w-7 rounded-full transition-all"
                :style="{ backgroundColor: c }"
                :class="form.color === c ? 'ring-2 ring-foreground ring-offset-2' : 'ring-1 ring-transparent hover:ring-muted-foreground'"
                @click="form.color = c"
              />
            </div>
          </div>
        </div>
      </Modal>
    </div>
  </Page>
</template>
