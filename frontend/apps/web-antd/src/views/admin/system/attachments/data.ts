/**
 * 附件管理 - 表格列和搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AttachmentCategory, AttachmentInfo } from '#/types/attachment';

import { searchInput, select } from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';
import {
  getAttachmentCategoryColor,
  getAttachmentMimeCategoryFilterValues,
  getAttachmentVisibilityColor,
} from '#/utils/attachment-presentation';

// ============ 工具函数 / Helpers ============

/**
 * 获取文件分类颜色
 */
export function getCategoryColor(
  category: AttachmentCategory | null | undefined,
): string {
  return getAttachmentCategoryColor(category);
}

/**
 * 获取文件分类文本
 */
export function getCategoryText(
  category: AttachmentCategory | null | undefined,
): string {
  if (!category) return '-';
  return $t(`admin.system.attachment.categoryType.${category}`);
}

/**
 * 获取可见性颜色
 */
export function getVisibilityColor(
  visibility: 'private' | 'public' | undefined,
): string {
  return getAttachmentVisibilityColor(visibility);
}

/**
 * 获取可见性文本
 */
export function getVisibilityText(
  visibility: 'private' | 'public' | undefined,
): string {
  if (!visibility) return '-';
  return $t(`admin.system.attachment.visibilityType.${visibility}`);
}

/**
 * 分类筛选选项（按 mime_type 前缀过滤）
 */
export function getCategoryFilterOptions(): {
  label: string;
  value: string;
}[] {
  const [image, document, video, audio] =
    getAttachmentMimeCategoryFilterValues();
  return [
    {
      label: $t('admin.system.attachment.categoryType.image'),
      value: image,
    },
    {
      label: $t('admin.system.attachment.categoryType.document'),
      value: document,
    },
    {
      label: $t('admin.system.attachment.categoryType.video'),
      value: video,
    },
    {
      label: $t('admin.system.attachment.categoryType.audio'),
      value: audio,
    },
  ];
}

/**
 * 可见性选项
 */
export function getVisibilityOptions(): { label: string; value: string }[] {
  return [
    {
      label: $t('admin.system.attachment.visibilityType.public'),
      value: 'public',
    },
    {
      label: $t('admin.system.attachment.visibilityType.private'),
      value: 'private',
    },
  ];
}

// ============ 表格列定义 / Table columns ============

/**
 * 表格列定义
 */
export function useColumns<T = AttachmentInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'preview',
      title: $t('admin.system.attachment.preview'),
      width: 80,
      align: 'center',
      slots: {
        default: 'preview_cell',
      },
    },
    {
      field: 'name',
      title: $t('admin.system.attachment.name'),
      minWidth: 200,
      slots: {
        default: 'name_cell',
      },
    },
    {
      field: 'category',
      title: $t('admin.system.attachment.category'),
      width: 100,
      align: 'center',
      slots: {
        default: 'category_cell',
      },
    },
    {
      field: 'mimeType',
      title: $t('admin.system.attachment.mimeType'),
      width: 160,
      slots: {
        default: 'mimeType_cell',
      },
    },
    {
      field: 'size',
      title: $t('admin.system.attachment.size'),
      width: 100,
      align: 'right',
      slots: {
        default: 'size_cell',
      },
    },
    {
      field: 'visibility',
      title: $t('admin.system.attachment.visibility'),
      width: 90,
      align: 'center',
      slots: {
        default: 'visibility_cell',
      },
    },
    {
      field: 'tenantId',
      title: $t('admin.system.attachment.tenantName'),
      width: 120,
      slots: {
        default: 'tenant_cell',
      },
    },
    {
      field: 'driver',
      title: $t('admin.system.attachment.driver'),
      width: 100,
      align: 'center',
      slots: {
        default: 'driver_cell',
      },
    },
    {
      field: 'createdAt',
      title: $t('admin.system.attachment.uploadedAt'),
      width: 140,
      slots: {
        default: 'uploadedAt_cell',
      },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'attachment',
          nameField: 'name',
          nameTitle: $t('admin.system.attachment.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('admin.system.attachment.detail'),
            icon: 'lucide:eye',
            accessCodes: ['attachment:detail'],
          },
          {
            code: 'download',
            text: $t('admin.system.attachment.actions.download'),
            icon: 'lucide:download',
            accessCodes: ['attachment:download_url'],
          },
          'delete',
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 160,
    },
  ];
}

// ============ 搜索表单 / Search form ============

/** 企业选择器（搜索） / Tenant selector (search) */
function tenantSelect(options: { search?: boolean } = {}): VbenFormSchema {
  const { search = true } = options;
  return select(
    search ? 'filter[tenant_id]' : 'tenant_id',
    $t('admin.system.attachment.tenantName'),
    {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.system.attachment.placeholder.allTenant'),
    },
  );
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('admin.system.attachment.name'), {
      placeholder: $t('admin.system.attachment.placeholder.searchName'),
    }),
    select('filter[mime_type][like]', $t('admin.system.attachment.category'), {
      options: getCategoryFilterOptions(),
      placeholder: $t('admin.system.attachment.placeholder.allCategory'),
    }),
    select('filter[visibility]', $t('admin.system.attachment.visibility'), {
      options: getVisibilityOptions(),
      placeholder: $t('admin.system.attachment.placeholder.allVisibility'),
    }),
    tenantSelect({ search: true }),
  ];
}

export { formatFileSize, getFileIcon } from '#/utils/file';
