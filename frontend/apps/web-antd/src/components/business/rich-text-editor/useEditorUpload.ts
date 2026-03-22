/**
 * Editor image/attachment upload composable
 */

import type { Editor } from '@tiptap/core';

import { message } from 'ant-design-vue';

import { $t } from '@vben/locales';

import { smartUploadFile as adminSmartUploadFile } from '#/api/admin/attachment';
import { smartUploadFile as tenantSmartUploadFile } from '#/api/tenant/attachment';
import { smartUploadFile as userSmartUploadFile } from '#/api/user/attachment';
import { toAttachmentImageUrl } from '#/utils/image';

import type { AttachmentInfo } from './types';

const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10 MB
const MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024; // 50 MB

interface UploadAttachmentPayload {
  id?: number | string;
  mime_type?: null | string;
  original_name?: null | string;
  size?: null | number;
}

interface UploadResponseLike {
  attachment?: UploadAttachmentPayload;
  url?: string;
}

type UploadEndpoint = 'admin' | 'tenant' | 'user';

function getUploadEndpoint(): UploadEndpoint {
  if (window.location.pathname.startsWith('/admin')) {
    return 'admin';
  }
  if (window.location.pathname.startsWith('/tenant')) {
    return 'tenant';
  }
  return 'user';
}

async function smartUpload(file: File): Promise<UploadResponseLike> {
  const endpoint = getUploadEndpoint();
  if (endpoint === 'admin') {
    return adminSmartUploadFile({
      file,
      tenant_id: 0,
      visibility: 'public',
    });
  }
  if (endpoint === 'user') {
    return userSmartUploadFile({
      file,
      visibility: 'public',
    });
  }
  return tenantSmartUploadFile({
    file,
    visibility: 'public',
  });
}

export interface UploadResult {
  url: string;
  id: string | number;
}

export async function uploadImage(file: File): Promise<UploadResult | null> {
  if (!file.type.startsWith('image/')) return null;
  if (file.size > MAX_IMAGE_SIZE) {
    message.error($t('common.uploadValidation.fileTooLarge', { max: 10 }));
    return null;
  }

  try {
    const data = await smartUpload(file);
    const attachmentId = data.attachment?.id;
    const url =
      toAttachmentImageUrl(attachmentId, { preset: 'large' }) || data.url;
    if (!attachmentId || !url) {
      throw new Error('Invalid upload response');
    }

    return {
      url,
      id: attachmentId,
    };
  } catch {
    message.error($t('common.uploadValidation.uploadFailed'));
    return null;
  }
}

export async function uploadAttachment(
  file: File,
): Promise<AttachmentInfo | null> {
  if (file.size > MAX_ATTACHMENT_SIZE) {
    message.error($t('common.uploadValidation.fileTooLarge', { max: 50 }));
    return null;
  }

  try {
    const data = await smartUpload(file);
    const attachment = data.attachment;
    if (!attachment?.id || !data.url) {
      throw new Error('Invalid upload response');
    }

    return {
      id: attachment.id,
      name: attachment.original_name || file.name,
      size: attachment.size || file.size,
      mime_type: attachment.mime_type || file.type,
      url: data.url,
    };
  } catch {
    message.error($t('common.uploadValidation.uploadFailed'));
    return null;
  }
}

function removePlaceholderImage(editor: Editor, placeholder: string) {
  const { doc } = editor.state;
  doc.descendants((node, pos) => {
    if (node.type.name === 'image' && node.attrs.alt === placeholder) {
      editor
        .chain()
        .focus()
        .deleteRange({ from: pos, to: pos + node.nodeSize })
        .run();
      return false;
    }
    return true;
  });
}

export function handleImagePaste(editor: Editor, event: ClipboardEvent) {
  const items = event.clipboardData?.items;
  if (!items) return false;

  for (const item of items) {
    if (item.type.startsWith('image/')) {
      event.preventDefault();
      const file = item.getAsFile();
      if (!file) continue;

      const placeholder = `uploading-${Date.now()}`;
      editor.chain().focus().setImage({ src: '', alt: placeholder }).run();

      uploadImage(file).then((result) => {
        if (result) {
          const { state } = editor;
          const { doc } = state;
          doc.descendants((node, pos) => {
            if (node.type.name === 'image' && node.attrs.alt === placeholder) {
              editor
                .chain()
                .focus()
                .setNodeSelection(pos)
                .setImage({ src: result.url, alt: '' })
                .run();
              return false;
            }
            return true;
          });
        } else {
          removePlaceholderImage(editor, placeholder);
        }
      });

      return true;
    }
  }
  return false;
}

export function handleImageDrop(editor: Editor, event: DragEvent, pos: number) {
  const files = event.dataTransfer?.files;
  if (!files?.length) return false;

  for (const file of files) {
    if (file.type.startsWith('image/')) {
      event.preventDefault();

      uploadImage(file).then((result) => {
        if (result) {
          editor
            .chain()
            .focus()
            .insertContentAt(pos, {
              type: 'image',
              attrs: { src: result.url },
            })
            .run();
        }
      });

      return true;
    }
  }
  return false;
}

export function triggerImageUpload(editor: Editor) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.onchange = () => {
    const file = input.files?.[0];
    if (!file) return;
    uploadImage(file).then((result) => {
      if (result) {
        editor.chain().focus().setImage({ src: result.url }).run();
      }
    });
  };
  input.click();
}

export function triggerAttachmentUpload(editor: Editor) {
  const input = document.createElement('input');
  input.type = 'file';
  input.onchange = () => {
    const file = input.files?.[0];
    if (!file) return;
    uploadAttachment(file).then((info) => {
      if (info) {
        editor
          .chain()
          .focus()
          .insertContent({
            type: 'paragraph',
            content: [
              {
                type: 'text',
                marks: [{ type: 'link', attrs: { href: info.url } }],
                text: `📎 ${info.name} (${formatFileSize(info.size)})`,
              },
            ],
          })
          .run();
      }
    });
  };
  input.click();
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
