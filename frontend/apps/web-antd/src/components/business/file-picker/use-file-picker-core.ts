import type {
  AttachmentListQueryParams,
  FilePickerProps,
  UploadRules,
  UploadTask,
} from './types';

import type { AttachmentInfo } from '#/types/attachment';

import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import { useVbenModal } from '@vben/common-ui';

import { message } from 'ant-design-vue';

import {
  batchUploadAttachmentsApi as adminBatchUploadApi,
  getAttachmentListApi as adminGetAttachmentListApi,
  getUploadRulesApi as adminGetUploadRulesApi,
  smartUploadFile as adminSmartUploadFile,
} from '#/api/admin/attachment';
import {
  batchUploadAttachmentsApi as tenantBatchUploadApi,
  getAttachmentListApi as tenantGetAttachmentListApi,
  getUploadRulesApi as tenantGetUploadRulesApi,
  smartUploadFile as tenantSmartUploadFile,
} from '#/api/tenant/attachment';
import { $t } from '#/locales';
import { formatFileSize } from '#/utils/file';
import { getAttachmentUrl } from '#/utils/image';

interface UseFilePickerCoreOptions {
  onSelect: (files: AttachmentInfo[]) => void;
  props: Pick<FilePickerProps, 'endpoint'> &
    Required<Omit<FilePickerProps, 'endpoint'>>;
}

interface UploadRequestPayload {
  file: File;
  onSuccess?: (body?: unknown) => void;
}

type UploadProgress = { percent: number };
type UploadSignalOptions = { signal: AbortSignal };

const BATCH_SIZE_THRESHOLD = 5 * 1024 * 1024;
const BATCH_MAX_FILES = 20;

function isUploadRequestPayload(value: unknown): value is UploadRequestPayload {
  return (
    typeof value === 'object' &&
    value !== null &&
    'file' in value &&
    (value as { file: unknown }).file instanceof File
  );
}

export function useFilePickerCore(options: UseFilePickerCoreOptions) {
  const { onSelect, props } = options;

  const resolvedEndpoint = computed(() => {
    if (props.endpoint) return props.endpoint;
    return window.location.pathname.startsWith('/admin') ? 'admin' : 'tenant';
  });

  const uploadRules = ref<null | UploadRules>(null);
  const uploadRulesLoaded = ref(false);
  const effectiveMaxFileSize = computed(() => {
    if (uploadRules.value) {
      return uploadRules.value.maxFileSizeMb * 1024 * 1024;
    }
    return props.maxFileSize;
  });

  async function loadUploadRules() {
    if (uploadRulesLoaded.value) return;
    try {
      const api =
        resolvedEndpoint.value === 'admin'
          ? adminGetUploadRulesApi
          : tenantGetUploadRulesApi;
      const rules = await api();
      uploadRules.value = {
        allowedExtensions: rules.allowed_extensions ?? '',
        deniedExtensions: rules.denied_extensions ?? '',
        maxFileSizeMb: rules.max_file_size_mb ?? 100,
      };
      uploadRulesLoaded.value = true;
    } catch {
      //
    }
  }

  const [Modal, modalApi] = useVbenModal({
    onOpenChange: (isOpen) => {
      if (isOpen) {
        void loadFiles();
        void loadUploadRules();
      }
    },
  });

  const loading = ref(false);
  const uploading = ref(false);
  const files = ref<AttachmentInfo[]>([]);
  const selectedIds = ref<Set<number>>(new Set());
  const searchKeyword = ref('');
  const categoryFilter = ref<string>('');
  const currentPage = ref(1);
  const pageSize = ref(18);
  const total = ref(0);
  const viewMode = ref<'grid' | 'list'>('grid');
  const isDragOver = ref(false);
  let dragCounter = 0;
  const uploadTasks = ref<UploadTask[]>([]);
  const previewVisible = ref(false);
  const previewUrl = ref('');

  const uploadingCount = computed(
    () =>
      uploadTasks.value.filter((task) => task.status === 'uploading').length,
  );
  const errorCount = computed(
    () => uploadTasks.value.filter((task) => task.status === 'error').length,
  );

  const acceptMimeFilter = computed(() => {
    if (!props.accept || props.accept === '*') return '';
    const parts = props.accept.split(',').map((item) => item.trim());
    const mimeWild = parts.find((item) => item.endsWith('/*'));
    if (mimeWild) return mimeWild.replace('/*', '');
    return '';
  });

  const showCategoryFilter = computed(
    () => !props.imageOnly && !acceptMimeFilter.value,
  );

  const categoryOptions = computed(() => [
    { label: $t('shared.filePicker.allCategories'), value: '' },
    { label: $t('shared.filePicker.categories.image'), value: 'image' },
    { label: $t('shared.filePicker.categories.document'), value: 'document' },
    { label: $t('shared.filePicker.categories.video'), value: 'video' },
    { label: $t('shared.filePicker.categories.audio'), value: 'audio' },
    { label: $t('shared.filePicker.categories.archive'), value: 'archive' },
    { label: $t('shared.filePicker.categories.other'), value: 'other' },
  ]);

  const selectedFiles = computed(() =>
    files.value.filter((file) => selectedIds.value.has(file.id)),
  );

  function isImage(file: AttachmentInfo): boolean {
    return file.category === 'image' || !!file.mimeType?.startsWith('image/');
  }

  function getPreviewUrl(file: AttachmentInfo): null | string {
    if (!isImage(file)) return null;
    return getAttachmentUrl(file, {
      preset: 'thumb',
      format: 'webp',
      quality: 75,
    });
  }

  function getFullPreviewUrl(file: AttachmentInfo): null | string {
    if (!isImage(file)) return null;
    return getAttachmentUrl(file);
  }

  function openPreview(file: AttachmentInfo) {
    const url = getFullPreviewUrl(file);
    if (!url) return;
    previewUrl.value = url;
    previewVisible.value = true;
  }

  async function loadFiles() {
    loading.value = true;
    try {
      const params: AttachmentListQueryParams = {
        page: currentPage.value,
        page_size: pageSize.value,
        sort: '-created_at',
      };
      if (searchKeyword.value) {
        params['filter[name][ilike]'] = searchKeyword.value;
      }
      if (categoryFilter.value) {
        params['filter[mime_type][ilike]'] = `${categoryFilter.value}/`;
      } else if (props.imageOnly) {
        params['filter[mime_type][ilike]'] = 'image/';
      } else if (acceptMimeFilter.value) {
        params['filter[mime_type][ilike]'] = `${acceptMimeFilter.value}/`;
      }
      const listApi =
        resolvedEndpoint.value === 'admin'
          ? adminGetAttachmentListApi
          : tenantGetAttachmentListApi;
      const result = await listApi(params);
      files.value = result.items;
      total.value = result.total;
    } catch {
      //
    } finally {
      loading.value = false;
    }
  }

  function handleSearch() {
    currentPage.value = 1;
    void loadFiles();
  }

  function handleCategoryChange() {
    currentPage.value = 1;
    void loadFiles();
  }

  function handlePageChange(page: number) {
    currentPage.value = page;
    void loadFiles();
  }

  function handleFileClick(file: AttachmentInfo) {
    if (props.multiple) {
      if (selectedIds.value.has(file.id)) {
        selectedIds.value.delete(file.id);
      } else if (selectedIds.value.size < props.maxCount) {
        selectedIds.value.add(file.id);
      } else {
        message.warning(
          $t('shared.filePicker.maxCountExceeded', { count: props.maxCount }),
        );
      }
      selectedIds.value = new Set(selectedIds.value);
      return;
    }
    onSelect([file]);
    modalApi.close();
  }

  function validateFile(file: File): null | string {
    const maxSize = effectiveMaxFileSize.value;
    if (file.size > maxSize) {
      return $t('shared.filePicker.fileTooLarge', {
        maxSize: formatFileSize(maxSize),
      });
    }
    if (props.imageOnly && !file.type.startsWith('image/')) {
      return $t('shared.filePicker.onlyImages');
    }
    if (!file.name?.trim()) {
      return $t('shared.filePicker.invalidFileName');
    }
    if (!uploadRules.value) return null;

    const extension = file.name.includes('.')
      ? (file.name.split('.').pop()?.toLowerCase() ?? '')
      : '';
    if (!extension) return null;
    const allowed = uploadRules.value.allowedExtensions
      .split(',')
      .map((item) => item.trim().toLowerCase().replace(/^\./, ''))
      .filter(Boolean);
    if (allowed.length > 0 && !allowed.includes(extension)) {
      return $t('shared.filePicker.extensionNotAllowed', { ext: extension });
    }
    const denied = uploadRules.value.deniedExtensions
      .split(',')
      .map((item) => item.trim().toLowerCase().replace(/^\./, ''))
      .filter(Boolean);
    if (denied.includes(extension)) {
      return $t('shared.filePicker.extensionDenied', { ext: extension });
    }
    return null;
  }

  async function executeUploadTask(task: UploadTask): Promise<void> {
    task.status = 'uploading';
    task.percent = 0;
    task.abortController = new AbortController();
    try {
      const uploadFn =
        resolvedEndpoint.value === 'admin'
          ? (
              payload: { file: File; visibility: string },
              onProgress: (progress: UploadProgress) => void,
              requestOptions: UploadSignalOptions,
            ) =>
              adminSmartUploadFile(
                {
                  file: payload.file,
                  tenant_id: 0,
                  visibility: payload.visibility as 'private' | 'public',
                },
                onProgress,
                requestOptions,
              )
          : tenantSmartUploadFile;
      const result = await uploadFn(
        { file: task.file, visibility: props.visibility },
        (progress) => {
          task.percent = progress.percent;
        },
        { signal: task.abortController.signal },
      );
      task.status = 'success';
      task.percent = 100;
      if (!result.attachment?.id) return;
      if (!props.multiple) selectedIds.value.clear();
      if (selectedIds.value.size < props.maxCount) {
        selectedIds.value.add(result.attachment.id);
        selectedIds.value = new Set(selectedIds.value);
      }
    } catch (error: unknown) {
      const err = error as Error & { name?: string };
      if (err.name === 'AbortError') return;
      if (task.retryCount < props.maxRetries) {
        task.retryCount += 1;
        task.status = 'pending';
        await new Promise((resolve) => {
          setTimeout(resolve, 1000 * task.retryCount);
        });
        return executeUploadTask(task);
      }
      task.status = 'error';
      task.error = err.message || $t('shared.filePicker.uploadFailed');
    } finally {
      task.abortController = undefined;
      await nextTick();
      checkAllUploadsComplete();
    }
  }

  function checkAllUploadsComplete() {
    const hasActiveTask = uploadTasks.value.some(
      (task) => task.status === 'uploading' || task.status === 'pending',
    );
    if (hasActiveTask) return;
    if (uploadTasks.value.some((task) => task.status === 'error')) return;
    uploading.value = false;
    setTimeout(() => {
      uploadTasks.value = [];
      void loadFiles();
    }, 600);
  }

  function processQueue() {
    const activeCount = uploadTasks.value.filter(
      (task) => task.status === 'uploading',
    ).length;
    const pendingTasks = uploadTasks.value.filter(
      (task) => task.status === 'pending',
    );
    if (activeCount >= props.maxConcurrency || pendingTasks.length === 0)
      return;
    for (const task of pendingTasks.slice(
      0,
      props.maxConcurrency - activeCount,
    )) {
      void executeUploadTask(task).finally(() => processQueue());
    }
  }

  async function executeBatchUpload(batchFiles: File[]): Promise<void> {
    const batchTasks: UploadTask[] = batchFiles.map((file) => ({
      uid: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      file,
      name: file.name,
      size: file.size,
      status: 'uploading',
      percent: 50,
      retryCount: 0,
    }));
    uploadTasks.value.unshift(...batchTasks);
    try {
      const batchApi =
        resolvedEndpoint.value === 'admin'
          ? (payload: { files: File[]; visibility?: 'private' | 'public' }) =>
              adminBatchUploadApi({ ...payload, tenant_id: 0 })
          : tenantBatchUploadApi;

      const result = await batchApi({
        files: batchFiles,
        visibility: props.visibility,
      });
      for (let i = 0; i < result.items.length; i += 1) {
        const item = result.items[i];
        const task = batchTasks[i];
        if (!item || !task) continue;
        if (item.success) {
          task.status = 'success';
          task.percent = 100;
          if (item.attachment?.id) {
            if (!props.multiple) selectedIds.value.clear();
            if (selectedIds.value.size < props.maxCount) {
              selectedIds.value.add(item.attachment.id);
              selectedIds.value = new Set(selectedIds.value);
            }
          }
          continue;
        }
        task.status = 'error';
        task.error = item.error ?? $t('shared.filePicker.uploadFailed');
      }
    } catch (error: unknown) {
      const messageText =
        (error as Error).message ?? $t('shared.filePicker.uploadFailed');
      for (const task of batchTasks) {
        if (task.status === 'uploading') {
          task.status = 'error';
          task.error = messageText;
        }
      }
    } finally {
      await nextTick();
      checkAllUploadsComplete();
    }
  }

  function addFilesToQueue(fileList: File[]) {
    const validFiles: File[] = [];
    for (const file of fileList) {
      const errorText = validateFile(file);
      if (errorText) {
        message.error(`${file.name}: ${errorText}`);
        continue;
      }
      validFiles.push(file);
    }
    if (validFiles.length === 0) return;

    const smallFiles = validFiles.filter(
      (file) => file.size <= BATCH_SIZE_THRESHOLD,
    );
    const largeFiles = validFiles.filter(
      (file) => file.size > BATCH_SIZE_THRESHOLD,
    );

    for (const file of largeFiles) {
      uploadTasks.value.unshift({
        uid: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
        file,
        name: file.name,
        size: file.size,
        status: 'pending',
        percent: 0,
        retryCount: 0,
      });
    }
    uploading.value = true;

    if (smallFiles.length >= 2) {
      for (let i = 0; i < smallFiles.length; i += BATCH_MAX_FILES) {
        const chunk = smallFiles.slice(i, i + BATCH_MAX_FILES);
        void executeBatchUpload(chunk).finally(() => processQueue());
      }
    } else {
      for (const file of smallFiles) {
        uploadTasks.value.unshift({
          uid: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
          file,
          name: file.name,
          size: file.size,
          status: 'pending',
          percent: 0,
          retryCount: 0,
        });
      }
    }

    if (uploadTasks.value.some((task) => task.status === 'pending')) {
      processQueue();
    }
  }

  function handleCustomUpload(options: unknown) {
    if (!isUploadRequestPayload(options)) {
      return;
    }
    const payload = options;
    addFilesToQueue([payload.file]);
    payload.onSuccess?.();
  }

  function cancelTask(task: UploadTask) {
    if (task.status === 'uploading' && task.abortController) {
      task.abortController.abort();
    }
    task.status = 'cancelled';
  }

  function retryTask(task: UploadTask) {
    if (task.status !== 'error' && task.status !== 'cancelled') return;
    task.status = 'pending';
    task.percent = 0;
    task.error = undefined;
    task.retryCount = 0;
    processQueue();
  }

  function clearCompletedTasks() {
    uploadTasks.value = uploadTasks.value.filter(
      (task) =>
        task.status === 'uploading' ||
        task.status === 'pending' ||
        task.status === 'error',
    );
  }

  function clearErrors() {
    uploadTasks.value = uploadTasks.value.filter(
      (task) => task.status !== 'error',
    );
  }

  function retryAllErrors() {
    uploadTasks.value
      .filter((task) => task.status === 'error')
      .forEach((task) => retryTask(task));
  }

  function hasFiles(event: DragEvent) {
    return !!event.dataTransfer?.types?.includes('Files');
  }

  function onModalDragEnter(event: DragEvent) {
    if (!hasFiles(event)) return;
    dragCounter += 1;
    isDragOver.value = true;
  }

  function onModalDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
  }

  function onModalDragLeave() {
    dragCounter -= 1;
    if (dragCounter > 0) return;
    dragCounter = 0;
    isDragOver.value = false;
  }

  function onModalDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    dragCounter = 0;
    isDragOver.value = false;
    const droppedFiles = event.dataTransfer?.files;
    if (droppedFiles?.length) {
      addFilesToQueue([...droppedFiles]);
    }
  }

  function onWindowDragOver(event: DragEvent) {
    event.preventDefault();
  }

  window.addEventListener('dragover', onWindowDragOver);
  onBeforeUnmount(() =>
    window.removeEventListener('dragover', onWindowDragOver),
  );

  function handleConfirm() {
    onSelect(selectedFiles.value);
    modalApi.close();
  }

  watch(
    () => modalApi.getData(),
    () => {
      selectedIds.value.clear();
      searchKeyword.value = '';
      categoryFilter.value = '';
      currentPage.value = 1;
    },
  );

  return {
    Modal,
    acceptMimeFilter,
    cancelTask,
    categoryFilter,
    categoryOptions,
    clearCompletedTasks,
    clearErrors,
    currentPage,
    effectiveMaxFileSize,
    errorCount,
    files,
    handleCategoryChange,
    handleConfirm,
    handleCustomUpload,
    handleFileClick,
    handlePageChange,
    handleSearch,
    isDragOver,
    isImage,
    loadFiles,
    loading,
    modalApi,
    onModalDragEnter,
    onModalDragLeave,
    onModalDragOver,
    onModalDrop,
    openPreview,
    pageSize,
    previewUrl,
    previewVisible,
    resolvedEndpoint,
    retryAllErrors,
    retryTask,
    searchKeyword,
    selectedFiles,
    selectedIds,
    showCategoryFilter,
    total,
    uploadTasks,
    uploading,
    uploadingCount,
    viewMode,
    getPreviewUrl,
  };
}
