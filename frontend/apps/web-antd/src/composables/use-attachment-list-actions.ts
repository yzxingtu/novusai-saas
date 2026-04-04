import type { Component } from 'vue';

import type { AttachmentInfo } from '#/types/attachment';

import { useVbenDrawer } from '@vben/common-ui';

import { message } from 'ant-design-vue';

import { getAttachmentUrl } from '#/utils/image';

interface UseAttachmentListActionsOptions {
  connectedComponent: Component;
  download: (
    attachmentId: number,
    filename: string,
    mimeType?: null | string,
  ) => Promise<void>;
  downloadSuccessMessage: string;
}

export function useAttachmentListActions(
  options: UseAttachmentListActionsOptions,
) {
  const [DetailDrawerComp, detailDrawerApi] = useVbenDrawer({
    connectedComponent: options.connectedComponent,
  });

  function onViewDetail(row: AttachmentInfo) {
    detailDrawerApi.setData({ id: row.id, mode: 'view' }).open();
  }

  function getThumbnailUrl(row: AttachmentInfo): string {
    return getAttachmentUrl(row, { preset: 'thumb' });
  }

  function getPreviewUrl(row: AttachmentInfo): string {
    return getAttachmentUrl(row);
  }

  function isImage(row: AttachmentInfo): boolean {
    return (
      row.category === 'image' || Boolean(row.mimeType?.startsWith('image/'))
    );
  }

  async function onDownload(row: AttachmentInfo) {
    try {
      await options.download(row.id, row.name, row.mimeType);
      message.success(options.downloadSuccessMessage);
    } catch {
      // Error handled by request interceptor / 错误由请求拦截器处理
    }
  }

  return {
    DetailDrawerComp,
    getPreviewUrl,
    getThumbnailUrl,
    isImage,
    onDownload,
    onViewDetail,
  };
}
