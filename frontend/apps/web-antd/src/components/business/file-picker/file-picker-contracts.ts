import type {
  AttachmentListQueryParams,
  FilePickerProps,
  UploadRules,
} from './types';

import { formatFileSize } from '#/utils/file';

type FilePickerTranslate = (
  key: string,
  params?: Record<string, unknown>,
) => string;

interface BuildFilePickerListQueryOptions {
  acceptMimeFilter: string;
  categoryFilter: string;
  currentPage: number;
  imageOnly: boolean;
  pageSize: number;
  searchKeyword: string;
}

interface BuildFilePickerUploadPlanOptions {
  batchMaxFiles?: number;
  batchSizeThreshold?: number;
  files: File[];
}

interface FilePickerUploadPlan {
  batchedFiles: File[][];
  queuedFiles: File[];
}

interface NormalizeUploadRulesResponse {
  allowed_extensions?: null | string;
  denied_extensions?: null | string;
  max_file_size_mb?: null | number;
}

interface ValidateFilePickerFileOptions {
  effectiveMaxFileSize: number;
  file: File;
  imageOnly: boolean;
  translate: FilePickerTranslate;
  uploadRules: null | UploadRules;
}

export const FILE_PICKER_BATCH_SIZE_THRESHOLD = 5 * 1024 * 1024;
export const FILE_PICKER_BATCH_MAX_FILES = 20;

export function resolveFilePickerEndpoint(
  explicitEndpoint: FilePickerProps['endpoint'],
  pathname: string,
): 'admin' | 'tenant' {
  if (explicitEndpoint) return explicitEndpoint;
  return pathname.startsWith('/admin') ? 'admin' : 'tenant';
}

export function resolveAcceptMimeFilter(accept: FilePickerProps['accept']) {
  if (!accept || accept === '*') return '';
  const parts = accept.split(',').map((item) => item.trim());
  const mimeWild = parts.find((item) => item.endsWith('/*'));
  return mimeWild ? mimeWild.replace('/*', '') : '';
}

export function buildFilePickerListQuery(
  options: BuildFilePickerListQueryOptions,
): AttachmentListQueryParams {
  const {
    acceptMimeFilter,
    categoryFilter,
    currentPage,
    imageOnly,
    pageSize,
    searchKeyword,
  } = options;

  const params: AttachmentListQueryParams = {
    page: currentPage,
    page_size: pageSize,
    sort: '-created_at',
  };

  if (searchKeyword) {
    params['filter[name][ilike]'] = searchKeyword;
  }

  if (categoryFilter) {
    params['filter[mime_type][ilike]'] = `${categoryFilter}/`;
  } else if (imageOnly) {
    params['filter[mime_type][ilike]'] = 'image/';
  } else if (acceptMimeFilter) {
    params['filter[mime_type][ilike]'] = `${acceptMimeFilter}/`;
  }

  return params;
}

export function normalizeUploadRulesResponse(
  rules: NormalizeUploadRulesResponse,
): UploadRules {
  return {
    allowedExtensions: rules.allowed_extensions ?? '',
    deniedExtensions: rules.denied_extensions ?? '',
    maxFileSizeMb: rules.max_file_size_mb ?? 100,
  };
}

function normalizeExtensionList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim().toLowerCase().replace(/^\./, ''))
    .filter(Boolean);
}

export function validateFilePickerFile(
  options: ValidateFilePickerFileOptions,
): null | string {
  const { effectiveMaxFileSize, file, imageOnly, translate, uploadRules } =
    options;

  if (file.size > effectiveMaxFileSize) {
    return translate('shared.filePicker.fileTooLarge', {
      maxSize: formatFileSize(effectiveMaxFileSize),
    });
  }

  if (imageOnly && !file.type.startsWith('image/')) {
    return translate('shared.filePicker.onlyImages');
  }

  if (!file.name.trim()) {
    return translate('shared.filePicker.invalidFileName');
  }

  if (!uploadRules) return null;

  const extension = file.name.includes('.')
    ? (file.name.split('.').pop()?.toLowerCase() ?? '')
    : '';
  if (!extension) return null;

  const allowed = normalizeExtensionList(uploadRules.allowedExtensions);
  if (allowed.length > 0 && !allowed.includes(extension)) {
    return translate('shared.filePicker.extensionNotAllowed', {
      ext: extension,
    });
  }

  const denied = normalizeExtensionList(uploadRules.deniedExtensions);
  if (denied.includes(extension)) {
    return translate('shared.filePicker.extensionDenied', { ext: extension });
  }

  return null;
}

export function buildFilePickerUploadPlan(
  options: BuildFilePickerUploadPlanOptions,
): FilePickerUploadPlan {
  const {
    batchMaxFiles = FILE_PICKER_BATCH_MAX_FILES,
    batchSizeThreshold = FILE_PICKER_BATCH_SIZE_THRESHOLD,
    files,
  } = options;

  const queuedFiles = files.filter((file) => file.size > batchSizeThreshold);
  const smallFiles = files.filter((file) => file.size <= batchSizeThreshold);

  if (smallFiles.length < 2) {
    return {
      batchedFiles: [],
      queuedFiles: [...queuedFiles, ...smallFiles],
    };
  }

  const batchedFiles: File[][] = [];
  for (let index = 0; index < smallFiles.length; index += batchMaxFiles) {
    batchedFiles.push(smallFiles.slice(index, index + batchMaxFiles));
  }

  return {
    batchedFiles,
    queuedFiles,
  };
}
