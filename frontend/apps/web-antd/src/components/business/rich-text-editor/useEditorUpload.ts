/**
 * Editor image/attachment upload composable
 */

import type { Editor } from '@tiptap/core';

import { message } from 'ant-design-vue';

import { $t } from '@vben/locales';

import { requestClient } from '#/utils/request';

import type { AttachmentInfo } from './types';

const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10 MB
const MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024; // 50 MB

function getUploadEndpoint(): string {
  const isAdmin = window.location.pathname.startsWith('/admin');
  return isAdmin ? '/admin/attachments/upload' : '/tenant/attachments/upload';
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
    const res = await requestClient.upload(getUploadEndpoint(), {
      file,
      visibility: 'public',
    });
    const data = (res as Record<string, unknown>).data as Record<
      string,
      unknown
    >;
    return {
      url: data.url as string,
      id: (data.attachment as Record<string, unknown>)?.id as string,
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
    const res = await requestClient.upload(getUploadEndpoint(), {
      file,
      visibility: 'public',
    });
    const data = (res as Record<string, unknown>).data as Record<
      string,
      unknown
    >;
    const attachment = data.attachment as Record<string, unknown>;
    return {
      id: attachment?.id as string,
      name: attachment?.original_filename as string,
      size: attachment?.file_size as number,
      mime_type: attachment?.mime_type as string,
      url: data.url as string,
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
      editor.chain().focus().deleteRange({ from: pos, to: pos + node.nodeSize }).run();
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
      editor
        .chain()
        .focus()
        .setImage({ src: '', alt: placeholder })
        .run();

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
