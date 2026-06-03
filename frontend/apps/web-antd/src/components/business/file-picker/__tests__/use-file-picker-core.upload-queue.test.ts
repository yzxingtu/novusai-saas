import type { UnwrapRef } from 'vue';

import type { FilePickerProps, UploadTask } from '../types';

// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FILE_PICKER_BATCH_SIZE_THRESHOLD } from '../file-picker-contracts';
import { useFilePickerCore } from '../use-file-picker-core';

const mockAdminApi = vi.hoisted(() => ({
  batchUploadAttachmentsApi: vi.fn(),
  getAttachmentListApi: vi.fn(),
  getUploadRulesApi: vi.fn(),
  smartUploadFile: vi.fn(),
}));

const mockTenantApi = vi.hoisted(() => ({
  batchUploadAttachmentsApi: vi.fn(),
  getAttachmentListApi: vi.fn(),
  getUploadRulesApi: vi.fn(),
  smartUploadFile: vi.fn(),
}));

const mockModalApi = vi.hoisted(() => ({
  close: vi.fn(),
  getData: vi.fn(() => ({})),
}));

vi.mock('#/api/admin/attachment', () => ({
  batchUploadAttachmentsApi: mockAdminApi.batchUploadAttachmentsApi,
  getAttachmentListApi: mockAdminApi.getAttachmentListApi,
  getUploadRulesApi: mockAdminApi.getUploadRulesApi,
  smartUploadFile: mockAdminApi.smartUploadFile,
}));

vi.mock('#/api/tenant/attachment', () => ({
  batchUploadAttachmentsApi: mockTenantApi.batchUploadAttachmentsApi,
  getAttachmentListApi: mockTenantApi.getAttachmentListApi,
  getUploadRulesApi: mockTenantApi.getUploadRulesApi,
  smartUploadFile: mockTenantApi.smartUploadFile,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/image', () => ({
  getAttachmentUrl: vi.fn(() => 'preview-url'),
}));

vi.mock('ant-design-vue', () => ({
  message: {
    error: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock('@vben/common-ui', async () => {
  const vue = await vi.importActual<typeof import('vue')>('vue');
  return {
    useVbenModal: () => [
      vue.defineComponent({ render: () => null }),
      mockModalApi,
    ],
  };
});

type FilePickerVm = UnwrapRef<ReturnType<typeof useFilePickerCore>>;

const BASE_PROPS: Pick<FilePickerProps, 'endpoint'> &
  Required<Omit<FilePickerProps, 'endpoint'>> = {
  accept: '',
  endpoint: 'admin',
  imageOnly: false,
  maxConcurrency: 2,
  maxCount: 3,
  maxFileSize: 20 * 1024 * 1024,
  maxRetries: 0,
  multiple: true,
  visibility: 'private',
};

function createFile(
  name: string,
  size: number,
  type = 'application/octet-stream',
) {
  const file = new File(['x'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

function createDropEvent(files: File[]) {
  return {
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
    dataTransfer: {
      files,
    },
  } as unknown as DragEvent;
}

function createTask(name: string, status: UploadTask['status']): UploadTask {
  const file = createFile(name, 128);
  return {
    uid: `${name}-${status}`,
    file,
    name,
    size: file.size,
    status,
    percent: status === 'success' ? 100 : 0,
    retryCount: 0,
    error: status === 'error' ? 'boom' : undefined,
  };
}

function mountHarness(props: Partial<FilePickerProps> = {}) {
  const onSelect = vi.fn();
  const wrapper = mount(
    defineComponent({
      name: 'FilePickerCoreHarness',
      setup() {
        return useFilePickerCore({
          onSelect,
          props: {
            ...BASE_PROPS,
            ...props,
          },
        });
      },
      render: () => null,
    }),
  );

  return {
    vm: wrapper.vm as unknown as FilePickerVm,
    onSelect,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockAdminApi.batchUploadAttachmentsApi.mockResolvedValue({ items: [] });
  mockAdminApi.getAttachmentListApi.mockResolvedValue({
    items: [],
    total: 0,
  });
  mockAdminApi.getUploadRulesApi.mockResolvedValue({});
  mockAdminApi.smartUploadFile.mockResolvedValue({
    attachment: { id: 1 },
  });

  mockTenantApi.batchUploadAttachmentsApi.mockResolvedValue({ items: [] });
  mockTenantApi.getAttachmentListApi.mockResolvedValue({
    items: [],
    total: 0,
  });
  mockTenantApi.getUploadRulesApi.mockResolvedValue({});
  mockTenantApi.smartUploadFile.mockResolvedValue({
    attachment: { id: 1 },
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('use-file-picker-core upload queue', () => {
  it('creates queued tasks when handling custom uploads', async () => {
    let resolveUpload:
      | ((value: { attachment?: { id: number } }) => void)
      | undefined;
    const uploadPromise = new Promise<{ attachment?: { id: number } }>(
      (resolve) => {
        resolveUpload = resolve;
      },
    );
    mockAdminApi.smartUploadFile.mockReturnValue(uploadPromise);

    const { vm } = mountHarness();
    const file = createFile('large.bin', FILE_PICKER_BATCH_SIZE_THRESHOLD + 1);
    const onSuccess = vi.fn();

    vm.handleCustomUpload({ file, onSuccess });
    await flushPromises();

    expect(onSuccess).toHaveBeenCalled();
    expect(mockAdminApi.smartUploadFile).toHaveBeenCalledTimes(1);
    expect(vm.uploading).toBe(true);
    expect(vm.uploadTasks).toHaveLength(1);
    expect(vm.uploadTasks[0]?.name).toBe('large.bin');
    expect(vm.uploadTasks[0]?.status).toBe('uploading');

    if (!resolveUpload) {
      throw new Error('Expected upload resolver to be initialized');
    }
    resolveUpload({ attachment: { id: 10 } });
    await flushPromises();
  });

  it('batches small files and queues large files during drop uploads', async () => {
    let resolveUpload:
      | ((value: { attachment?: { id: number } }) => void)
      | undefined;
    const uploadPromise = new Promise<{ attachment?: { id: number } }>(
      (resolve) => {
        resolveUpload = resolve;
      },
    );
    mockAdminApi.smartUploadFile.mockReturnValue(uploadPromise);
    mockAdminApi.batchUploadAttachmentsApi.mockResolvedValue({
      items: [
        { success: true, attachment: { id: 101 } },
        { success: true, attachment: { id: 102 } },
      ],
    });

    const { vm } = mountHarness();
    const smallA = createFile(
      'small-a.png',
      FILE_PICKER_BATCH_SIZE_THRESHOLD - 1,
      'image/png',
    );
    const smallB = createFile(
      'small-b.png',
      FILE_PICKER_BATCH_SIZE_THRESHOLD - 2,
      'image/png',
    );
    const large = createFile(
      'large.zip',
      FILE_PICKER_BATCH_SIZE_THRESHOLD + 4,
      'application/zip',
    );

    vm.onModalDrop(createDropEvent([smallA, smallB, large]));
    await flushPromises();

    expect(mockAdminApi.batchUploadAttachmentsApi).toHaveBeenCalledWith({
      files: [smallA, smallB],
      visibility: 'private',
      tenant_id: 0,
    });
    expect(mockAdminApi.smartUploadFile).toHaveBeenCalledTimes(1);

    const taskNames = vm.uploadTasks.map((task) => task.name);
    expect(taskNames).toEqual(
      expect.arrayContaining(['small-a.png', 'small-b.png', 'large.zip']),
    );
    expect(
      vm.uploadTasks.find((task) => task.name === 'large.zip')?.status,
    ).toBe('uploading');
    expect(
      vm.uploadTasks.filter((task) => task.name.startsWith('small-')),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ status: 'success' }),
        expect.objectContaining({ status: 'success' }),
      ]),
    );

    if (!resolveUpload) {
      throw new Error('Expected upload resolver to be initialized');
    }
    resolveUpload({ attachment: { id: 200 } });
  });

  it('selects uploaded ids and refreshes the list after success', async () => {
    vi.useFakeTimers();
    mockAdminApi.smartUploadFile.mockResolvedValue({
      attachment: { id: 55 },
    });

    const { vm } = mountHarness();
    const file = createFile(
      'avatar.png',
      FILE_PICKER_BATCH_SIZE_THRESHOLD + 2,
      'image/png',
    );

    vm.handleCustomUpload({ file });
    await flushPromises();
    await vi.advanceTimersByTimeAsync(600);
    await flushPromises();

    expect(vm.selectedIds.has(55)).toBe(true);
    expect(mockAdminApi.getAttachmentListApi).toHaveBeenCalledTimes(1);
  });

  it('clears completed and error tasks from the queue', () => {
    const { vm } = mountHarness();
    vm.uploadTasks = [
      createTask('success.log', 'success'),
      createTask('pending.log', 'pending'),
      createTask('error.log', 'error'),
      createTask('uploading.log', 'uploading'),
      createTask('cancelled.log', 'cancelled'),
    ];

    vm.clearCompletedTasks();
    expect(vm.uploadTasks.map((task) => task.status)).toEqual(
      expect.arrayContaining(['pending', 'error', 'uploading']),
    );
    expect(vm.uploadTasks.some((task) => task.status === 'success')).toBe(
      false,
    );
    expect(vm.uploadTasks.some((task) => task.status === 'cancelled')).toBe(
      false,
    );

    vm.clearErrors();
    expect(vm.uploadTasks.some((task) => task.status === 'error')).toBe(false);
  });

  it('retries all error tasks and restarts uploads', async () => {
    let resolveUpload:
      | ((value: { attachment?: { id: number } }) => void)
      | undefined;
    const uploadPromise = new Promise<{ attachment?: { id: number } }>(
      (resolve) => {
        resolveUpload = resolve;
      },
    );
    mockAdminApi.smartUploadFile.mockReturnValue(uploadPromise);

    const { vm } = mountHarness({ maxConcurrency: 5 });
    vm.uploadTasks = [
      createTask('error-a.log', 'error'),
      createTask('error-b.log', 'error'),
    ];

    vm.retryAllErrors();
    await flushPromises();

    expect(mockAdminApi.smartUploadFile).toHaveBeenCalledTimes(2);
    expect(vm.uploadTasks.every((task) => task.status === 'uploading')).toBe(
      true,
    );

    if (!resolveUpload) {
      throw new Error('Expected upload resolver to be initialized');
    }
    resolveUpload({ attachment: { id: 301 } });
  });
});
