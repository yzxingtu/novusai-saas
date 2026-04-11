import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useFilePickerCore } from '../use-file-picker-core';

const mocks = vi.hoisted(() => ({
  adminBatchUploadApi: vi.fn(),
  adminGetAttachmentListApi: vi.fn(),
  adminGetUploadRulesApi: vi.fn(),
  adminSmartUploadFile: vi.fn(),
  messageError: vi.fn(),
  messageWarning: vi.fn(),
  tenantBatchUploadApi: vi.fn(),
  tenantGetAttachmentListApi: vi.fn(),
  tenantGetUploadRulesApi: vi.fn(),
  tenantSmartUploadFile: vi.fn(),
}));

vi.mock('@vben/common-ui', () => ({
  useVbenModal: (options?: { onOpenChange?: (isOpen: boolean) => void }) => {
    const api = {
      close: vi.fn(),
      getData: () => null,
      open: () => options?.onOpenChange?.(true),
    };

    return [
      defineComponent({
        name: 'MockModal',
        setup(_, { slots }) {
          return () => h('div', slots.default?.());
        },
      }),
      api,
    ];
  },
}));

vi.mock('ant-design-vue', () => ({
  message: {
    error: mocks.messageError,
    warning: mocks.messageWarning,
  },
}));

vi.mock('#/api/admin/attachment', () => ({
  batchUploadAttachmentsApi: mocks.adminBatchUploadApi,
  getAttachmentListApi: mocks.adminGetAttachmentListApi,
  getUploadRulesApi: mocks.adminGetUploadRulesApi,
  smartUploadFile: mocks.adminSmartUploadFile,
}));

vi.mock('#/api/tenant/attachment', () => ({
  batchUploadAttachmentsApi: mocks.tenantBatchUploadApi,
  getAttachmentListApi: mocks.tenantGetAttachmentListApi,
  getUploadRulesApi: mocks.tenantGetUploadRulesApi,
  smartUploadFile: mocks.tenantSmartUploadFile,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/image', () => ({
  getAttachmentUrl: vi.fn(),
}));

type DragPayload = {
  files?: File[];
  types?: string[];
};

function createDragEvent(payload: DragPayload = {}): DragEvent {
  const { files = [], types = [] } = payload;
  return {
    dataTransfer: {
      files,
      types,
    },
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
  } as unknown as DragEvent;
}

function createFile(
  name: string,
  size: number,
  type = 'application/octet-stream',
) {
  const file = new File(['x'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

type FilePickerCore = ReturnType<typeof useFilePickerCore>;

function createCore(): { core: FilePickerCore; unmount: () => void } {
  let core!: FilePickerCore;
  const wrapper = mount(
    defineComponent({
      name: 'FilePickerCoreHarness',
      setup() {
        core = useFilePickerCore({
          onSelect: vi.fn(),
          props: {
            accept: '*',
            endpoint: 'admin',
            imageOnly: false,
            maxConcurrency: 2,
            maxCount: 3,
            maxFileSize: 10 * 1024 * 1024,
            maxRetries: 1,
            multiple: true,
            visibility: 'private',
          },
        });
        return () => null;
      },
    }),
  );

  return {
    core,
    unmount: () => wrapper.unmount(),
  };
}

describe('useFilePickerCore drag/drop', () => {
  beforeEach(() => {
    mocks.adminBatchUploadApi.mockReset();
    mocks.adminGetAttachmentListApi.mockReset();
    mocks.adminGetUploadRulesApi.mockReset();
    mocks.adminSmartUploadFile.mockReset();
    mocks.messageError.mockReset();
    mocks.messageWarning.mockReset();
    mocks.tenantBatchUploadApi.mockReset();
    mocks.tenantGetAttachmentListApi.mockReset();
    mocks.tenantGetUploadRulesApi.mockReset();
    mocks.tenantSmartUploadFile.mockReset();
    window.history.replaceState({}, '', '/admin');
  });

  it('keeps overlay active until the drag counter returns to zero', () => {
    const { core, unmount } = createCore();
    const dragEvent = createDragEvent({ types: ['Files'] });

    core.onModalDragEnter(dragEvent);
    core.onModalDragEnter(dragEvent);
    expect(core.isDragOver.value).toBe(true);

    core.onModalDragLeave();
    expect(core.isDragOver.value).toBe(true);

    core.onModalDragLeave();
    expect(core.isDragOver.value).toBe(false);
    unmount();
  });

  it('ignores non-file drags for overlay activation', () => {
    const { core, unmount } = createCore();

    core.onModalDragEnter(createDragEvent({ types: ['text/plain'] }));
    expect(core.isDragOver.value).toBe(false);
    unmount();
  });

  it('closes overlay and queues dropped files for upload', () => {
    const { core, unmount } = createCore();
    const droppedFile = createFile('drop.txt', 1024, 'text/plain');
    const dragEvent = createDragEvent({ types: ['Files'] });
    const dropEvent = createDragEvent({ files: [droppedFile], types: ['Files'] });

    mocks.adminSmartUploadFile.mockResolvedValue({
      attachment: { id: 11 },
    });

    core.onModalDragEnter(dragEvent);
    expect(core.isDragOver.value).toBe(true);

    core.onModalDrop(dropEvent);

    expect(core.isDragOver.value).toBe(false);
    expect(core.uploading.value).toBe(true);
    expect(core.uploadTasks.value).toHaveLength(1);
    expect(mocks.adminSmartUploadFile).toHaveBeenCalledTimes(1);
    expect(mocks.adminSmartUploadFile).toHaveBeenCalledWith(
      expect.objectContaining({
        file: droppedFile,
        tenant_id: 0,
        visibility: 'private',
      }),
      expect.any(Function),
      expect.any(Object),
    );
    unmount();
  });
});
