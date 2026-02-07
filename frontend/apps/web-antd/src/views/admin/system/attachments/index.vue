<script lang="ts" setup>
/**
 * 附件管理列表页面
 */
import type { AttachmentInfo } from '#/types/attachment';

import { onMounted, ref } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { getAttachmentUrl } from '#/utils/image';

import { Card, Image, message, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getAttachmentDownloadUrlApi,
  getAttachmentListApi,
} from '#/api/admin/attachment';
import { getTenantSelectApi } from '#/api/admin/tenant';
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

defineOptions({ name: 'AdminSystemAttachments' });

const tenantMap = ref<Map<number, string>>(new Map());

onMounted(async () => {
  try {
    const { items } = await getTenantSelectApi();
    for (const item of items) {
      tenantMap.value.set(Number(item.value), item.label);
    }
  } catch {
    //
  }
});

function getTenantName(tenantId: number | undefined): string {
  if (!tenantId) return '-';
  return tenantMap.value.get(tenantId) || `#${tenantId}`;
}

// 详情抽屉
const [DetailDrawerComp, detailDrawerApi] = useVbenDrawer({
  connectedComponent: DetailDrawer,
});

/**
 * 查看详情
 */
function onViewDetail(row: AttachmentInfo) {
  detailDrawerApi.setData({ id: row.id, mode: 'view' }).open();
}

/**
 * 获取缩略图URL（列表显示用）
 */
function getThumbnailUrl(row: AttachmentInfo): string {
  return getAttachmentUrl(row, { preset: 'thumb' });
}

/**
 * 获取预览URL（点击放大用）
 */
function getPreviewUrl(row: AttachmentInfo): string {
  return getAttachmentUrl(row);
}

/**
 * 判断是否为图片
 */
function isImage(row: AttachmentInfo): boolean {
  if (row.category === 'image') return true;
  if (row.mimeType?.startsWith('image/')) return true;
  return false;
}

/**
 * 下载附件
 */
async function onDownload(row: AttachmentInfo) {
  try {
    const result = await getAttachmentDownloadUrlApi(row.id);
    // 创建隐藏的 a 标签触发下载
    const link = document.createElement('a');
    link.href = result.url;
    link.download = row.name;
    link.target = '_blank';
    document.body.append(link);
    link.click();
    link.remove();
    message.success($t('admin.system.attachment.messages.downloadStarted'));
  } catch {
    // Error handled by request interceptor
  }
}

// CRUD 页面（只读列表，不需要新建/编辑表单）
const { Grid } = useCrudPage<AttachmentInfo>({
  api: {
    list: getAttachmentListApi,
    resource: '/admin/attachments',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.system.attachment',
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
    <DetailDrawerComp />

    <!-- 表格 -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
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

        <!-- 租户列 -->
        <template #tenant_cell="{ row }">
          <span class="text-foreground">
            {{ getTenantName(row.tenantId) }}
          </span>
        </template>

        <!-- 存储驱动列 -->
        <template #driver_cell="{ row }">
          <Tag color="blue">{{ row.driver }}</Tag>
        </template>

        <!-- 上传时间列 -->
        <template #uploadedAt_cell="{ row }">
          <Tooltip :title="formatDate(row.uploadedAt)">
            <span class="text-muted-foreground">
              {{ formatRelativeTime(row.uploadedAt) }}
            </span>
          </Tooltip>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
