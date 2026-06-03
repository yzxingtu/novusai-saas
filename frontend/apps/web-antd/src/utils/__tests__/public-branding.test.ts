import { describe, expect, it } from 'vitest';

import { mergeBrandConfig, resolveCopyrightDisplay } from '../public-branding';

describe('public-branding helpers', () => {
  it('merges tenant brand fields over platform defaults', () => {
    expect(
      mergeBrandConfig(
        {
          copyright: 'Platform Copyright',
          favicon: '/platform.ico',
          icp: 'ICP 123',
          logo: '/platform-logo.png',
          siteDescription: 'Platform Description',
          siteName: 'Platform',
        },
        {
          logo: '/tenant-logo.png',
          siteName: 'Tenant',
        },
      ),
    ).toEqual({
      copyright: 'Platform Copyright',
      favicon: '/platform.ico',
      icp: 'ICP 123',
      logo: '/tenant-logo.png',
      logoDark: undefined,
      loginBg: undefined,
      primaryColor: undefined,
      siteDescription: 'Platform Description',
      siteName: 'Tenant',
    });
  });

  it('prefers icp over legacy companySiteLink when building footer text', () => {
    expect(
      resolveCopyrightDisplay({
        companyName: 'NovusAI',
        companySiteLink: 'https://www.vben.pro',
        enable: true,
        icp: 'ICP 123456',
      }),
    ).toEqual({
      companyName: 'NovusAI',
      meta: 'ICP 123456',
      visible: true,
    });
  });
});
