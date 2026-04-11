import { describe, expect, it } from 'vitest';

import {
  buildFilePickerListQuery,
  buildFilePickerUploadPlan,
  FILE_PICKER_BATCH_MAX_FILES,
  FILE_PICKER_BATCH_SIZE_THRESHOLD,
  normalizeUploadRulesResponse,
  resolveAcceptMimeFilter,
  resolveFilePickerEndpoint,
  validateFilePickerFile,
} from '../file-picker-contracts';

function createFile(
  name: string,
  size: number,
  type: string = 'application/octet-stream',
) {
  const file = new File(['x'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

const translate = (key: string, params?: Record<string, unknown>) =>
  `${key}:${JSON.stringify(params ?? {})}`;

describe('file-picker-contracts', () => {
  it('prefers an explicit endpoint and otherwise derives it from the pathname', () => {
    expect(
      resolveFilePickerEndpoint('tenant', '/admin/system/attachments'),
    ).toBe('tenant');
    expect(
      resolveFilePickerEndpoint(undefined, '/admin/system/attachments'),
    ).toBe('admin');
    expect(
      resolveFilePickerEndpoint(undefined, '/tenant/system/attachments'),
    ).toBe('tenant');
  });

  it('extracts the wildcard MIME family from accept filters', () => {
    expect(resolveAcceptMimeFilter('image/*,.png')).toBe('image');
    expect(resolveAcceptMimeFilter('application/pdf')).toBe('');
    expect(resolveAcceptMimeFilter('*')).toBe('');
  });

  it('builds list query params with the right filter precedence', () => {
    expect(
      buildFilePickerListQuery({
        acceptMimeFilter: 'image',
        categoryFilter: 'document',
        currentPage: 2,
        imageOnly: true,
        pageSize: 18,
        searchKeyword: 'contract',
      }),
    ).toEqual({
      'filter[mime_type][ilike]': 'document/',
      'filter[name][ilike]': 'contract',
      page: 2,
      page_size: 18,
      sort: '-created_at',
    });

    expect(
      buildFilePickerListQuery({
        acceptMimeFilter: 'audio',
        categoryFilter: '',
        currentPage: 1,
        imageOnly: false,
        pageSize: 18,
        searchKeyword: '',
      }),
    ).toEqual({
      'filter[mime_type][ilike]': 'audio/',
      page: 1,
      page_size: 18,
      sort: '-created_at',
    });
  });

  it('normalizes upload rules responses into the local contract', () => {
    expect(
      normalizeUploadRulesResponse({
        allowed_extensions: '.png,.jpg',
        denied_extensions: '.exe',
        max_file_size_mb: 32,
      }),
    ).toEqual({
      allowedExtensions: '.png,.jpg',
      deniedExtensions: '.exe',
      maxFileSizeMb: 32,
    });

    expect(normalizeUploadRulesResponse({})).toEqual({
      allowedExtensions: '',
      deniedExtensions: '',
      maxFileSizeMb: 100,
    });
  });

  it('validates file size, image-only mode, and extension allow/deny rules', () => {
    expect(
      validateFilePickerFile({
        effectiveMaxFileSize: 512,
        file: createFile('huge.png', 1024, 'image/png'),
        imageOnly: false,
        translate,
        uploadRules: null,
      }),
    ).toContain('shared.filePicker.fileTooLarge');

    expect(
      validateFilePickerFile({
        effectiveMaxFileSize: 2048,
        file: createFile('report.pdf', 128, 'application/pdf'),
        imageOnly: true,
        translate,
        uploadRules: null,
      }),
    ).toBe('shared.filePicker.onlyImages:{}');

    expect(
      validateFilePickerFile({
        effectiveMaxFileSize: 2048,
        file: createFile('report.pdf', 128, 'application/pdf'),
        imageOnly: false,
        translate,
        uploadRules: {
          allowedExtensions: '.png,.jpg',
          deniedExtensions: '',
          maxFileSizeMb: 50,
        },
      }),
    ).toBe('shared.filePicker.extensionNotAllowed:{"ext":"pdf"}');

    expect(
      validateFilePickerFile({
        effectiveMaxFileSize: 2048,
        file: createFile('script.exe', 128),
        imageOnly: false,
        translate,
        uploadRules: {
          allowedExtensions: '',
          deniedExtensions: '.exe,.bat',
          maxFileSizeMb: 50,
        },
      }),
    ).toBe('shared.filePicker.extensionDenied:{"ext":"exe"}');
  });

  it('groups small files into batch uploads and keeps large files in the queue', () => {
    const smallFiles = Array.from({ length: 23 }, (_, index) =>
      createFile(
        `small-${index}.png`,
        FILE_PICKER_BATCH_SIZE_THRESHOLD - 1,
        'image/png',
      ),
    );
    const largeFile = createFile(
      'large.zip',
      FILE_PICKER_BATCH_SIZE_THRESHOLD + 1,
      'application/zip',
    );

    const plan = buildFilePickerUploadPlan({
      files: [...smallFiles, largeFile],
    });

    expect(plan.queuedFiles).toEqual([largeFile]);
    expect(plan.batchedFiles).toHaveLength(2);
    expect(plan.batchedFiles[0]).toHaveLength(FILE_PICKER_BATCH_MAX_FILES);
    expect(plan.batchedFiles[1]).toHaveLength(3);
  });

  it('leaves a single small file in the regular queue instead of forcing a batch call', () => {
    const onlyFile = createFile(
      'single.txt',
      FILE_PICKER_BATCH_SIZE_THRESHOLD - 1,
      'text/plain',
    );

    expect(
      buildFilePickerUploadPlan({
        files: [onlyFile],
      }),
    ).toEqual({
      batchedFiles: [],
      queuedFiles: [onlyFile],
    });
  });
});
