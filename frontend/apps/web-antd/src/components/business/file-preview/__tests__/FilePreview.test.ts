/* eslint-disable vue/one-component-per-file */
import { mount } from '@vue/test-utils';
import { defineComponent, h, nextTick } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import FilePreview from '../FilePreview.vue';

const mocks = vi.hoisted(() => ({
  downloadAdminAttachmentApi: vi.fn(),
  downloadTenantAttachmentApi: vi.fn(),
  downloadUserAttachmentApi: vi.fn(),
  getAdminAttachmentPreviewUrlApi: vi.fn(),
  getAttachmentUrl: vi.fn(),
  getTenantAttachmentPreviewUrlApi: vi.fn(),
  getUserAttachmentPreviewUrlApi: vi.fn(),
  messageError: vi.fn(),
}));

vi.mock('@vben/common-ui', () => ({
  useVbenModal: (options?: { onOpenChange?: (isOpen: boolean) => void }) => {
    const api = {
      close: () => options?.onOpenChange?.(false),
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

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIcon',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('ant-design-vue', () => ({
  Button: defineComponent({
    name: 'ButtonStub',
    template: '<button><slot /></button>',
  }),
  Image: defineComponent({
    name: 'ImageStub',
    props: {
      alt: {
        default: '',
        type: String,
      },
      src: {
        default: '',
        type: String,
      },
    },
    template: '<img :alt="alt" :src="src" />',
  }),
  Spin: defineComponent({
    name: 'SpinStub',
    template: '<div><slot /></div>',
  }),
  message: {
    error: mocks.messageError,
  },
}));

vi.mock('#/api/admin/attachment', () => ({
  downloadAttachmentApi: mocks.downloadAdminAttachmentApi,
  getAttachmentPreviewUrlApi: mocks.getAdminAttachmentPreviewUrlApi,
}));

vi.mock('#/api/tenant/attachment', () => ({
  downloadAttachmentApi: mocks.downloadTenantAttachmentApi,
  getAttachmentPreviewUrlApi: mocks.getTenantAttachmentPreviewUrlApi,
}));

vi.mock('#/api/user/attachment', () => ({
  downloadAttachmentApi: mocks.downloadUserAttachmentApi,
  getAttachmentPreviewUrlApi: mocks.getUserAttachmentPreviewUrlApi,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/image', () => ({
  getAttachmentUrl: mocks.getAttachmentUrl,
}));

describe('filePreview', () => {
  beforeEach(() => {
    mocks.downloadAdminAttachmentApi.mockReset();
    mocks.downloadTenantAttachmentApi.mockReset();
    mocks.downloadUserAttachmentApi.mockReset();
    mocks.getAdminAttachmentPreviewUrlApi.mockReset();
    mocks.getAttachmentUrl.mockReset();
    mocks.getTenantAttachmentPreviewUrlApi.mockReset();
    mocks.getUserAttachmentPreviewUrlApi.mockReset();
    mocks.messageError.mockReset();
  });

  it('uses signed attachment preview for private images instead of anonymous image url', async () => {
    const signedPreviewUrl =
      '/api/public/attachments/9/image?exp=1&sign=abc&token=jwt&p=preview';
    mocks.getAttachmentUrl.mockReturnValue(signedPreviewUrl);

    const wrapper = mount(FilePreview, {
      props: {
        endpoint: 'tenant',
        file: {
          category: 'image',
          createdAt: '2026-03-23T00:00:00Z',
          id: 9,
          name: 'secret.png',
          previewUrl:
            '/api/public/attachments/9/image?exp=1&sign=abc&token=jwt',
          size: 128,
          status: 'active',
          visibility: 'private',
        },
      },
    });

    (wrapper.vm as unknown as { open: () => void }).open();
    await nextTick();

    expect(mocks.getAttachmentUrl).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 9,
        previewUrl: '/api/public/attachments/9/image?exp=1&sign=abc&token=jwt',
      }),
      { preset: 'preview' },
    );
    expect(mocks.getTenantAttachmentPreviewUrlApi).not.toHaveBeenCalled();
    expect(wrapper.find('img').attributes('src')).toBe(signedPreviewUrl);
  });

  it('supports user endpoint preview and download for non-image files', async () => {
    mocks.getUserAttachmentPreviewUrlApi.mockResolvedValue({
      url: '/api/user/attachments/15/preview-url?token=abc',
    });
    mocks.downloadUserAttachmentApi.mockResolvedValue(undefined);

    const wrapper = mount(FilePreview, {
      props: {
        endpoint: 'user',
        file: {
          category: 'document',
          createdAt: '2026-03-23T00:00:00Z',
          id: 15,
          mimeType: 'text/plain',
          name: 'notes.txt',
          size: 256,
          status: 'active',
          visibility: 'private',
        },
      },
    });

    (wrapper.vm as unknown as { open: () => void }).open();
    await nextTick();
    await nextTick();

    expect(mocks.getUserAttachmentPreviewUrlApi).toHaveBeenCalledWith(15);
    expect(mocks.getTenantAttachmentPreviewUrlApi).not.toHaveBeenCalled();
    expect(mocks.getAdminAttachmentPreviewUrlApi).not.toHaveBeenCalled();

    const buttons = wrapper.findAll('button');
    expect(buttons.length).toBeGreaterThan(0);
    const downloadButton = buttons.at(-1);
    if (!downloadButton) {
      throw new Error('Download button not found');
    }
    await downloadButton.trigger('click');

    expect(mocks.downloadUserAttachmentApi).toHaveBeenCalledWith(
      15,
      'notes.txt',
      'text/plain',
    );
  });
});
