<script setup lang="ts">
/**
 * File Picker - supports selecting existing attachments or uploading new files
 * 附件选择器 - 支持选择已有附件或上传新文件
 */
import type { AttachmentInfo } from '#/types/attachment';

import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import { useVbenModal } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Checkbox,
  Col,
  Image,
  Input,
  message,
  Pagination,
  Progress,
  Row,
  Select,
  Spin,
  Tag,
  Tooltip,
  Upload,
} from 'ant-design-vue';

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
import { formatDate } from '#/utils/common';
import { formatFileSize, getFileIcon } from '#/utils/file';
import { getAttachmentUrl } from '#/utils/image';

defineOptions({ name: 'FilePicker' });

const props = withDefaults(
  defineProps<{
    accept?: string;
    /** API endpoint type: admin uses platform attachment API, tenant uses tenant attachment API. Auto-detected from URL by default. / API 端类型：admin 使用平台附件 API，tenant 使用租户附件 API。默认根据 URL 自动检测。 */
    endpoint?: 'admin' | 'tenant';
    imageOnly?: boolean;
    maxConcurrency?: number;
    maxCount?: number;
    maxFileSize?: number;
    maxRetries?: number;
    multiple?: boolean;
  }>(),
  {
    multiple: false,
    accept: '*',
    endpoint: undefined,
    maxCount: 10,
    imageOnly: false,
    maxFileSize: 100 * 1024 * 1024,
    maxConcurrency: 3,
    maxRetries: 2,
  },
);

const emit = defineEmits<{
  (e: 'select', files: AttachmentInfo[]): void;
}>();

/** Resolve actual endpoint type: prefer prop, otherwise auto-detect from URL / 解析实际使用的端类型：优先 prop，否则从 URL 自动检测 */
const resolvedEndpoint = computed(() => {
  if (props.endpoint) return props.endpoint;
  return window.location.pathname.startsWith('/admin') ? 'admin' : 'tenant';
});

interface UploadTask {
  uid: string;
  file: File;
  name: string;
  size: number;
  status: 'cancelled' | 'error' | 'pending' | 'success' | 'uploading';
  percent: number;
  error?: string;
  retryCount: number;
  abortController?: AbortController;
}

/** Server-side upload rules (dynamically loaded) / 服务端上传规则（动态加载） */
interface UploadRules {
  allowedExtensions: string;
  deniedExtensions: string;
  maxFileSizeMb: number;
}

const uploadRules = ref<UploadRules | null>(null);
const uploadRulesLoaded = ref(false);

/** Dynamically calculate max file size: prefer server rules, then prop / 动态计算最大文件大小：优先服务端规则，其次 prop */
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
    // Use prop defaults on load failure / 加载失败时使用 prop 默认值
  }
}

const [Modal, modalApi] = useVbenModal({
  onOpenChange: (isOpen) => {
    if (isOpen) {
      loadFiles();
      loadUploadRules();
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
  () => uploadTasks.value.filter((t) => t.status === 'uploading').length,
);
const errorCount = computed(
  () => uploadTasks.value.filter((t) => t.status === 'error').length,
);

/**
 * Extract MIME major type from accept prop for backend filtering
 * e.g. 'image/*' → 'image', 'video/*' → 'video'
 * Non-wildcard formats (e.g. 'application/pdf,.docx') return empty, no auto-filtering
 * 从 accept prop 中提取 MIME 大类用于后端筛选
 */
const acceptMimeFilter = computed(() => {
  if (!props.accept || props.accept === '*') return '';
  const parts = props.accept.split(',').map((s) => s.trim());
  const mimeWild = parts.find((p) => p.endsWith('/*'));
  if (mimeWild) return mimeWild.replace('/*', '');
  return '';
});

/** When imageOnly or accept specifies a type, hide category dropdown filter / 当 imageOnly 或 accept 指定了类型时，隐藏分类下拉筛选器 */
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
  files.value.filter((f) => selectedIds.value.has(f.id)),
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

/** Get original image URL (for zoom preview), no preset returns original size / 获取原图 URL（用于放大预览），不传 preset 返回原始尺寸 */
function getFullPreviewUrl(file: AttachmentInfo): null | string {
  if (!isImage(file)) return null;
  return getAttachmentUrl(file);
}

function openPreview(file: AttachmentInfo) {
  const url = getFullPreviewUrl(file);
  if (url) {
    previewUrl.value = url;
    previewVisible.value = true;
  }
}

// ============ Data loading / 数据加载 ============

async function loadFiles() {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: pageSize.value,
      sort: '-created_at',
    };
    if (searchKeyword.value) {
      params['filter[name][ilike]'] = searchKeyword.value;
    }
    // Filter by category/file type: prefer user-selected category, then imageOnly, finally MIME type from accept prop / 按分类/文件类型筛选：优先用户选择的分类，其次 imageOnly，最后 accept prop 推导的 MIME 大类
    // Uses ilike operator, backend auto-wraps with %...%, no need for manual wildcards
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
  loadFiles();
}

function handleCategoryChange() {
  currentPage.value = 1;
  loadFiles();
}

function handlePageChange(page: number) {
  currentPage.value = page;
  loadFiles();
}

// ============ File selection / 文件选择 ============

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
  } else {
    emit('select', [file]);
    modalApi.close();
  }
}

// ============ Upload / 上传 ============

function validateFile(file: File): null | string {
  const maxSize = effectiveMaxFileSize.value;
  if (file.size > maxSize)
    return $t('shared.filePicker.fileTooLarge', {
      maxSize: formatFileSize(maxSize),
    });
  if (props.imageOnly && !file.type.startsWith('image/'))
    return $t('shared.filePicker.onlyImages');
  if (!file.name?.trim()) return $t('shared.filePicker.invalidFileName');

  // Server-side extension whitelist/blacklist validation / 服务端扩展名白/黑名单校验
  if (uploadRules.value) {
    const ext = file.name.includes('.')
      ? file.name.split('.').pop()!.toLowerCase()
      : '';
    if (ext) {
      const { allowedExtensions, deniedExtensions } = uploadRules.value;
      if (allowedExtensions) {
        const allowed = allowedExtensions
          .split(',')
          .map((s) => s.trim().toLowerCase().replace(/^\./, ''));
        if (allowed.length > 0 && !allowed.includes(ext)) {
          return $t('shared.filePicker.extensionNotAllowed', { ext });
        }
      }
      if (deniedExtensions) {
        const denied = deniedExtensions
          .split(',')
          .map((s) => s.trim().toLowerCase().replace(/^\./, ''));
        if (denied.includes(ext)) {
          return $t('shared.filePicker.extensionDenied', { ext });
        }
      }
    }
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
            p: { file: File; visibility: string },
            onProg: (pg: { percent: number }) => void,
            opts: Record<string, unknown>,
          ) =>
            adminSmartUploadFile(
              {
                file: p.file,
                tenant_id: 0,
                visibility: p.visibility as 'private' | 'public',
              },
              onProg,
              opts,
            )
        : tenantSmartUploadFile;
    const result = await uploadFn(
      { file: task.file, visibility: 'private' },
      (progress) => {
        task.percent = progress.percent;
      },
      { signal: task.abortController.signal },
    );
    task.status = 'success';
    task.percent = 100;

    if (result.attachment?.id) {
      if (!props.multiple) selectedIds.value.clear();
      if (selectedIds.value.size < props.maxCount) {
        selectedIds.value.add(result.attachment.id);
        selectedIds.value = new Set(selectedIds.value);
      }
    }
  } catch (error: unknown) {
    const err = error as Error & { name?: string };
    if (err.name === 'AbortError' || (task.status as string) === 'cancelled')
      return;

    if (task.retryCount < props.maxRetries) {
      task.retryCount++;
      task.status = 'pending';
      await new Promise((r) => setTimeout(r, 1000 * task.retryCount));
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
  if (
    uploadTasks.value.some(
      (t) => t.status === 'uploading' || t.status === 'pending',
    )
  )
    return;
  if (uploadTasks.value.some((t) => t.status === 'error')) return;
  uploading.value = false;
  setTimeout(() => {
    uploadTasks.value = [];
    loadFiles();
  }, 600);
}

function processQueue() {
  const active = uploadTasks.value.filter(
    (t) => t.status === 'uploading',
  ).length;
  const pending = uploadTasks.value.filter((t) => t.status === 'pending');
  if (active >= props.maxConcurrency || pending.length === 0) return;
  for (const task of pending.slice(0, props.maxConcurrency - active)) {
    executeUploadTask(task).finally(() => processQueue());
  }
}

const BATCH_SIZE_THRESHOLD = 5 * 1024 * 1024; // Files ≤ 5MB can be batch-uploaded / ≤ 5MB 的文件可批量打包
const BATCH_MAX_FILES = 20; // Max files per batch / 每批最多文件数

/**
 * Try to batch upload qualifying small files, remaining files go through single-file queue
 * 尝试将符合条件的小文件批量上传，剩余文件走单文件队列
 */
async function executeBatchUpload(batchFiles: File[]): Promise<void> {
  // Create task for each file in batch for UI display / 为批量中每个文件创建 task 用于 UI 展示
  const batchTasks: UploadTask[] = batchFiles.map((file) => ({
    uid: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    file,
    name: file.name,
    size: file.size,
    status: 'uploading' as const,
    percent: 50,
    retryCount: 0,
  }));
  uploadTasks.value.unshift(...batchTasks);

  try {
    const batchApi =
      resolvedEndpoint.value === 'admin'
        ? (p: { files: File[]; visibility?: 'private' | 'public' }) =>
            adminBatchUploadApi({ ...p, tenant_id: 0 })
        : tenantBatchUploadApi;

    const result = await batchApi({
      files: batchFiles,
      visibility: 'private',
    });

    for (let i = 0; i < result.items.length; i++) {
      const item = result.items[i]!;
      const task = batchTasks[i];
      if (task) {
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
        } else {
          task.status = 'error';
          task.error = item.error ?? $t('shared.filePicker.uploadFailed');
        }
      }
    }
  } catch (err: unknown) {
    const errMsg = (err as Error).message || $t('shared.filePicker.uploadFailed');
    for (const task of batchTasks) {
      if (task.status === 'uploading') {
        task.status = 'error';
        task.error = errMsg;
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
    const error = validateFile(file);
    if (error) {
      message.error(`${file.name}: ${error}`);
      continue;
    }
    validFiles.push(file);
  }
  if (validFiles.length === 0) return;

  // Group small files and large files / 将小文件和大文件分组
  const smallFiles = validFiles.filter((f) => f.size <= BATCH_SIZE_THRESHOLD);
  const largeFiles = validFiles.filter((f) => f.size > BATCH_SIZE_THRESHOLD);

  // Large files go through single-file queue / 大文件走单文件队列
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

  // Batch upload when ≥ 2 small files, otherwise use single-file queue / 小文件 ≥ 2 个时批量上传，否则也走单文件队列
  if (smallFiles.length >= 2) {
    // Split by BATCH_MAX_FILES / 按 BATCH_MAX_FILES 分批
    for (let i = 0; i < smallFiles.length; i += BATCH_MAX_FILES) {
      const batch = smallFiles.slice(i, i + BATCH_MAX_FILES);
      executeBatchUpload(batch).finally(() => processQueue());
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

  if (uploadTasks.value.some((t) => t.status === 'pending')) {
    processQueue();
  }
}

function handleCustomUpload(options: unknown) {
  const opts = options as {
    file: File;
    onSuccess?: (...args: unknown[]) => void;
  };
  addFilesToQueue([opts.file]);
  opts.onSuccess?.();
}

function cancelTask(task: UploadTask) {
  if (task.status === 'uploading' && task.abortController)
    task.abortController.abort();
  task.status = 'cancelled';
}

function retryTask(task: UploadTask) {
  if (task.status === 'error' || task.status === 'cancelled') {
    task.status = 'pending';
    task.percent = 0;
    task.error = undefined;
    task.retryCount = 0;
    processQueue();
  }
}

function clearCompletedTasks() {
  uploadTasks.value = uploadTasks.value.filter(
    (t) =>
      t.status === 'uploading' ||
      t.status === 'pending' ||
      t.status === 'error',
  );
}

function clearErrors() {
  uploadTasks.value = uploadTasks.value.filter((t) => t.status !== 'error');
}

function retryAllErrors() {
  uploadTasks.value
    .filter((t) => t.status === 'error')
    .forEach((t) => retryTask(t));
}

// ============ Full modal drag & drop / 全弹窗拖拽 ============

function hasFiles(e: DragEvent) {
  return !!e.dataTransfer?.types?.includes('Files');
}

function onModalDragEnter(e: DragEvent) {
  if (!hasFiles(e)) return;
  dragCounter++;
  isDragOver.value = true;
}

function onModalDragOver(e: DragEvent) {
  e.preventDefault();
  e.stopPropagation();
}

function onModalDragLeave() {
  dragCounter--;
  if (dragCounter <= 0) {
    dragCounter = 0;
    isDragOver.value = false;
  }
}

function onModalDrop(e: DragEvent) {
  e.preventDefault();
  e.stopPropagation();
  dragCounter = 0;
  isDragOver.value = false;
  const droppedFiles = e.dataTransfer?.files;
  if (droppedFiles?.length) addFilesToQueue([...droppedFiles]);
}

function onWindowDragOver(e: DragEvent) {
  e.preventDefault();
}

window.addEventListener('dragover', onWindowDragOver);
onBeforeUnmount(() => window.removeEventListener('dragover', onWindowDragOver));

// ============ Confirm/Cancel / 确认/取消 ============

function handleConfirm() {
  emit('select', selectedFiles.value);
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

defineExpose({
  open: () => modalApi.open(),
  close: () => modalApi.close(),
});
</script>

<template>
  <Modal
    :title="$t('shared.filePicker.title')"
    :footer="false"
    :fullscreen-button="true"
    class="w-[1100px] max-w-[95vw]"
  >
    <div
      class="relative flex min-h-[520px] flex-col"
      @dragenter.prevent="onModalDragEnter"
      @dragover.prevent="onModalDragOver"
      @dragleave="onModalDragLeave"
      @drop="onModalDrop"
    >
      <!-- Full modal drag overlay / 全弹窗拖拽覆盖层 -->
      <Transition name="fp-overlay">
        <div
          v-if="isDragOver"
          class="pointer-events-none absolute inset-0 z-50 flex flex-col items-center justify-center gap-5 rounded-xl border-[3px] border-dashed border-primary/80 bg-primary/[0.04] backdrop-blur-sm"
        >
          <div
            class="fp-drop-icon flex size-20 items-center justify-center rounded-3xl shadow-xl"
          >
            <IconifyIcon
              icon="lucide:cloud-upload"
              class="size-10 text-white"
            />
          </div>
          <div class="flex flex-col items-center gap-1.5">
            <span class="text-xl font-bold text-foreground">
              {{ $t('shared.filePicker.releaseToUpload') }}
            </span>
            <span class="text-sm text-muted-foreground">
              {{ $t('shared.filePicker.dropFilesAnywhere') }}
            </span>
          </div>
        </div>
      </Transition>

      <!-- ========= Upper section: Upload + Queue / 上半区：上传 + 队列 ========= -->
      <div class="border-b border-border/60 pb-4">
        <!-- Upload zone / 上传区 -->
        <div class="upload-dropzone group rounded-xl">
          <Upload.Dragger
            :custom-request="handleCustomUpload"
            :accept="accept"
            :multiple="multiple"
            :show-upload-list="false"
            :open-file-dialog-on-click="true"
            class="!border-none !bg-transparent"
          >
            <div class="flex items-center gap-5 px-6 py-5">
              <div
                class="fp-drop-icon flex size-14 shrink-0 items-center justify-center rounded-2xl shadow-lg transition-transform duration-300 group-hover:-translate-y-0.5"
              >
                <IconifyIcon
                  icon="lucide:cloud-upload"
                  class="size-7 text-white"
                />
              </div>
              <div class="flex flex-col gap-0.5 text-left">
                <span class="text-[15px] font-semibold text-foreground">
                  {{ $t('shared.filePicker.dropToUpload') }}
                </span>
                <span class="text-[13px] text-muted-foreground">
                  {{ $t('shared.filePicker.orClickToSelect') }}
                  ·
                  {{
                    $t('shared.filePicker.maxSizeHint', {
                      size: formatFileSize(maxFileSize),
                    })
                  }}
                </span>
              </div>
            </div>
          </Upload.Dragger>
        </div>

        <!-- Upload task queue / 上传任务队列 -->
        <Transition name="fp-slide">
          <div
            v-if="uploadTasks.length > 0"
            class="mt-3 overflow-hidden rounded-xl border border-border/60 bg-card"
          >
            <div
              class="flex items-center justify-between border-b border-border/40 bg-muted/30 px-4 py-2.5"
            >
              <span class="text-xs font-semibold text-muted-foreground">
                {{
                  $t('shared.filePicker.uploadingTitle', {
                    count: uploadingCount,
                    total: uploadTasks.length,
                  })
                }}
              </span>
              <span class="flex items-center gap-1">
                <template v-if="errorCount > 0">
                  <Button
                    type="link"
                    size="small"
                    danger
                    @click="retryAllErrors"
                  >
                    {{ $t('shared.filePicker.retryAll') }}
                  </Button>
                  <Button type="link" size="small" @click="clearErrors">
                    {{ $t('shared.filePicker.clearErrors') }}
                  </Button>
                </template>
                <Button type="link" size="small" @click="clearCompletedTasks">
                  {{ $t('shared.filePicker.clearCompleted') }}
                </Button>
              </span>
            </div>
            <div class="max-h-[120px] overflow-y-auto">
              <TransitionGroup name="fp-task">
                <div
                  v-for="task in uploadTasks"
                  :key="task.uid"
                  class="flex items-center gap-3 px-4 py-2 transition-colors duration-150 hover:bg-muted/20"
                  :class="{ 'opacity-40': task.status === 'success' }"
                >
                  <IconifyIcon
                    :icon="getFileIcon(task.name, task.file.type)"
                    class="shrink-0 text-base text-muted-foreground"
                  />
                  <span
                    class="min-w-0 flex-1 truncate text-xs"
                    :title="task.name"
                  >
                    {{ task.name }}
                  </span>
                  <span class="shrink-0 text-[11px] text-muted-foreground">
                    {{ formatFileSize(task.size) }}
                  </span>
                  <div class="w-24 shrink-0">
                    <Progress
                      :percent="task.percent"
                      size="small"
                      :status="
                        task.status === 'error'
                          ? 'exception'
                          : task.status === 'success'
                            ? 'success'
                            : 'active'
                      "
                      :show-info="false"
                      :stroke-width="4"
                    />
                  </div>
                  <div class="flex w-6 shrink-0 justify-end">
                    <IconifyIcon
                      v-if="task.status === 'success'"
                      icon="lucide:check"
                      class="text-sm text-green-500"
                    />
                    <Tooltip
                      v-else-if="task.status === 'error'"
                      :title="task.error"
                    >
                      <Button
                        type="text"
                        size="small"
                        class="!size-5 !min-w-0"
                        @click="retryTask(task)"
                      >
                        <IconifyIcon
                          icon="lucide:rotate-ccw"
                          class="text-xs text-red-500"
                        />
                      </Button>
                    </Tooltip>
                    <Button
                      v-else-if="
                        task.status === 'pending' || task.status === 'uploading'
                      "
                      type="text"
                      size="small"
                      class="!size-5 !min-w-0"
                      @click="cancelTask(task)"
                    >
                      <IconifyIcon
                        icon="lucide:x"
                        class="text-xs text-muted-foreground"
                      />
                    </Button>
                  </div>
                </div>
              </TransitionGroup>
            </div>
          </div>
        </Transition>
      </div>

      <!-- ========= Lower section: File list / 下半区：文件列表 ========= -->
      <div class="flex flex-1 flex-col gap-3 pt-4">
        <!-- Toolbar / 工具栏 -->
        <div class="flex items-center gap-2.5">
          <Input
            v-model:value="searchKeyword"
            :placeholder="$t('shared.filePicker.searchPlaceholder')"
            allow-clear
            class="max-w-[320px] flex-1"
            @press-enter="handleSearch"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:search" class="text-muted-foreground" />
            </template>
          </Input>

          <Select
            v-if="showCategoryFilter"
            v-model:value="categoryFilter"
            :options="categoryOptions"
            :placeholder="$t('shared.filePicker.allCategories')"
            class="w-32"
            @change="handleCategoryChange"
          />

          <div
            class="ml-auto flex gap-0.5 rounded-lg border border-border/60 p-0.5"
          >
            <Tooltip :title="$t('shared.filePicker.gridView')">
              <Button
                type="text"
                size="small"
                class="!rounded-md"
                :class="viewMode === 'grid' ? '!bg-accent' : ''"
                @click="viewMode = 'grid'"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:layout-grid" class="text-sm" />
                </template>
              </Button>
            </Tooltip>
            <Tooltip :title="$t('shared.filePicker.listView')">
              <Button
                type="text"
                size="small"
                class="!rounded-md"
                :class="viewMode === 'list' ? '!bg-accent' : ''"
                @click="viewMode = 'list'"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:list" class="text-sm" />
                </template>
              </Button>
            </Tooltip>
          </div>
        </div>

        <!-- File grid / list / 文件网格 / 列表 -->
        <Spin :spinning="loading" class="flex-1">
          <div class="min-h-[260px]">
            <!-- Grid -->
            <div v-if="viewMode === 'grid' && files.length > 0">
              <Row :gutter="[10, 10]">
                <Col
                  v-for="(file, idx) in files"
                  :key="file.id"
                  :span="4"
                  :style="{ '--fp-i': idx }"
                >
                  <!-- File card: click entire card to select/deselect / 文件卡片：点击整张卡片即选中/取消选中 -->
                  <div
                    class="fp-card fp-fade-in group relative cursor-pointer rounded-lg border border-border/50 bg-card p-1.5 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
                    :class="{
                      '!border-primary ring-2 ring-primary/20': selectedIds.has(
                        file.id,
                      ),
                    }"
                    @click="handleFileClick(file)"
                  >
                    <!-- Top-left: multi-select checkbox / 左上角：多选复选框 -->
                    <div v-if="multiple" class="absolute left-2.5 top-2.5 z-10">
                      <Checkbox :checked="selectedIds.has(file.id)" />
                    </div>

                    <!-- Selected state: top-right check badge / 选中状态：右上角勾选角标 -->
                    <div
                      v-if="selectedIds.has(file.id)"
                      class="absolute right-0 top-0 z-10"
                    >
                      <div
                        class="flex size-6 items-center justify-center rounded-bl-lg rounded-tr-lg bg-primary text-white"
                      >
                        <IconifyIcon icon="lucide:check" class="size-3.5" />
                      </div>
                    </div>

                    <!-- Preview area / 预览区 -->
                    <div
                      class="relative mb-1.5 flex h-[90px] items-center justify-center overflow-hidden rounded-md bg-muted/30"
                    >
                      <img
                        v-if="getPreviewUrl(file)"
                        :src="getPreviewUrl(file)!"
                        :alt="file.name"
                        loading="lazy"
                        class="size-full object-cover"
                        @error="
                          ($event.target as HTMLImageElement).classList.add(
                            'hidden',
                          )
                        "
                      />
                      <IconifyIcon
                        v-if="!getPreviewUrl(file)"
                        :icon="getFileIcon(file.name, file.mimeType)"
                        class="size-10 text-muted-foreground/60"
                      />
                      <!-- Image zoom button: small button at bottom-right, doesn't block the image / 图片放大按钮：仅小按钮在右下角，不遮挡整个图片 -->
                      <button
                        v-if="isImage(file)"
                        class="absolute bottom-1.5 right-1.5 z-10 flex size-7 items-center justify-center rounded-full bg-black/50 text-white opacity-0 backdrop-blur-sm transition-all duration-200 hover:bg-black/70 group-hover:opacity-100"
                        :title="$t('shared.common.preview')"
                        @click.stop="openPreview(file)"
                      >
                        <IconifyIcon icon="lucide:zoom-in" class="size-3.5" />
                      </button>
                    </div>

                    <div class="px-0.5">
                      <div
                        class="truncate text-xs font-medium leading-tight"
                        :title="file.name"
                      >
                        {{ file.name.replace(/\.[^/.]+$/, '') }}
                      </div>
                      <div
                        class="mt-0.5 flex items-center justify-between text-[10px] text-muted-foreground"
                      >
                        <span>{{
                          file.mimeType?.split('/')[1]?.toUpperCase() || 'FILE'
                        }}</span>
                        <span>{{ formatFileSize(file.size) }}</span>
                      </div>
                    </div>
                  </div>
                </Col>
              </Row>
            </div>

            <!-- List -->
            <div
              v-else-if="viewMode === 'list' && files.length > 0"
              class="flex flex-col gap-1"
            >
              <!-- List item: click entire row to select/deselect / 列表项：点击整行选中/取消选中 -->
              <div
                v-for="file in files"
                :key="file.id"
                class="group flex cursor-pointer items-center gap-3 rounded-lg border border-transparent px-3 py-2 transition-all duration-150 hover:border-border hover:bg-accent/40"
                :class="{
                  '!border-primary/50 bg-primary/5': selectedIds.has(file.id),
                }"
                @click="handleFileClick(file)"
              >
                <Checkbox v-if="multiple" :checked="selectedIds.has(file.id)" />
                <!-- Selected state icon (shown in single-select mode) / 选中状态图标（单选模式下显示） -->
                <IconifyIcon
                  v-if="!multiple && selectedIds.has(file.id)"
                  icon="lucide:circle-check"
                  class="size-4 shrink-0 text-primary"
                />
                <div
                  class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted/40"
                >
                  <img
                    v-if="getPreviewUrl(file)"
                    :src="getPreviewUrl(file)!"
                    loading="lazy"
                    class="size-full object-cover"
                    @error="
                      ($event.target as HTMLImageElement).classList.add(
                        'hidden',
                      )
                    "
                  />
                  <IconifyIcon
                    v-if="!getPreviewUrl(file)"
                    :icon="getFileIcon(file.name, file.mimeType)"
                    class="size-5 text-muted-foreground/60"
                  />
                </div>
                <div class="flex min-w-0 flex-1 flex-col">
                  <span
                    class="truncate text-sm font-medium"
                    :title="file.name"
                    >{{ file.name }}</span
                  >
                  <span class="text-xs text-muted-foreground">
                    {{ formatFileSize(file.size) }}
                    <span class="mx-1">&middot;</span>
                    <Tag
                      v-if="file.category"
                      :bordered="false"
                      size="small"
                      class="!text-[10px]"
                    >
                      {{ file.category }}
                    </Tag>
                  </span>
                </div>
                <span class="shrink-0 text-xs text-muted-foreground">
                  {{ formatDate(file.createdAt) }}
                </span>
                <!-- Preview button in list mode / 列表模式下的预览按钮 -->
                <button
                  v-if="isImage(file)"
                  class="flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground opacity-0 transition-all duration-150 hover:bg-accent hover:text-foreground group-hover:opacity-100"
                  :title="$t('shared.common.preview')"
                  @click.stop="openPreview(file)"
                >
                  <IconifyIcon icon="lucide:zoom-in" class="size-3.5" />
                </button>
              </div>
            </div>

            <!-- Empty -->
            <div
              v-else-if="!loading && files.length === 0"
              class="flex min-h-[200px] flex-col items-center justify-center gap-3 py-12"
            >
              <IconifyIcon
                icon="lucide:inbox"
                class="size-14 text-muted-foreground/30"
              />
              <div class="text-sm font-medium text-muted-foreground">
                {{ $t('shared.filePicker.empty') }}
              </div>
              <div class="text-xs text-muted-foreground/60">
                {{ $t('shared.filePicker.emptyHint') }}
              </div>
            </div>
          </div>
        </Spin>

        <!-- Pagination / 分页 -->
        <div v-if="total > pageSize" class="flex justify-center">
          <Pagination
            :current="currentPage"
            :page-size="pageSize"
            :total="total"
            size="small"
            show-less-items
            @change="handlePageChange"
          />
        </div>
      </div>

      <!-- ========= Bottom bar / 底栏 ========= -->
      <div
        v-if="multiple"
        class="flex items-center justify-between border-t border-border/60 pt-4"
      >
        <span class="text-xs text-muted-foreground">
          <template v-if="selectedIds.size > 0">
            {{
              $t('shared.filePicker.selectedCount', { count: selectedIds.size })
            }}
          </template>
        </span>
        <div class="flex gap-2">
          <Button @click="modalApi.close()">
            {{ $t('shared.common.cancel') }}
          </Button>
          <Button
            type="primary"
            :disabled="selectedIds.size === 0"
            @click="handleConfirm"
          >
            {{ $t('shared.common.select') }}
          </Button>
        </div>
      </div>

      <!-- Image preview / 图片预览 -->
      <Image
        :src="previewUrl"
        :preview="{
          visible: previewVisible,
          onVisibleChange: (v: boolean) => (previewVisible = v),
        }"
        class="hidden"
      />
    </div>
  </Modal>
</template>

<style scoped>
@keyframes fp-in {
  from {
    opacity: 0;
    transform: translateY(6px) scale(0.98);
  }

  to {
    opacity: 1;
    transform: none;
  }
}

.upload-dropzone {
  background: hsl(var(--primary) / 2%);
  border: 1.5px dashed hsl(var(--primary) / 30%);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.upload-dropzone:hover {
  background: hsl(var(--primary) / 5%);
  border-color: hsl(var(--primary) / 60%);
}

.upload-dropzone :deep(.ant-upload-drag) {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
}

.upload-dropzone :deep(.ant-upload-btn) {
  padding: 0 !important;
}

/* === Gradient icon / 渐变图标 === */
.fp-drop-icon {
  background: linear-gradient(
    135deg,
    hsl(var(--primary)) 0%,
    hsl(var(--primary) / 75%) 100%
  );
}

/* === Grid card staggered fade-in / 网格卡片交错淡入 === */
.fp-fade-in {
  animation: fp-in 0.3s cubic-bezier(0.4, 0, 0.2, 1) both;
  animation-delay: calc(var(--fp-i, 0) * 25ms);
}

/* === Drag overlay / 拖拽覆盖层 === */
.fp-overlay-enter-active {
  transition: all 0.2s ease-out;
}

.fp-overlay-leave-active {
  transition: all 0.15s ease-in;
}

.fp-overlay-enter-from,
.fp-overlay-leave-to {
  opacity: 0;
}

/* === Upload queue animation / 上传队列动画 === */
.fp-slide-enter-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.fp-slide-leave-active {
  transition: all 0.2s ease-in;
}

.fp-slide-enter-from,
.fp-slide-leave-to {
  max-height: 0;
  margin-top: 0;
  opacity: 0;
}

.fp-task-enter-active {
  transition: all 0.25s ease-out;
}

.fp-task-leave-active {
  transition: all 0.15s ease-in;
}

.fp-task-enter-from {
  opacity: 0;
  transform: translateX(-8px);
}

.fp-task-leave-to {
  opacity: 0;
  transform: translateX(8px);
}

.fp-task-move {
  transition: transform 0.25s ease;
}

/* === Upload zone: gradient border + drag activation / 上传区：渐变边框 + 拖拽激活 === */
</style>
