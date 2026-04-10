import type { AttachmentListParams } from '#/types/attachment';

export interface FilePickerProps {
  accept?: string;
  endpoint?: 'admin' | 'tenant';
  imageOnly?: boolean;
  maxConcurrency?: number;
  maxCount?: number;
  maxFileSize?: number;
  maxRetries?: number;
  multiple?: boolean;
  visibility?: 'private' | 'public';
}

export interface UploadTask {
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

export interface UploadRules {
  allowedExtensions: string;
  deniedExtensions: string;
  maxFileSizeMb: number;
}

export type AttachmentListQueryParams = AttachmentListParams;
