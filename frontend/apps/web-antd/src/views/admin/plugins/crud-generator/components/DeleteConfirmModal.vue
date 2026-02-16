<script setup lang="ts">
import { computed, ref } from 'vue';

import { Alert, Button, Collapse, Modal, Spin, Tag, message } from 'ant-design-vue';

import { deleteGeneratedFilesApi } from '#/api/admin/crud-records';
import { $t } from '#/locales';

import type { CrudConfig } from '../types';

interface Props {
  config: CrudConfig;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  deleted: [count: number];
}>();

const visible = ref(false);
const loading = ref(false);
const deleting = ref(false);
const previewFiles = ref<Array<{ path: string; exists: boolean }>>([]);

const existingFiles = computed(() =>
  previewFiles.value.filter((f) => f.exists),
);

const groupedFiles = computed(() => {
  const groups: Record<string, Array<{ path: string; exists: boolean }>> = {};
  for (const f of existingFiles.value) {
    const parts = f.path.split('/');
    const dir = parts.length > 1 ? parts.slice(0, 2).join('/') : '.';
    if (!groups[dir]) groups[dir] = [];
    groups[dir].push(f);
  }
  return groups;
});

const activeKeys = computed(() => Object.keys(groupedFiles.value));

async function open() {
  visible.value = true;
  loading.value = true;
  previewFiles.value = [];

  try {
    const res = await deleteGeneratedFilesApi({
      mode: 'entity',
      module_name: props.config.module,
      table_name: props.config.table_name,
      config: props.config,
      dry_run: true,
    });
    previewFiles.value = res.files || [];
  } catch {
    message.error($t('admin.dev.crudGenerator.deleteFiles.previewFailed'));
  } finally {
    loading.value = false;
  }
}

async function confirmDelete() {
  deleting.value = true;
  try {
    const res = await deleteGeneratedFilesApi({
      mode: 'entity',
      module_name: props.config.module,
      table_name: props.config.table_name,
      config: props.config,
      dry_run: false,
    });
    const count = res.total_deleted || 0;
    message.success(
      $t('admin.dev.crudGenerator.deleteFiles.success', { count }),
    );
    emit('deleted', count);
    visible.value = false;
  } catch {
    message.error($t('admin.dev.crudGenerator.deleteFiles.failed'));
  } finally {
    deleting.value = false;
  }
}

defineExpose({ open });
</script>

<template>
  <Modal
    v-model:open="visible"
    :title="$t('admin.dev.crudGenerator.deleteFiles.title')"
    :width="600"
    :footer="null"
    destroy-on-close
  >
    <Spin :spinning="loading">
      <div v-if="!loading" class="space-y-4">
        <!-- Summary -->
        <Alert
          type="warning"
          show-icon
          :message="
            $t('admin.dev.crudGenerator.deleteFiles.warning', {
              module: config.module,
              table: config.table_name,
            })
          "
        />

        <div class="text-muted-foreground flex items-center gap-4 text-sm">
          <span>
            {{ $t('admin.dev.crudGenerator.deleteFiles.totalFiles') }}:
            <strong>{{ previewFiles.length }}</strong>
          </span>
          <span>
            {{ $t('admin.dev.crudGenerator.deleteFiles.existing') }}:
            <strong class="text-destructive">
              {{ existingFiles.length }}
            </strong>
          </span>
        </div>

        <!-- File list grouped by directory -->
        <div
          v-if="existingFiles.length > 0"
          class="max-h-[350px] overflow-y-auto"
        >
          <Collapse :active-key="activeKeys" size="small">
            <Collapse.Panel
              v-for="(files, dir) in groupedFiles"
              :key="dir"
              :header="`${dir}/ (${files.length})`"
            >
              <div
                v-for="f in files"
                :key="f.path"
                class="flex items-center gap-2 py-0.5 font-mono text-xs"
              >
                <Tag v-if="f.exists" color="red" class="!m-0 !text-[10px]">
                  {{ $t('common.delete') }}
                </Tag>
                <span class="text-muted-foreground truncate">
                  {{ f.path }}
                </span>
              </div>
            </Collapse.Panel>
          </Collapse>
        </div>

        <div
          v-else
          class="text-muted-foreground rounded-lg border border-dashed p-6 text-center"
        >
          {{ $t('admin.dev.crudGenerator.deleteFiles.noFiles') }}
        </div>

        <!-- Actions -->
        <div class="flex justify-end gap-2 border-t pt-3">
          <Button @click="visible = false">
            {{ $t('common.cancel') }}
          </Button>
          <Button
            danger
            type="primary"
            :disabled="existingFiles.length === 0"
            :loading="deleting"
            @click="confirmDelete"
          >
            <template #icon>
              <span class="icon-[lucide--trash-2] size-3.5" />
            </template>
            {{
              $t('admin.dev.crudGenerator.deleteFiles.confirm', {
                count: existingFiles.length,
              })
            }}
          </Button>
        </div>
      </div>
    </Spin>
  </Modal>
</template>
