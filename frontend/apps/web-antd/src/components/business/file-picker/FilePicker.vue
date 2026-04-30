<script setup lang="ts">
import type { FilePickerProps } from './types';

import type { AttachmentInfo } from '#/types/attachment';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Checkbox,
  Col,
  Image,
  Input,
  Pagination,
  Progress,
  Row,
  Select,
  Spin,
  Tag,
  Tooltip,
  Upload,
} from 'ant-design-vue';

import { formatDate } from '#/utils/common';
import { formatFileSize, getFileIcon } from '#/utils/file';

import { useFilePickerCore } from './use-file-picker-core';

defineOptions({ name: 'FilePicker' });

const props = withDefaults(defineProps<FilePickerProps>(), {
  accept: '*',
  endpoint: undefined,
  imageOnly: false,
  maxConcurrency: 3,
  maxCount: 10,
  maxFileSize: 100 * 1024 * 1024,
  maxRetries: 2,
  multiple: false,
  visibility: 'private',
});

const emit = defineEmits<{
  (e: 'select', files: AttachmentInfo[]): void;
}>();

const {
  Modal,
  cancelTask,
  categoryFilter,
  categoryOptions,
  clearCompletedTasks,
  clearErrors,
  currentPage,
  effectiveMaxFileSize,
  errorCount,
  files,
  getPreviewUrl,
  handleCategoryChange,
  handleConfirm,
  handleCustomUpload,
  handleFileClick,
  handlePageChange,
  handleSearch,
  isDragOver,
  isImage,
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
  retryAllErrors,
  retryTask,
  searchKeyword,
  selectedIds,
  showCategoryFilter,
  total,
  uploadTasks,
  uploadingCount,
  viewMode,
} = useFilePickerCore({
  onSelect: (files) => emit('select', files),
  props,
});

const filesWithPreview = computed(() =>
  files.value.map((file) => ({
    file,
    previewSrc: getPreviewUrl(file),
  })),
);

defineExpose({
  close: () => modalApi.close(),
  open: () => modalApi.open(),
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
                      size: formatFileSize(effectiveMaxFileSize),
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
                  v-for="({ file, previewSrc }, idx) in filesWithPreview"
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
                        v-if="previewSrc"
                        :src="previewSrc"
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
                        v-if="!previewSrc"
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
                v-for="{ file, previewSrc } in filesWithPreview"
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
                    v-if="previewSrc"
                    :src="previewSrc"
                    loading="lazy"
                    class="size-full object-cover"
                    @error="
                      ($event.target as HTMLImageElement).classList.add(
                        'hidden',
                      )
                    "
                  />
                  <IconifyIcon
                    v-if="!previewSrc"
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
