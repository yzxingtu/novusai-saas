<script setup lang="ts">
/**
 * 文件选择器弹窗组件
 * 支持选择已有附件或上传新文件
 */
import type { AttachmentInfo } from '#/types/attachment';

import { computed, ref, watch } from 'vue';

import { useVbenModal } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Checkbox,
  Col,
  Input,
  message,
  Pagination,
  Progress,
  Row,
  Select,
  Spin,
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
    /** 文件类型过滤 */
    accept?: string;
    /** 仅显示图片 */
    imageOnly?: boolean;
    /** 并发上传数 */
    maxConcurrency?: number;
    /** 最大选择数量 */
    maxCount?: number;
    /** 最大文件大小 (bytes) */
    maxFileSize?: number;
    /** 重试次数 */
    maxRetries?: number;
    /** 是否多选 */
    multiple?: boolean;
  }>(),
  {
    multiple: false,
    accept: '*',
    maxCount: 10,
    imageOnly: false,
    maxFileSize: 100 * 1024 * 1024, // 100MB
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

// 弹窗
const [Modal, modalApi] = useVbenModal({
  onOpenChange: (isOpen) => {
    if (isOpen) {
      loadFiles();
    }
  },
});

// 状态
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

// 上传任务队列
const uploadTasks = ref<UploadTask[]>([]);

// 正在上传的任务数
const uploadingCount = computed(() => {
  return uploadTasks.value.filter((t) => t.status === 'uploading').length;
});

// 有错误的任务数
const errorCount = computed(() => {
  return uploadTasks.value.filter((t) => t.status === 'error').length;
});

// 分类选项
const categoryOptions = computed(() => [
  { label: $t('shared.filePicker.allCategories'), value: '' },
  { label: $t('shared.filePicker.categories.image'), value: 'image' },
  { label: $t('shared.filePicker.categories.document'), value: 'document' },
  { label: $t('shared.filePicker.categories.video'), value: 'video' },
  { label: $t('shared.filePicker.categories.audio'), value: 'audio' },
  { label: $t('shared.filePicker.categories.archive'), value: 'archive' },
  { label: $t('shared.filePicker.categories.other'), value: 'other' },
]);

// 已选文件列表
const selectedFiles = computed(() => {
  return files.value.filter((f) => selectedIds.value.has(f.id));
});

// 加载文件列表
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

    if (categoryFilter.value) {
      params['filter[category]'] = categoryFilter.value;
    } else if (props.imageOnly) {
      params['filter[category]'] = 'image';
    }

    const result = await getAttachmentListApi(params);
    files.value = result.items;
    total.value = result.total;
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false;
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1;
  loadFiles();
}

// 分类筛选变化
function handleCategoryChange() {
  currentPage.value = 1;
  loadFiles();
}

// 分页变化
function handlePageChange(page: number) {
  currentPage.value = page;
  loadFiles();
}

// 切换选择 / 直接选择
function handleFileClick(file: AttachmentInfo) {
  if (props.multiple) {
    if (selectedIds.value.has(file.id)) {
      selectedIds.value.delete(file.id);
    } else {
      if (selectedIds.value.size < props.maxCount) {
        selectedIds.value.add(file.id);
      } else {
        message.warning(
          $t('shared.filePicker.maxCountExceeded', { count: props.maxCount }),
        );
      }
    }
    // 触发响应式更新
    selectedIds.value = new Set(selectedIds.value);
  } else {
    // 单选模式：点击即选中并确认
    emit('select', [file]);
    modalApi.close();
  }
}

// 验证文件
function validateFile(file: File): null | string {
  // 文件大小检查
  if (file.size > props.maxFileSize) {
    return $t('shared.filePicker.fileTooLarge', {
      maxSize: formatFileSize(props.maxFileSize),
    });
  }

  // MIME 类型检查（如果有限制）
  if (props.imageOnly && !file.type.startsWith('image/')) {
    return $t('shared.filePicker.onlyImages');
  }

  // 文件名检查
  if (!file.name || file.name.trim() === '') {
    return $t('shared.filePicker.invalidFileName');
  }

  return null;
}

// 执行单个上传任务
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
      {
        signal: task.abortController.signal,
      },
    );

    task.status = 'success';
    task.percent = 100;

    // 自动选中新上传的文件
    if (result.id) {
      if (!props.multiple) {
        selectedIds.value.clear();
      }
      if (selectedIds.value.size < props.maxCount) {
        selectedIds.value.add(result.id);
        selectedIds.value = new Set(selectedIds.value);
      }
    }

    // 刷新列表
    await loadFiles();
  } catch (error: any) {
    // 如果被取消，不处理错误
    if (error.name === 'AbortError' || (task.status as string) === 'cancelled') {
      return;
    }

    if (task.status === 'cancelled') {
      return;
    }

    // 重试逻辑
    if (task.retryCount < props.maxRetries) {
      task.retryCount++;
      task.status = 'pending';
      await new Promise((resolve) =>
        setTimeout(resolve, 1000 * task.retryCount),
      ); // 指数退避
      return executeUploadTask(task);
    }

    task.status = 'error';
    task.error = error.message || $t('shared.filePicker.uploadFailed');
  } finally {
    task.abortController = undefined;
  }
}

// 处理队列
function processQueue() {
  const uploading = uploadTasks.value.filter(
    (t) => t.status === 'uploading',
  ).length;
  const pending = uploadTasks.value.filter((t) => t.status === 'pending');

  if (uploading >= props.maxConcurrency || pending.length === 0) {
    return;
  }

  const toProcess = pending.slice(0, props.maxConcurrency - uploading);
  for (const task of toProcess) {
    executeUploadTask(task).finally(() => {
      processQueue();
    });
  }
}

// 自定义上传
function handleCustomUpload(options: any) {
  const { file } = options;

  // 验证文件
  const error = validateFile(file);
  if (error) {
    message.error(error);
    options.onError?.(new Error(error));
    return;
  }

  const task: UploadTask = {
    uid: file.uid,
    file: file as File,
    name: file.name,
    size: file.size,
    status: 'pending',
    percent: 0,
    retryCount: 0,
  };

  uploadTasks.value.unshift(task);
  uploading.value = true;

  // 启动队列处理
  processQueue();

  options.onSuccess?.();
}

// 取消上传
function cancelTask(task: UploadTask) {
  if (task.status === 'uploading' && task.abortController) {
    task.abortController.abort();
  }
  task.status = 'cancelled';
}

// 重试上传
function retryTask(task: UploadTask) {
  if (task.status === 'error' || task.status === 'cancelled') {
    task.status = 'pending';
    task.percent = 0;
    task.error = undefined;
    task.retryCount = 0;
    processQueue();
  }
}

// 清除已完成任务
function clearCompletedTasks() {
  uploadTasks.value = uploadTasks.value.filter(
    (t) =>
      t.status === 'uploading' ||
      t.status === 'pending' ||
      t.status === 'error',
  );
}

// 清除所有错误任务
function clearErrors() {
  uploadTasks.value = uploadTasks.value.filter((t) => t.status !== 'error');
}

// 重试所有错误任务
function retryAllErrors() {
  uploadTasks.value
    .filter((t) => t.status === 'error')
    .forEach((t) => retryTask(t));
}

// 确认选择
function handleConfirm() {
  emit('select', selectedFiles.value);
  modalApi.close();
}

// 取消
function handleCancel() {
  modalApi.close();
}

// 获取预览 URL
function getPreviewUrl(file: AttachmentInfo): null | string {
  if (file.category === 'image' && file.path) {
    // 使用公共访问接口
    return `/api/public/attachments/${file.id}/access`;
  }
  return null;
}

// 重置
watch(
  () => modalApi.getData(),
  () => {
    selectedIds.value.clear();
    searchKeyword.value = '';
    categoryFilter.value = '';
    currentPage.value = 1;
  },
);

// 暴露方法
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
    <div class="file-picker">
      <!-- 顶部工具栏 -->
      <div class="file-picker__toolbar">
        <Input
          v-model:value="searchKeyword"
          :placeholder="$t('shared.filePicker.searchPlaceholder')"
          allow-clear
          class="file-picker__search"
          @press-enter="handleSearch"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:search" class="text-muted-foreground" />
          </template>
        </Input>

        <Select
          v-if="!imageOnly"
          v-model:value="categoryFilter"
          :options="categoryOptions"
          :placeholder="$t('shared.filePicker.allCategories')"
          class="file-picker__filter"
          @change="handleCategoryChange"
        />

        <div class="file-picker__view-toggle">
          <Tooltip :title="$t('shared.filePicker.gridView')">
            <Button
              type="text"
              size="small"
              :class="{ 'bg-accent': viewMode === 'grid' }"
              @click="viewMode = 'grid'"
            >
              <template #icon>
                <IconifyIcon icon="lucide:layout-grid" />
              </template>
            </Button>
          </Tooltip>
          <Tooltip :title="$t('shared.filePicker.listView')">
            <Button
              type="text"
              size="small"
              :class="{ 'bg-accent': viewMode === 'list' }"
              @click="viewMode = 'list'"
            >
              <template #icon>
                <IconifyIcon icon="lucide:list" />
              </template>
            </Button>
          </Tooltip>
        </div>
      </div>

      <!-- 上传区域 -->
      <Upload.Dragger
        :custom-request="handleCustomUpload"
        :accept="accept"
        :multiple="multiple"
        :show-upload-list="false"
        class="upload-dropzone"
      >
        <div class="upload-dropzone__content">
          <div class="upload-dropzone__icon">
            <IconifyIcon
              icon="lucide:cloud-upload"
              class="upload-dropzone__icon-main"
            />
          </div>
          <div class="upload-dropzone__text">
            <span class="upload-dropzone__title">
              {{ $t('shared.filePicker.dropToUpload') }}
            </span>
            <span class="upload-dropzone__subtitle">
              {{ $t('shared.filePicker.orClickToSelect') }}
            </span>
          </div>
          <div class="upload-dropzone__hint">
            {{
              $t('shared.filePicker.maxSizeHint', {
                size: formatFileSize(maxFileSize),
              })
            }}
          </div>
        </div>
      </Upload.Dragger>

      <!-- 上传任务队列 -->
      <div v-if="uploadTasks.length > 0" class="file-picker__queue">
        <div class="file-picker__queue-header">
          <span class="file-picker__queue-title">
            {{
              $t('shared.filePicker.uploadingTitle', {
                count: uploadingCount,
                total: uploadTasks.length,
              })
            }}
          </span>
          <span v-if="errorCount > 0" class="mr-2">
            <Button type="link" size="small" danger @click="retryAllErrors">
              {{ $t('shared.filePicker.retryAll') }}
            </Button>
            <Button type="link" size="small" @click="clearErrors">
              {{ $t('shared.filePicker.clearErrors') }}
            </Button>
          </span>
          <Button type="link" size="small" @click="clearCompletedTasks">
            {{ $t('shared.filePicker.clearCompleted') }}
          </Button>
        </div>
        <div class="file-picker__queue-list">
          <div
            v-for="task in uploadTasks"
            :key="task.uid"
            class="file-picker__queue-item"
          >
            <div class="file-picker__queue-info">
              <IconifyIcon
                :icon="getFileIcon(task.name, task.file.type)"
                class="file-picker__queue-icon"
              />
              <div class="file-picker__queue-meta">
                <span class="file-picker__queue-name" :title="task.name">
                  {{ task.name }}
                </span>
                <span class="file-picker__queue-size">
                  {{ formatFileSize(task.size) }}
                </span>
              </div>
            </div>
            <div class="file-picker__queue-progress">
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
              />
            </div>
            <div class="file-picker__queue-action">
              <IconifyIcon
                v-if="task.status === 'success'"
                icon="lucide:check-circle"
                class="text-green-500"
              />
              <div
                v-else-if="task.status === 'error'"
                class="flex items-center"
              >
                <Tooltip :title="task.error">
                  <IconifyIcon
                    icon="lucide:alert-circle"
                    class="mr-1 text-red-500"
                  />
                </Tooltip>
                <Button type="text" size="small" @click="retryTask(task)">
                  <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
                </Button>
              </div>
              <Button
                v-else-if="
                  task.status === 'pending' || task.status === 'uploading'
                "
                type="text"
                size="small"
                @click="cancelTask(task)"
              >
                <IconifyIcon icon="lucide:x" class="text-muted-foreground" />
              </Button>
              <span
                v-else-if="task.status === 'cancelled'"
                class="text-xs text-muted-foreground"
              >
                {{ $t('shared.filePicker.cancelled') }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 文件列表 -->
      <Spin :spinning="loading">
        <div class="file-picker__content">
          <!-- Grid View -->
          <div
            v-if="viewMode === 'grid' && files.length > 0"
            class="file-picker__grid"
          >
            <Row :gutter="[12, 12]">
              <Col v-for="file in files" :key="file.id" :span="4">
                <Card
                  hoverable
                  class="file-picker__item"
                  :class="[
                    { 'file-picker__item--selected': selectedIds.has(file.id) },
                  ]"
                  :body-style="{ padding: '8px' }"
                  @click="handleFileClick(file)"
                >
                  <div v-if="multiple" class="file-picker__item-checkbox">
                    <Checkbox :checked="selectedIds.has(file.id)" />
                  </div>

                  <div class="file-picker__item-preview">
                    <img
                      v-if="getPreviewUrl(file)"
                      :src="getPreviewUrl(file)!"
                      :alt="file.name"
                      class="file-picker__item-image"
                    />
                    <div v-else class="file-picker__item-icon">
                      <IconifyIcon
                        :icon="getFileIcon(file.name, file.mimeType)"
                        class="size-12"
                      />
                    </div>
                  </div>

                  <div class="file-picker__item-info">
                    <div class="file-picker__item-name" :title="file.name">
                      {{ file.name.replace(/\.[^/.]+$/, '') }}
                    </div>
                    <div class="file-picker__item-meta">
                      {{
                        file.mimeType?.split('/')[1]?.toUpperCase() || 'FILE'
                      }}
                    </div>
                  </div>
                </Card>
              </Col>
            </Row>
          </div>

          <!-- List View -->
          <div
            v-else-if="viewMode === 'list' && files.length > 0"
            class="file-picker__list"
          >
            <div
              v-for="file in files"
              :key="file.id"
              class="file-picker__list-item"
              :class="{
                'file-picker__list-item--selected': selectedIds.has(file.id),
              }"
              @click="handleFileClick(file)"
            >
              <Checkbox
                v-if="multiple"
                :checked="selectedIds.has(file.id)"
                class="mr-3"
              />
              <div class="file-picker__list-icon">
                <img
                  v-if="getPreviewUrl(file)"
                  :src="getPreviewUrl(file)!"
                  class="h-8 w-8 rounded object-cover"
                />
                <IconifyIcon
                  v-else
                  :icon="getFileIcon(file.name, file.mimeType)"
                  class="size-8 text-muted-foreground"
                />
              </div>
              <div class="file-picker__list-info">
                <div class="truncate font-medium" :title="file.name">
                  {{ file.name }}
                </div>
                <div class="text-xs text-muted-foreground">
                  {{ formatFileSize(file.size) }} ·
                  {{ formatDate(file.uploadedAt) }}
                </div>
              </div>
            </div>
          </div>

          <div v-else-if="files.length === 0" class="file-picker__empty">
            <div class="file-picker__empty-icon">
              <IconifyIcon icon="lucide:folder-open" class="size-16" />
            </div>
            <div class="file-picker__empty-text">
              {{ $t('shared.filePicker.empty') }}
            </div>
            <div class="file-picker__empty-hint">
              {{ $t('shared.filePicker.emptyHint') }}
            </div>
          </div>
        </div>
      </Spin>

      <!-- 分页 -->
      <div v-if="total > pageSize" class="file-picker__pagination">
        <Pagination
          :current="currentPage"
          :page-size="pageSize"
          :total="total"
          size="small"
          show-less-items
          @change="handlePageChange"
        />
      </div>

      <!-- 底部操作栏 (仅多选模式显示) -->
      <div v-if="multiple" class="file-picker__footer">
        <div class="file-picker__selected-info">
          <span v-if="selectedIds.size > 0">
            {{
              $t('shared.filePicker.selectedCount', { count: selectedIds.size })
            }}
          </span>
        </div>
        <div class="file-picker__actions">
          <Button @click="handleCancel">
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
    </div>
  </Modal>
</template>

<style scoped>
.file-picker {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 500px;
}

.file-picker__toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.file-picker__search {
  flex: 1;
  max-width: 400px;
}

.file-picker__filter {
  width: 140px;
}

.file-picker__view-toggle {
  display: flex;
  gap: 4px;
  padding: 2px;
  margin-left: auto;
  border: 1px solid var(--ant-color-border);
  border-radius: 6px;
}

/* 上传区域 */
.upload-dropzone {
  background: linear-gradient(
    135deg,
    hsl(var(--primary) / 2%) 0%,
    hsl(var(--primary) / 6%) 100%
  );
  border: 2px dashed hsl(var(--primary) / 25%);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.upload-dropzone:hover {
  background: linear-gradient(
    135deg,
    hsl(var(--primary) / 4%) 0%,
    hsl(var(--primary) / 10%) 100%
  );
  border-color: hsl(var(--primary) / 50%);
}

.upload-dropzone :deep(.ant-upload-drag) {
  padding: 24px 16px;
  background: transparent !important;
  border: none !important;
}

.upload-dropzone :deep(.ant-upload-btn) {
  padding: 0 !important;
}

.upload-dropzone__content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}

.upload-dropzone__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  background: linear-gradient(
    135deg,
    hsl(var(--primary)) 0%,
    hsl(var(--primary) / 80%) 100%
  );
  border-radius: 16px;
  box-shadow: 0 8px 24px hsl(var(--primary) / 25%);
}

.upload-dropzone__icon-main {
  width: 28px;
  height: 28px;
  color: white;
}

.upload-dropzone__text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}

.upload-dropzone__title {
  font-size: 15px;
  font-weight: 600;
  color: hsl(var(--foreground));
}

.upload-dropzone__subtitle {
  font-size: 13px;
  color: hsl(var(--muted-foreground));
}

.upload-dropzone__hint {
  padding: 6px 12px;
  font-size: 12px;
  color: hsl(var(--muted-foreground) / 70%);
  background: hsl(var(--muted) / 50%);
  border-radius: 6px;
}

.file-picker__content {
  flex: 1;
  min-height: 300px;
  overflow-y: auto;
}

.file-picker__grid {
  padding: 4px;
}

.file-picker__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px;
}

.file-picker__list-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  border: 1px solid var(--ant-color-border);
  border-radius: 8px;
  transition: all 0.2s;
}

.file-picker__list-item:hover {
  background-color: var(--ant-color-fill-quaternary);
  border-color: var(--ant-color-primary);
}

.file-picker__list-item--selected {
  background-color: var(--ant-color-primary-bg);
  border-color: var(--ant-color-primary);
}

.file-picker__list-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  margin-right: 12px;
}

.file-picker__list-info {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.file-picker__item {
  position: relative;
  cursor: pointer;
  transition: all 0.2s;
}

.file-picker__item--selected {
  border-color: var(--ant-color-primary);
  box-shadow: 0 0 0 2px var(--ant-color-primary-bg);
}

.file-picker__item-checkbox {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 1;
}

.file-picker__item-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  margin-bottom: 8px;
  overflow: hidden;
  background: var(--ant-color-fill-tertiary);
  border-radius: 4px;
}

.file-picker__item-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.file-picker__item-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ant-color-text-tertiary);
}

.file-picker__item-info {
  text-align: center;
}

.file-picker__item-name {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.file-picker__item-meta {
  font-size: 11px;
  color: var(--ant-color-text-tertiary);
}

.file-picker__empty {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 40px 20px;
}

.file-picker__empty-icon {
  margin-bottom: 8px;
  color: hsl(var(--muted-foreground) / 40%);
}

.file-picker__empty-text {
  font-size: 15px;
  font-weight: 500;
  color: hsl(var(--muted-foreground));
}

.file-picker__empty-hint {
  font-size: 13px;
  color: hsl(var(--muted-foreground) / 70%);
}

.file-picker__pagination {
  display: flex;
  justify-content: center;
  padding-top: 8px;
}

.file-picker__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 16px;
  border-top: 1px solid var(--ant-color-border);
}

.file-picker__selected-info {
  font-size: 13px;
  color: var(--ant-color-text-secondary);
}

.file-picker__actions {
  display: flex;
  gap: 8px;
}

.file-picker__queue {
  overflow: hidden;
  background-color: hsl(var(--card));
  border: 1px solid hsl(var(--border));
  border-radius: 12px;
}

.file-picker__queue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: linear-gradient(
    135deg,
    hsl(var(--muted) / 30%) 0%,
    hsl(var(--muted) / 50%) 100%
  );
  border-bottom: 1px solid hsl(var(--border));
}

.file-picker__queue-title {
  font-size: 13px;
  font-weight: 600;
  color: hsl(var(--foreground));
}

.file-picker__queue-list {
  max-height: 160px;
  padding: 8px 0;
  overflow-y: auto;
}

.file-picker__queue-item {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 10px 16px;
  transition: background-color 0.2s;
}

.file-picker__queue-item:hover {
  background-color: hsl(var(--muted) / 30%);
}

.file-picker__queue-info {
  display: flex;
  flex: 1;
  gap: 8px;
  align-items: center;
  min-width: 0;
}

.file-picker__queue-icon {
  flex-shrink: 0;
  color: var(--ant-color-text-tertiary);
}

.file-picker__queue-meta {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.file-picker__queue-name {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.file-picker__queue-size {
  font-size: 11px;
  color: var(--ant-color-text-tertiary);
}

.file-picker__queue-progress {
  flex-shrink: 0;
  width: 120px;
}

.file-picker__queue-action {
  display: flex;
  flex-shrink: 0;
  gap: 4px;
  justify-content: flex-end;
  width: 32px;
}
</style>
