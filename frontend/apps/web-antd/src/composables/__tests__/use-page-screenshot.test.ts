// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => ({
  buildChatAttachmentFromUpload: vi.fn(),
  createObjectURL: vi.fn(() => 'blob:preview'),
  html2canvas: vi.fn(),
  resolveEndpointByPath: vi.fn(),
  showRequestError: vi.fn(),
  uploadChatFileApi: vi.fn(),
  warning: vi.fn(),
}));

vi.mock('html2canvas', () => ({
  default: mockRefs.html2canvas,
}));

vi.mock('ant-design-vue', () => ({
  message: {
    warning: mockRefs.warning,
  },
}));

vi.mock('#/api/shared/ai-chat', () => ({
  buildChatAttachmentFromUpload: mockRefs.buildChatAttachmentFromUpload,
  uploadChatFileApi: mockRefs.uploadChatFileApi,
}));

vi.mock('#/constants/endpoints', () => ({
  resolveEndpointByPath: mockRefs.resolveEndpointByPath,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/types/endpoint', () => ({
  EndpointType: {
    ADMIN: 'admin',
    TENANT: 'tenant',
    USER: 'user',
  },
}));

vi.mock('#/utils/error-helpers', () => ({
  showRequestError: mockRefs.showRequestError,
}));

function createCanvas(blob: Blob) {
  return {
    height: 600,
    toBlob: (callback: (value: Blob | null) => void) => callback(blob),
    width: 800,
  } as unknown as HTMLCanvasElement;
}

describe('page screenshot helpers', () => {
  beforeEach(() => {
    mockRefs.buildChatAttachmentFromUpload.mockReset();
    mockRefs.createObjectURL.mockReset();
    mockRefs.createObjectURL.mockReturnValue('blob:preview');
    mockRefs.html2canvas.mockReset();
    mockRefs.resolveEndpointByPath.mockReset();
    mockRefs.showRequestError.mockReset();
    mockRefs.uploadChatFileApi.mockReset();
    mockRefs.warning.mockReset();
    vi.stubGlobal('URL', {
      createObjectURL: mockRefs.createObjectURL,
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('resolves upload target by current endpoint type', async () => {
    const { resolveScreenshotUploadTarget } = await import('../use-page-screenshot');

    mockRefs.resolveEndpointByPath.mockReturnValueOnce('admin');
    expect(resolveScreenshotUploadTarget('/admin/agents', 'example.com')).toEqual({
      uploadUrl: '/admin/attachments/upload',
      extraData: { tenant_id: '0' },
    });

    mockRefs.resolveEndpointByPath.mockReturnValueOnce('tenant');
    expect(resolveScreenshotUploadTarget('/tenant/agents', 'tenant.example.com')).toEqual({
      uploadUrl: '/tenant/attachments/upload',
    });

    mockRefs.resolveEndpointByPath.mockReturnValueOnce('user');
    expect(resolveScreenshotUploadTarget('/ai-chat', 'user.example.com')).toEqual({
      uploadUrl: '/api/user/attachments/upload',
    });
  });

  it('captures and uploads a screenshot through the composable facade', async () => {
    const { usePageScreenshot } = await import('../use-page-screenshot');

    mockRefs.html2canvas.mockResolvedValue(
      createCanvas(new Blob(['image'], { type: 'image/jpeg' })),
    );
    mockRefs.uploadChatFileApi.mockResolvedValue({ id: 'upload-1' });
    mockRefs.buildChatAttachmentFromUpload.mockReturnValue({
      id: 'attachment-1',
      name: 'screenshot.jpg',
    });

    const { captureAndUpload, capturing } = usePageScreenshot();
    const result = await captureAndUpload({
      uploadUrl: '/admin/attachments/upload',
      extraData: { tenant_id: '0' },
      target: document.body,
    });

    expect(result?.attachment.preview).toBe('blob:preview');
    expect(result?.blob.type).toBe('image/jpeg');
    expect(mockRefs.uploadChatFileApi).toHaveBeenCalledWith(
      '/admin/attachments/upload',
      expect.any(File),
      { tenant_id: '0' },
    );
    expect(capturing.value).toBe(false);
  });

  it('reports request errors when screenshot capture fails', async () => {
    const { capturePageScreenshot } = await import('../use-page-screenshot');

    mockRefs.html2canvas.mockRejectedValue(new Error('capture failed'));

    const result = await capturePageScreenshot({
      uploadUrl: '/tenant/attachments/upload',
      target: document.body,
    });

    expect(result).toBeNull();
    expect(mockRefs.showRequestError).toHaveBeenCalledWith(
      expect.any(Error),
      'common.globalAiChat.screenshotFailed',
    );
  });
});
