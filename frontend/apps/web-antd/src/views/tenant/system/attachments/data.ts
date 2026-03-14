import type { VbenFormSchema } from '#/adapter/form';
/**
 * 企业端附件管理 - 列定义和搜索 Schema
 * 复用平台端的大部分配置，移除企业筛选
 */
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AttachmentInfo } from '#/types/attachment';

import { searchInput, select } from '#/core/adapter/form/schema-helpers';
import { $t } from '#/locales';

// ============ 工具函数 ============

/** 文件分类颜色映射 */
export function getCategoryColor(
  category?: null | string,
): 'blue' | 'cyan' | 'default' | 'green' | 'orange' | 'purple' | 'red' {
  if (!category) return 'default';
  const colorMap: Record<
    string,
    'blue' | 'cyan' | 'default' | 'green' | 'orange' | 'purple' | 'red'
  > = {
    image: 'green',
    document: 'blue',
    video: 'purple',
    audio: 'orange',
    archive: 'cyan',
    other: 'default',
  };
  return colorMap[category] || 'default';
}

/** 文件分类文本映射 */
export function getCategoryText(category?: null | string): string {
  if (!category) return $t('tenant.system.attachment.categories.other');
  return $t(`tenant.system.attachment.categories.${category}`);
}

/** 可见性颜色映射 */
export function getVisibilityColor(
  visibility: string,
): 'default' | 'green' | 'orange' {
  return visibility === 'public' ? 'green' : 'orange';
}

/** 获取可见性文本映射 */
export function getVisibilityText(visibility: string): string {
  return $t(`tenant.system.attachment.visibilityOptions.${visibility}`);
}

/** 获取分类筛选选项（按 mime_type 前缀过滤） */
export function getCategoryFilterOptions(): { label: string; value: string }[] {
  return [
    { label: $t('tenant.system.attachment.categories.image'), value: 'image/' },
    {
      label: $t('tenant.system.attachment.categories.document'),
      value: 'application/',
    },
    { label: $t('tenant.system.attachment.categories.video'), value: 'video/' },
    { label: $t('tenant.system.attachment.categories.audio'), value: 'audio/' },
  ];
}

/** 获取可见性选项 */
export function getVisibilityOptions() {
  return [
    {
      label: $t('tenant.system.attachment.visibilityOptions.public'),
      value: 'public',
    },
    {
      label: $t('tenant.system.attachment.visibilityOptions.private'),
      value: 'private',
    },
  ];
}

// ============ 列定义 ============

type OnActionClickFn = (
  code: string,
  row: AttachmentInfo,
) => Promise<void> | void;

/**
 * 表格列定义
 */
export function useColumns(
  onActionClick: OnActionClickFn,
): VxeTableGridOptions<AttachmentInfo>['columns'] {
  return [
    { type: 'checkbox', width: 50 },
    {
      field: 'preview',
      title: $t('tenant.system.attachment.preview'),
      width: 80,
      align: 'center',
      slots: {
        default: 'preview_cell',
      },
    },
    {
      field: 'name',
      title: $t('tenant.system.attachment.name'),
      minWidth: 200,
      slots: {
        default: 'name_cell',
      },
    },
    {
      field: 'category',
      title: $t('tenant.system.attachment.category'),
      width: 100,
      align: 'center',
      slots: {
        default: 'category_cell',
      },
    },
    {
      field: 'mimeType',
      title: $t('tenant.system.attachment.mimeType'),
      width: 150,
      slots: {
        default: 'mimeType_cell',
      },
    },
    {
      field: 'size',
      title: $t('tenant.system.attachment.size'),
      width: 100,
      align: 'right',
      slots: {
        default: 'size_cell',
      },
    },
    {
      field: 'visibility',
      title: $t('tenant.system.attachment.visibility'),
      width: 90,
      align: 'center',
      slots: {
        default: 'visibility_cell',
      },
    },
    {
      field: 'createdAt',
      title: $t('tenant.system.attachment.uploadedAt'),
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
          nameTitle: $t('tenant.system.attachment.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'detail',
            text: $t('tenant.system.attachment.detail'),
            icon: 'lucide:eye',
            accessCodes: ['attachment:detail'],
          },
          {
            code: 'download',
            text: $t('tenant.system.attachment.actions.download'),
            icon: 'lucide:download',
            accessCodes: ['attachment:download_url'],
          },
          'delete',
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('tenant.common.operation'),
      width: 160,
    },
  ];
}

// ============ 搜索表单 ============

/**
 * 搜索表单 Schema（企业端不需要企业筛选）
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('tenant.system.attachment.name'), {
      placeholder: $t('tenant.system.attachment.placeholder.searchName'),
    }),
    select('filter[mime_type][like]', $t('tenant.system.attachment.category'), {
      options: getCategoryFilterOptions(),
      placeholder: $t('tenant.system.attachment.placeholder.allCategory'),
    }),
    select('filter[visibility]', $t('tenant.system.attachment.visibility'), {
      options: getVisibilityOptions(),
      placeholder: $t('tenant.system.attachment.placeholder.allVisibility'),
    }),
  ];
}

export { formatFileSize, getFileIcon } from '#/utils/file';
