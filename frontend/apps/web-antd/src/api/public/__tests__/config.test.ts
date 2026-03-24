import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getPlatformPublicConfigApi,
  getTenantPublicConfigApi,
} from '../config';

const requestMocks = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('#/utils/request', () => ({
  baseRequestClient: requestMocks,
}));

vi.mock('#/utils/image', () => ({
  toAttachmentImageUrl: (value?: string) =>
    value ? `/api/public/attachments/${value}/image` : '',
}));

describe('public config api transforms', () => {
  beforeEach(() => {
    requestMocks.get.mockReset();
  });

  it('maps platform public config storage and branding fields', async () => {
    requestMocks.get.mockResolvedValueOnce({
      data: {
        code: 0,
        data: {
          captcha_provider: 'slider',
          login_captcha_enabled: true,
          logo_dark: '15',
          runtime_limits: {
            page_context_max_bytes: 8192,
          },
          site_copyright: 'Platform Copyright',
          site_description: 'Platform Description',
          site_favicon: '26',
          site_icp: 'ICP 123456',
          site_logo: '10',
          site_name: 'Platform Site',
          storage: {
            allowed_extensions: 'png,jpg',
            base_url: 'https://cdn.example.com',
            chunk_size_mb: 5,
            driver: 'local',
            max_file_size_mb: 100,
          },
          tenant_domain_suffix: '.app.example.com',
        },
        message: 'ok',
      },
    });

    const result = await getPlatformPublicConfigApi();

    expect(result.brand).toEqual({
      copyright: 'Platform Copyright',
      favicon: '/api/public/attachments/26/image',
      icp: 'ICP 123456',
      logo: '/api/public/attachments/10/image',
      logoDark: '/api/public/attachments/15/image',
      primaryColor: undefined,
      siteDescription: 'Platform Description',
      siteName: 'Platform Site',
    });
    expect(result.login.captcha.provider).toBe('slider');
    expect(result.login.captcha.type).toBe('slider');
    expect(result.storage).toEqual({
      allowedExtensions: 'png,jpg',
      baseUrl: 'https://cdn.example.com',
      chunkSizeMb: 5,
      driver: 'local',
      maxFileSizeMb: 100,
    });
    expect(result.runtimeLimits?.pageContextMaxBytes).toBe(8192);
  });

  it('maps tenant public config dark logo, icp, and storage fields', async () => {
    requestMocks.get.mockResolvedValueOnce({
      data: {
        code: 0,
        data: {
          captcha_provider: 'slider',
          favicon_url: '12',
          footer_copyright: 'Tenant Copyright',
          icp: 'ICP 654321',
          login_bg: '13',
          login_subtitle: 'Tenant Subtitle',
          login_title: 'Tenant Site',
          logo_dark_url: '14',
          logo_url: '11',
          storage: {
            allowed_extensions: 'pdf,docx',
            base_url: 'https://tenant-cdn.example.com',
            chunk_size_mb: 8,
            driver: 's3',
            max_file_size_mb: 256,
          },
          tenant_code: 'acme',
          tenant_id: 1,
          tenant_name: 'Acme Inc',
        },
        message: 'ok',
      },
    });

    const result = await getTenantPublicConfigApi();

    expect(result.brand).toEqual({
      copyright: 'Tenant Copyright',
      favicon: '/api/public/attachments/12/image',
      icp: 'ICP 654321',
      loginBg: '/api/public/attachments/13/image',
      logo: '/api/public/attachments/11/image',
      logoDark: '/api/public/attachments/14/image',
      siteDescription: 'Tenant Subtitle',
      siteName: 'Tenant Site',
    });
    expect(result.storage).toEqual({
      allowedExtensions: 'pdf,docx',
      baseUrl: 'https://tenant-cdn.example.com',
      chunkSizeMb: 8,
      driver: 's3',
      maxFileSizeMb: 256,
    });
  });
});
