// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => ({
  isExtensionAllowed: vi.fn(),
  warning: vi.fn(),
}));

vi.mock('ant-design-vue', () => ({
  message: {
    warning: mockRefs.warning,
  },
}));

vi.mock('#/locales', () => ({
  $t: (key: string, params?: Record<string, unknown>) =>
    `${key}:${params?.extension ?? params?.max ?? ''}`,
}));

vi.mock('#/constants/upload', () => ({
  CHAT_MAX_FILE_SIZE_MB: 20,
  PLATFORM_ALLOWED_EXTENSIONS: new Set(['png', 'txt']),
  PLATFORM_DENIED_EXTENSIONS: new Set(['exe']),
  PLATFORM_MAX_FILE_SIZE_MB: 10,
  isExtensionAllowed: mockRefs.isExtensionAllowed,
}));

describe('useFileUpload', () => {
  beforeEach(() => {
    mockRefs.isExtensionAllowed.mockReset();
    mockRefs.warning.mockReset();
  });

  it('rejects files with disallowed extensions', async () => {
    const { useFileUpload } = await import('../use-file-upload');
    mockRefs.isExtensionAllowed.mockReturnValue(false);
    const file = new File(['demo'], 'virus.exe', {
      type: 'application/octet-stream',
    });

    const result = useFileUpload().validateFile(file);

    expect(result).toEqual({
      valid: false,
      errorMessage: 'common.uploadValidation.extensionNotAllowed:exe',
    });
    expect(mockRefs.warning).toHaveBeenCalledWith(
      'common.uploadValidation.extensionNotAllowed:exe',
    );
  });

  it('rejects chat images when vision support is disabled', async () => {
    const { useFileUpload } = await import('../use-file-upload');
    mockRefs.isExtensionAllowed.mockReturnValue(true);
    const file = new File(['img'], 'image.png', { type: 'image/png' });

    const result = useFileUpload().validateChatFile(file, {
      supportsVision: false,
    });

    expect(result).toEqual({
      valid: false,
      errorMessage: 'common.globalAiChat.imageNotSupported:',
    });
  });

  it('revokes preview urls for all attachments', async () => {
    const { useFileUpload } = await import('../use-file-upload');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', {
      revokeObjectURL,
    });

    useFileUpload().revokePreviewUrls([
      { preview: 'blob:one' },
      { preview: 'blob:two' },
      {},
    ]);

    expect(revokeObjectURL).toHaveBeenNthCalledWith(1, 'blob:one');
    expect(revokeObjectURL).toHaveBeenNthCalledWith(2, 'blob:two');
  });
});
