<script lang="ts" setup>
/**
 * 企业端附件管理列表页面
 */
import type { AttachmentInfo } from '#/types/attachment';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Image, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  downloadAttachmentApi,
  getAttachmentListApi,
} from '#/api/tenant/attachment';
import { FilePicker } from '#/components/business/file-picker';
import { useAttachmentListActions } from '#/composables/use-attachment-list-actions';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  formatFileSize,
  getCategoryColor,
  getCategoryText,
  getFileIcon,
  getVisibilityColor,
  getVisibilityText,
  useColumns,
  useGridFormSchema,
} from './data';
import DetailDrawer from './modules/DetailDrawer.vue';
import QuotaCard from './modules/QuotaCard.vue';

defineOptions({ name: 'TenantSystemAttachments' });

const quotaCardRef = ref<InstanceType<typeof QuotaCard> | null>(null);

const {
  DetailDrawerComp,
  getPreviewUrl,
  getThumbnailUrl,
  isImage,
  onDownload,
  onViewDetail,
} = useAttachmentListActions({
  connectedComponent: DetailDrawer,
  download: downloadAttachmentApi,
  downloadSuccessMessage: $t(
    'tenant.system.attachment.messages.downloadStarted',
  ),
});

const pickerRef = ref<InstanceType<typeof FilePicker> | null>(null);

// CRUD 页面 / CRUD page
const { Grid, gridApi } = useCrudPage<AttachmentInfo>({
  api: {
    list: getAttachmentListApi,
    resource: '/tenant/attachments',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'tenant.system.attachment',
  nameField: 'name',
  defaultSort: '-created_at',
  customActions: {
    detail: onViewDetail,
    download: onDownload,
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <QuotaCard ref="quotaCardRef" />
    <DetailDrawerComp />
    <FilePicker
      ref="pickerRef"
      multiple
      @select="
        () => {
          gridApi?.grid.commitProxy('query');
          quotaCardRef?.refresh();
        }
      "
    />

    <!-- 表格 -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 左侧工具栏：上传按钮 -->
        <template #toolbar-actions>
          <Button type="primary" @click="pickerRef?.open()">
            <template #icon>
              <IconifyIcon icon="lucide:upload" class="size-4" />
            </template>
            {{ $t('tenant.system.attachment.upload') }}
          </Button>
        </template>
        <!-- 预览列 -->
        <template #preview_cell="{ row }">
          <div class="flex items-center justify-center">
            <template v-if="isImage(row)">
              <Image
                :src="getThumbnailUrl(row)"
                :alt="row.name"
                class="size-12 rounded object-cover"
                :preview="{ src: getPreviewUrl(row) }"
                fallback="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0OCIgaGVpZ2h0PSI0OCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM5Y2EzYWYiIHN0cm9rZS13aWR0aD0iMS41IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxyZWN0IHg9IjMiIHk9IjMiIHdpZHRoPSIxOCIgaGVpZ2h0PSIxOCIgcng9IjIiLz48Y2lyY2xlIGN4PSI4LjUiIGN5PSI4LjUiIHI9IjEuNSIvPjxwYXRoIGQ9Im0yMSAxNS0zLjA4Ni0zLjA4NmEyIDIgMCAwIDAtMi44MjggMEw2IDIxIi8+PC9zdmc+"
              />
            </template>
            <template v-else>
              <div
                class="flex size-12 items-center justify-center rounded bg-accent"
              >
                <IconifyIcon
                  :icon="getFileIcon(row.name, row.mimeType)"
                  class="size-6 text-primary"
                />
              </div>
            </template>
          </div>
        </template>

        <!-- 文件名列 -->
        <template #name_cell="{ row }">
          <Tooltip :title="row.name">
            <span class="truncate font-medium text-foreground">
              {{ row.name }}
            </span>
          </Tooltip>
        </template>

        <!-- 分类列 -->
        <template #category_cell="{ row }">
          <Tag :color="getCategoryColor(row.category)">
            {{ getCategoryText(row.category) }}
          </Tag>
        </template>

        <!-- MIME类型列 -->
        <template #mimeType_cell="{ row }">
          <Tooltip :title="row.mimeType">
            <code
              class="max-w-[140px] truncate rounded bg-accent px-1 py-0.5 text-xs"
            >
              {{ row.mimeType }}
            </code>
          </Tooltip>
        </template>

        <!-- 文件大小列 -->
        <template #size_cell="{ row }">
          <span class="text-muted-foreground">
            {{ formatFileSize(row.size) }}
          </span>
        </template>

        <!-- 可见性列 -->
        <template #visibility_cell="{ row }">
          <Tag :color="getVisibilityColor(row.visibility)">
            {{ getVisibilityText(row.visibility) }}
          </Tag>
        </template>

        <!-- 上传时间列 -->
        <template #uploadedAt_cell="{ row }">
          <Tooltip :title="formatDate(row.createdAt)">
            <span class="text-muted-foreground">
              {{ formatRelativeTime(row.createdAt) }}
            </span>
          </Tooltip>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
