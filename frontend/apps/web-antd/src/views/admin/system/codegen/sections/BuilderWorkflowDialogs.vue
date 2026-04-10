<script lang="ts" setup>
import type { GenerateResultPayload } from '../composables/use-codegen-builder-workflows';

import type { CodegenVersionItem } from '#/api/admin/codegen';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Collapse,
  CollapsePanel,
  Input,
  List,
  Modal,
  Tooltip,
} from 'ant-design-vue';

import { formatDate } from '#/utils/common';

const props = defineProps<{
  closeResultModal: () => void;
  formatConflictItem: (conflict: unknown) => string;
  formatVersionTime: (iso: null | string) => string;
  hasPreviewSnapshot: boolean;
  importYamlText: string;
  importYamlVisible: boolean;
  isImporting: boolean;
  isRestoring: boolean;
  isVersionLoading: boolean;
  lastResult: GenerateResultPayload | null;
  onConfirmImportYaml: () => Promise<void> | void;
  onImportYamlFile: (event: Event) => void;
  onPreviewVersion: (version: CodegenVersionItem) => Promise<void> | void;
  onRestoreVersion: (version: CodegenVersionItem) => Promise<void> | void;
  openPreviewFromResult: () => void;
  resultModalVisible: boolean;
  resultNextSteps: string[];
  versionHistoryVisible: boolean;
  versionList: CodegenVersionItem[];
  versionPreviewContent: string;
  versionPreviewLoadingIds: Set<number>;
  versionPreviewNote: string;
  versionPreviewVisible: boolean;
}>();

const emit = defineEmits<{
  'update:importYamlText': [value: string];
  'update:importYamlVisible': [value: boolean];
  'update:resultModalVisible': [value: boolean];
  'update:versionHistoryVisible': [value: boolean];
  'update:versionPreviewVisible': [value: boolean];
}>();

const importYamlOpen = computed({
  get: () => props.importYamlVisible,
  set: (value: boolean) => emit('update:importYamlVisible', value),
});

const importYamlDraft = computed({
  get: () => props.importYamlText,
  set: (value: string) => emit('update:importYamlText', value),
});

const versionHistoryOpen = computed({
  get: () => props.versionHistoryVisible,
  set: (value: boolean) => emit('update:versionHistoryVisible', value),
});

const versionPreviewOpen = computed({
  get: () => props.versionPreviewVisible,
  set: (value: boolean) => emit('update:versionPreviewVisible', value),
});

const resultModalOpen = computed({
  get: () => props.resultModalVisible,
  set: (value: boolean) => emit('update:resultModalVisible', value),
});
</script>

<template>
  <Modal
    v-model:open="importYamlOpen"
    :title="$t('admin.system.codegen.builder.importYamlTitle')"
    :ok-text="$t('common.confirm')"
    :cancel-text="$t('common.cancel')"
    :confirm-loading="isImporting"
    @ok="onConfirmImportYaml"
  >
    <div class="flex flex-col gap-2">
      <Input.TextArea
        v-model:value="importYamlDraft"
        :placeholder="$t('admin.system.codegen.builder.importYamlPlaceholder')"
        :rows="12"
        class="font-mono text-sm"
      />
      <label
        class="inline-flex cursor-pointer items-center gap-1 text-sm text-muted-foreground underline"
      >
        <input
          type="file"
          accept=".yaml,.yml"
          class="sr-only"
          @change="onImportYamlFile"
        />
        <IconifyIcon icon="lucide:upload" class="size-4" />
        <span>{{
          $t('admin.system.codegen.builder.importYamlSelectFile')
        }}</span>
      </label>
    </div>
  </Modal>

  <Modal
    v-model:open="versionHistoryOpen"
    :title="$t('admin.system.codegen.builder.versionHistoryTitle')"
    :footer="null"
    width="520"
  >
    <div
      v-if="!isVersionLoading && versionList.length === 0"
      class="py-8 text-center text-muted-foreground"
    >
      {{ $t('admin.system.codegen.builder.versionEmpty') }}
    </div>
    <List
      v-else
      :loading="isVersionLoading"
      :data-source="versionList"
      size="small"
      class="max-h-80 overflow-y-auto"
    >
      <template #renderItem="{ item }">
        <List.Item class="flex items-center justify-between">
          <div class="flex flex-col gap-0.5">
            <Tooltip :title="formatDate(item.created_at)">
              <span class="text-sm">
                {{ formatVersionTime(item.created_at) }}
              </span>
            </Tooltip>
            <span v-if="item.note" class="text-xs text-muted-foreground">
              {{ item.note }}
            </span>
          </div>
          <div class="flex gap-0">
            <Button
              type="link"
              size="small"
              :loading="versionPreviewLoadingIds.has(item.id)"
              @click="onPreviewVersion(item)"
            >
              {{ $t('admin.system.codegen.builder.versionPreview') }}
            </Button>
            <Button
              type="link"
              size="small"
              :loading="isRestoring"
              @click="onRestoreVersion(item)"
            >
              {{ $t('admin.system.codegen.builder.versionRestore') }}
            </Button>
          </div>
        </List.Item>
      </template>
    </List>
  </Modal>

  <Modal
    v-model:open="versionPreviewOpen"
    :title="$t('admin.system.codegen.builder.versionPreviewTitle')"
    :footer="null"
    width="640"
  >
    <div v-if="versionPreviewNote" class="mb-2 text-sm text-muted-foreground">
      {{ versionPreviewNote }}
    </div>
    <div
      v-if="versionPreviewLoadingIds.size > 0"
      class="py-8 text-center text-muted-foreground"
    >
      {{ $t('common.loading') }}
    </div>
    <Input.TextArea
      v-else
      :value="versionPreviewContent"
      readonly
      :rows="18"
      class="font-mono text-sm"
    />
  </Modal>

  <Modal
    v-model:open="resultModalOpen"
    :title="$t('admin.system.codegen.generate.resultTitle')"
    :footer="null"
    width="520"
  >
    <template v-if="lastResult">
      <div
        v-if="lastResult.conflicts?.length && !lastResult.success"
        class="mb-4"
      >
        <Alert
          type="warning"
          show-icon
          :message="$t('admin.system.codegen.generate.partialWriteTitle')"
        >
          <template #description>
            <p class="mb-2">
              {{ $t('admin.system.codegen.generate.partialWriteDesc') }}
            </p>
            <ul class="list-inside list-disc text-sm">
              <li
                v-for="(conflict, index) in lastResult.conflicts"
                :key="index"
              >
                {{ formatConflictItem(conflict) }}
              </li>
            </ul>
          </template>
        </Alert>
      </div>
      <div v-if="lastResult.errors?.length" class="mb-4">
        <Alert type="error" :message="lastResult.errors.join(', ')" />
      </div>
      <div v-if="lastResult.migration" class="mb-4">
        <Alert
          :type="lastResult.migration.success ? 'success' : 'error'"
          :message="
            lastResult.migration.success
              ? lastResult.migration.message ||
                $t('admin.system.codegen.generate.migrationSuccess')
              : lastResult.migration.error ||
                $t('admin.system.codegen.generate.migrationFailed')
          "
          show-icon
        />
        <p
          v-if="lastResult.migration.migration_path"
          class="mt-1 text-xs text-muted-foreground"
        >
          {{ lastResult.migration.migration_path }}
        </p>
      </div>
      <Collapse
        v-if="
          lastResult.success ||
          lastResult.files_created?.length ||
          lastResult.files_modified?.length
        "
      >
        <CollapsePanel
          key="files"
          :header="
            $t('admin.system.codegen.generate.fileCountHeader', {
              create: lastResult.files_created?.length ?? 0,
              modify: lastResult.files_modified?.length ?? 0,
            })
          "
        >
          <div class="max-h-48 overflow-y-auto text-sm">
            <div
              v-for="path in lastResult.files_created"
              :key="`create-${path}`"
              class="text-green-600"
            >
              + {{ path }}
            </div>
            <div
              v-for="path in lastResult.files_modified"
              :key="`modify-${path}`"
              class="text-amber-600"
            >
              ~ {{ path }}
            </div>
          </div>
        </CollapsePanel>
      </Collapse>
      <div class="mt-4 rounded border border-border p-3">
        <h5 class="mb-2 font-medium">
          {{ $t('admin.system.codegen.generate.nextSteps') }}
        </h5>
        <ul class="list-inside list-decimal space-y-1 text-sm">
          <li v-for="step in resultNextSteps" :key="step">
            {{ $t(`admin.system.codegen.generate.${step}`) }}
          </li>
        </ul>
      </div>
      <div class="mt-4 flex justify-end gap-2">
        <Button
          v-if="hasPreviewSnapshot"
          v-access:code="['action.codegen.preview']"
          type="primary"
          ghost
          @click="openPreviewFromResult"
        >
          {{ $t('admin.system.codegen.toolbar.preview') }}
        </Button>
        <Button @click="closeResultModal">
          {{ $t('common.close') }}
        </Button>
      </div>
    </template>
  </Modal>
</template>
