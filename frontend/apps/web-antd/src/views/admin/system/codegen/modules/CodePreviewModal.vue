<script lang="ts" setup>
/**
 * 代码预览弹窗 / Code Preview Modal
 *
 * 全屏 Modal (90vw, 80vh)，复用 FileTreePanel + CodePreviewPanel，底部下载 ZIP + 关闭
 */
import { useDebounceFn } from '@vueuse/core';
import { computed, ref, watch } from 'vue';

import { Button, Modal, Spin } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';

import { downloadCodegenPreviewZipApi, postCodegenPreviewApi } from '#/api/admin/codegen';
import type { PreviewFile } from '#/api/admin/codegen';
import { message } from 'ant-design-vue';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import CodePreviewPanel from './CodePreviewPanel.vue';
import FileTreePanel from './FileTreePanel.vue';

defineOptions({ name: 'CodePreviewModal' });

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ 'update:open': [boolean] }>();

const store = useCodegenBuilderStore();

const modalOpen = computed({
  get: () => props.open,
  set: (v) => emit('update:open', v),
});

const selectedFilePath = ref('');
const isLoading = ref(false);

watch(
  () => props.open,
  (open) => {
    if (open) selectedFilePath.value = '';
  },
);
const isDownloading = ref(false);
let fetchId = 0;

const previewFiles = computed<PreviewFile[]>(() => store.previewCache?.files ?? []);
const selectedFile = computed(() =>
  previewFiles.value.find((f) => f.path === selectedFilePath.value) ?? null,
);

async function fetchPreview() {
  const currentId = ++fetchId;
  isLoading.value = true;
  try {
    const result = await postCodegenPreviewApi({ config_json: store.configJson });
    if (currentId !== fetchId) return;
    if (!result.success && result.error) {
      store.setPreviewCache({ files: [], error: result.error });
    } else {
      store.setPreviewCache({
        files: result.files ?? [],
        summary: result.summary,
        conflicts: result.conflicts,
        timestamp: Date.now(),
      });
    }
    if (result.files?.length && !selectedFilePath.value) {
      selectedFilePath.value = result.files[0]?.path ?? '';
    }
  } catch (e) {
    if (currentId !== fetchId) return;
    store.setPreviewCache({
      files: [],
      error: e instanceof Error ? e.message : String(e),
    });
  } finally {
    if (currentId === fetchId) isLoading.value = false;
  }
}

function onSelectFile(path: string) {
  selectedFilePath.value = path;
}

async function onDownloadZip() {
  isDownloading.value = true;
  try {
    await downloadCodegenPreviewZipApi(
      { config_json: store.configJson },
      { step: undefined },
    );
    message.success($t('admin.system.codegen.messages.downloadSuccess'));
  } catch (e) {
    const err = e as { response?: { data?: { detail?: { error?: string } | string } } };
    const detail = err?.response?.data?.detail;
    const msg =
      (typeof detail === 'object' && detail?.error) ||
      (typeof detail === 'string' ? detail : null) ||
      $t('admin.system.codegen.messages.downloadFail');
    message.error(msg);
  } finally {
    isDownloading.value = false;
  }
}

const debouncedFetchPreview = useDebounceFn(fetchPreview, 200);

watch(
  () => props.open,
  (open) => {
    if (open) debouncedFetchPreview();
  },
);
</script>

<template>
  <Modal
    v-model:open="modalOpen"
    :title="$t('admin.system.codegen.preview.title')"
    :width="1280"
    :style="{ maxWidth: '90vw' }"
    :body-style="{ maxHeight: '80vh', overflow: 'auto' }"
    destroy-on-close
    :footer="null"
  >
    <Spin :spinning="isLoading">
      <div class="flex gap-4">
        <div class="w-64 shrink-0">
          <FileTreePanel
            :files="previewFiles"
            :selected-path="selectedFilePath"
            @select="onSelectFile"
          />
        </div>
        <div class="min-h-96 flex-1 border-l border-border pl-4">
          <CodePreviewPanel
            :selected-file="selectedFile"
            :preview-error="store.previewCache?.error"
          />
        </div>
      </div>
      <div class="mt-4 flex justify-end gap-2 border-t border-border pt-4">
        <Button type="primary" :loading="isDownloading" @click="onDownloadZip">
          <IconifyIcon icon="lucide:download" class="mr-1 size-4" />
          {{ $t('admin.system.codegen.generate.downloadZip') }}
        </Button>
        <Button type="default" @click="emit('update:open', false)">
          {{ $t('common.close') }}
        </Button>
      </div>
    </Spin>
  </Modal>
</template>
