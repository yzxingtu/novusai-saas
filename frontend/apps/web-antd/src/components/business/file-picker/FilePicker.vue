<script setup lang="ts">
/**
 * 附件选择器 - 支持选择已有附件或上传新文件
 */
import type { AttachmentInfo } from '#/types/attachment';

import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import { useVbenModal } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { getAttachmentUrl } from '#/utils/image';

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

import { getAttachmentListApi, smartUploadFile } from '#/api/tenant/attachment';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { formatFileSize, getFileIcon } from '#/utils/file';

defineOptions({ name: 'FilePicker' });

const props = withDefaults(
  defineProps<{
    accept?: string;
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

const [Modal, modalApi] = useVbenModal({
  onOpenChange: (isOpen) => {
    if (isOpen) loadFiles();
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
 * 从 accept prop 中提取 MIME 大类用于后端筛选
 * 如 'image/*' → 'image'，'video/*' → 'video'
 * 非通配符格式(如 'application/pdf,.docx')则返回空，不自动筛选
 */
const acceptMimeFilter = computed(() => {
  if (!props.accept || props.accept === '*') return '';
  const parts = props.accept.split(',').map((s) => s.trim());
  const mimeWild = parts.find((p) => p.endsWith('/*'));
  if (mimeWild) return mimeWild.replace('/*', '');
  return '';
});

/** 当 imageOnly 或 accept 指定了类型时，隐藏分类下拉筛选器 */
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
  return getAttachmentUrl(file, { preset: 'thumb', format: 'webp', quality: 75 });
}

/** 获取原图 URL（用于放大预览），不传 preset 返回原始尺寸 */
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

// ============ 数据加载 ============

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
    // 按分类/文件类型筛选：优先用户选择的分类，其次 imageOnly，最后 accept prop 推导的 MIME 大类
    if (categoryFilter.value) {
      params['filter[mime_type][like]'] = `${categoryFilter.value}/%`;
    } else if (props.imageOnly) {
      params['filter[mime_type][like]'] = 'image/%';
    } else if (acceptMimeFilter.value) {
      params['filter[mime_type][like]'] = `${acceptMimeFilter.value}/%`;
    }
    const result = await getAttachmentListApi(params);
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

// ============ 文件选择 ============

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

// ============ 上传 ============

function validateFile(file: File): null | string {
  if (file.size > props.maxFileSize)
    return $t('shared.filePicker.fileTooLarge', {
      maxSize: formatFileSize(props.maxFileSize),
    });
  if (props.imageOnly && !file.type.startsWith('image/'))
    return $t('shared.filePicker.onlyImages');
  if (!file.name?.trim()) return $t('shared.filePicker.invalidFileName');
  return null;
}

async function executeUploadTask(task: UploadTask): Promise<void> {
  task.status = 'uploading';
  task.percent = 0;
  task.abortController = new AbortController();

  try {
    const result = await smartUploadFile(
      { file: task.file, visibility: 'private' },
      (progress) => {
        task.percent = progress.percent;
      },
      { signal: task.abortController.signal },
    );
    task.status = 'success';
    task.percent = 100;

    if (result.id) {
      if (!props.multiple) selectedIds.value.clear();
      if (selectedIds.value.size < props.maxCount) {
        selectedIds.value.add(result.id);
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
  if (uploadTasks.value.some((t) => t.status === 'uploading' || t.status === 'pending')) return;
  if (uploadTasks.value.some((t) => t.status === 'error')) return;
  uploading.value = false;
  setTimeout(() => {
    uploadTasks.value = [];
    loadFiles();
  }, 600);
}

function processQueue() {
  const active = uploadTasks.value.filter((t) => t.status === 'uploading').length;
  const pending = uploadTasks.value.filter((t) => t.status === 'pending');
  if (active >= props.maxConcurrency || pending.length === 0) return;
  for (const task of pending.slice(0, props.maxConcurrency - active)) {
    executeUploadTask(task).finally(() => processQueue());
  }
}

function addFilesToQueue(fileList: File[]) {
  for (const file of fileList) {
    const error = validateFile(file);
    if (error) {
      message.error(`${file.name}: ${error}`);
      continue;
    }
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
  if (uploadTasks.value.some((t) => t.status === 'pending')) {
    uploading.value = true;
    processQueue();
  }
}

function handleCustomUpload(options: any) {
  addFilesToQueue([options.file as File]);
  options.onSuccess?.();
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
    (t) => t.status === 'uploading' || t.status === 'pending' || t.status === 'error',
  );
}

function clearErrors() {
  uploadTasks.value = uploadTasks.value.filter((t) => t.status !== 'error');
}

function retryAllErrors() {
  uploadTasks.value.filter((t) => t.status === 'error').forEach((t) => retryTask(t));
}

// ============ 全弹窗拖拽 ============

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
  if (droppedFiles?.length) addFilesToQueue(Array.from(droppedFiles));
}

function onWindowDragOver(e: DragEvent) {
  e.preventDefault();
}

window.addEventListener('dragover', onWindowDragOver);
onBeforeUnmount(() => window.removeEventListener('dragover', onWindowDragOver));

// ============ 确认/取消 ============

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
      <!-- 全弹窗拖拽覆盖层 -->
      <Transition name="fp-overlay">
        <div
          v-if="isDragOver"
          class="pointer-events-none absolute inset-0 z-50 flex flex-col items-center justify-center gap-5 rounded-xl border-[3px] border-dashed border-primary/80 bg-primary/[0.04] backdrop-blur-sm"
        >
          <div class="fp-drop-icon flex size-20 items-center justify-center rounded-3xl shadow-xl">
            <IconifyIcon icon="lucide:cloud-upload" class="size-10 text-white" />
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

      <!-- ========= 上半区：上传 + 队列 ========= -->
      <div class="border-b border-border/60 pb-4">
        <!-- 上传区 -->
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
              <div class="fp-drop-icon flex size-14 shrink-0 items-center justify-center rounded-2xl shadow-lg transition-transform duration-300 group-hover:-translate-y-0.5">
                <IconifyIcon icon="lucide:cloud-upload" class="size-7 text-white" />
              </div>
              <div class="flex flex-col gap-0.5 text-left">
                <span class="text-[15px] font-semibold text-foreground">
                  {{ $t('shared.filePicker.dropToUpload') }}
                </span>
                <span class="text-[13px] text-muted-foreground">
                  {{ $t('shared.filePicker.orClickToSelect') }}
                  ·
                  {{ $t('shared.filePicker.maxSizeHint', { size: formatFileSize(maxFileSize) }) }}
                </span>
              </div>
            </div>
          </Upload.Dragger>
        </div>

        <!-- 上传任务队列 -->
        <Transition name="fp-slide">
          <div v-if="uploadTasks.length > 0" class="mt-3 overflow-hidden rounded-xl border border-border/60 bg-card">
            <div class="flex items-center justify-between border-b border-border/40 bg-muted/30 px-4 py-2.5">
              <span class="text-xs font-semibold text-muted-foreground">
                {{ $t('shared.filePicker.uploadingTitle', { count: uploadingCount, total: uploadTasks.length }) }}
              </span>
              <span class="flex items-center gap-1">
                <template v-if="errorCount > 0">
                  <Button type="link" size="small" danger @click="retryAllErrors">
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
                  <span class="min-w-0 flex-1 truncate text-xs" :title="task.name">
                    {{ task.name }}
                  </span>
                  <span class="shrink-0 text-[11px] text-muted-foreground">
                    {{ formatFileSize(task.size) }}
                  </span>
                  <div class="w-24 shrink-0">
                    <Progress
                      :percent="task.percent"
                      size="small"
                      :status="task.status === 'error' ? 'exception' : task.status === 'success' ? 'success' : 'active'"
                      :show-info="false"
                      :stroke-width="4"
                    />
                  </div>
                  <div class="flex w-6 shrink-0 justify-end">
                    <IconifyIcon v-if="task.status === 'success'" icon="lucide:check" class="text-sm text-green-500" />
                    <Tooltip v-else-if="task.status === 'error'" :title="task.error">
                      <Button type="text" size="small" class="!size-5 !min-w-0" @click="retryTask(task)">
                        <IconifyIcon icon="lucide:rotate-ccw" class="text-xs text-red-500" />
                      </Button>
                    </Tooltip>
                    <Button
                      v-else-if="task.status === 'pending' || task.status === 'uploading'"
                      type="text"
                      size="small"
                      class="!size-5 !min-w-0"
                      @click="cancelTask(task)"
                    >
                      <IconifyIcon icon="lucide:x" class="text-xs text-muted-foreground" />
                    </Button>
                  </div>
                </div>
              </TransitionGroup>
            </div>
          </div>
        </Transition>
      </div>

      <!-- ========= 下半区：文件列表 ========= -->
      <div class="flex flex-1 flex-col gap-3 pt-4">
        <!-- 工具栏 -->
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

          <div class="ml-auto flex gap-0.5 rounded-lg border border-border/60 p-0.5">
            <Tooltip :title="$t('shared.filePicker.gridView')">
              <Button
                type="text"
                size="small"
                class="!rounded-md"
                :class="viewMode === 'grid' ? '!bg-accent' : ''"
                @click="viewMode = 'grid'"
              >
                <template #icon><IconifyIcon icon="lucide:layout-grid" class="text-sm" /></template>
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
                <template #icon><IconifyIcon icon="lucide:list" class="text-sm" /></template>
              </Button>
            </Tooltip>
          </div>
        </div>

        <!-- 文件网格 / 列表 -->
        <Spin :spinning="loading" class="flex-1">
          <div class="min-h-[260px]">
            <!-- Grid -->
            <div v-if="viewMode === 'grid' && files.length > 0">
              <Row :gutter="[10, 10]">
                <Col v-for="(file, idx) in files" :key="file.id" :span="4" :style="{ '--fp-i': idx }">
                  <!-- 文件卡片：点击整张卡片即选中/取消选中 -->
                  <div
                    class="fp-card fp-fade-in group relative cursor-pointer rounded-lg border border-border/50 bg-card p-1.5 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
                    :class="{ '!border-primary ring-2 ring-primary/20': selectedIds.has(file.id) }"
                    @click="handleFileClick(file)"
                  >
                    <!-- 左上角：多选复选框 -->
                    <div v-if="multiple" class="absolute left-2.5 top-2.5 z-10">
                      <Checkbox :checked="selectedIds.has(file.id)" />
                    </div>

                    <!-- 选中状态：右上角勾选角标 -->
                    <div
                      v-if="selectedIds.has(file.id)"
                      class="absolute right-0 top-0 z-10"
                    >
                      <div class="flex size-6 items-center justify-center rounded-bl-lg rounded-tr-lg bg-primary text-white">
                        <IconifyIcon icon="lucide:check" class="size-3.5" />
                      </div>
                    </div>

                    <!-- 预览区 -->
                    <div class="relative mb-1.5 flex h-[90px] items-center justify-center overflow-hidden rounded-md bg-muted/30">
                      <img
                        v-if="getPreviewUrl(file)"
                        :src="getPreviewUrl(file)!"
                        :alt="file.name"
                        loading="lazy"
                        class="size-full object-cover"
                        @error="($event.target as HTMLImageElement).classList.add('hidden')"
                      />
                      <IconifyIcon
                        v-if="!getPreviewUrl(file)"
                        :icon="getFileIcon(file.name, file.mimeType)"
                        class="size-10 text-muted-foreground/60"
                      />
                      <!-- 图片放大按钮：仅小按钮在右下角，不遮挡整个图片 -->
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
                      <div class="truncate text-xs font-medium leading-tight" :title="file.name">
                        {{ file.name.replace(/\.[^/.]+$/, '') }}
                      </div>
                      <div class="mt-0.5 flex items-center justify-between text-[10px] text-muted-foreground">
                        <span>{{ file.mimeType?.split('/')[1]?.toUpperCase() || 'FILE' }}</span>
                        <span>{{ formatFileSize(file.size) }}</span>
                      </div>
                    </div>
                  </div>
                </Col>
              </Row>
            </div>

            <!-- List -->
            <div v-else-if="viewMode === 'list' && files.length > 0" class="flex flex-col gap-1">
              <!-- 列表项：点击整行选中/取消选中 -->
              <div
                v-for="file in files"
                :key="file.id"
                class="group flex cursor-pointer items-center gap-3 rounded-lg border border-transparent px-3 py-2 transition-all duration-150 hover:border-border hover:bg-accent/40"
                :class="{ '!border-primary/50 bg-primary/5': selectedIds.has(file.id) }"
                @click="handleFileClick(file)"
              >
                <Checkbox v-if="multiple" :checked="selectedIds.has(file.id)" />
                <!-- 选中状态图标（单选模式下显示） -->
                <IconifyIcon
                  v-if="!multiple && selectedIds.has(file.id)"
                  icon="lucide:circle-check"
                  class="size-4 shrink-0 text-primary"
                />
                <div class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted/40">
                  <img
                    v-if="getPreviewUrl(file)"
                    :src="getPreviewUrl(file)!"
                    loading="lazy"
                    class="size-full object-cover"
                    @error="($event.target as HTMLImageElement).classList.add('hidden')"
                  />
                  <IconifyIcon
                    v-if="!getPreviewUrl(file)"
                    :icon="getFileIcon(file.name, file.mimeType)"
                    class="size-5 text-muted-foreground/60"
                  />
                </div>
                <div class="flex min-w-0 flex-1 flex-col">
                  <span class="truncate text-sm font-medium" :title="file.name">{{ file.name }}</span>
                  <span class="text-xs text-muted-foreground">
                    {{ formatFileSize(file.size) }}
                    <span class="mx-1">&middot;</span>
                    <Tag v-if="file.category" :bordered="false" size="small" class="!text-[10px]">
                      {{ file.category }}
                    </Tag>
                  </span>
                </div>
                <span class="shrink-0 text-xs text-muted-foreground">
                  {{ formatDate(file.uploadedAt) }}
                </span>
                <!-- 列表模式下的预览按钮 -->
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
              <IconifyIcon icon="lucide:inbox" class="size-14 text-muted-foreground/30" />
              <div class="text-sm font-medium text-muted-foreground">
                {{ $t('shared.filePicker.empty') }}
              </div>
              <div class="text-xs text-muted-foreground/60">
                {{ $t('shared.filePicker.emptyHint') }}
              </div>
            </div>
          </div>
        </Spin>

        <!-- 分页 -->
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

      <!-- ========= 底栏 ========= -->
      <div
        v-if="multiple"
        class="flex items-center justify-between border-t border-border/60 pt-4"
      >
        <span class="text-xs text-muted-foreground">
          <template v-if="selectedIds.size > 0">
            {{ $t('shared.filePicker.selectedCount', { count: selectedIds.size }) }}
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

      <!-- 图片预览 -->
      <Image
        :src="previewUrl"
        :preview="{ visible: previewVisible, onVisibleChange: (v: boolean) => (previewVisible = v) }"
        class="hidden"
      />
    </div>
  </Modal>
</template>

<style scoped>
/* === 上传区：渐变边框 + 拖拽激活 === */
.upload-dropzone {
  border: 1.5px dashed hsl(var(--primary) / 30%);
  background: hsl(var(--primary) / 2%);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.upload-dropzone:hover {
  border-color: hsl(var(--primary) / 60%);
  background: hsl(var(--primary) / 5%);
}

.upload-dropzone :deep(.ant-upload-drag) {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
}

.upload-dropzone :deep(.ant-upload-btn) {
  padding: 0 !important;
}

/* === 渐变图标 === */
.fp-drop-icon {
  background: linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 75%) 100%);
}

/* === 网格卡片交错淡入 === */
.fp-fade-in {
  animation: fp-in 0.3s cubic-bezier(0.4, 0, 0.2, 1) both;
  animation-delay: calc(var(--fp-i, 0) * 25ms);
}

@keyframes fp-in {
  from { opacity: 0; transform: translateY(6px) scale(0.98); }
  to { opacity: 1; transform: none; }
}

/* === 拖拽覆盖层 === */
.fp-overlay-enter-active { transition: all 0.2s ease-out; }
.fp-overlay-leave-active { transition: all 0.15s ease-in; }
.fp-overlay-enter-from,
.fp-overlay-leave-to { opacity: 0; }

/* === 上传队列动画 === */
.fp-slide-enter-active { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.fp-slide-leave-active { transition: all 0.2s ease-in; }
.fp-slide-enter-from,
.fp-slide-leave-to { opacity: 0; max-height: 0; margin-top: 0; }

.fp-task-enter-active { transition: all 0.25s ease-out; }
.fp-task-leave-active { transition: all 0.15s ease-in; }
.fp-task-enter-from { opacity: 0; transform: translateX(-8px); }
.fp-task-leave-to { opacity: 0; transform: translateX(8px); }
.fp-task-move { transition: transform 0.25s ease; }
</style>
