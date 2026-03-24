import type { BrandConfig } from '#/api/public/config';

interface CopyrightPreferencesLike {
  companyName?: string;
  companySiteLink?: string;
  enable?: boolean;
  icp?: string;
}

export function mergeBrandConfig(
  platformBrand?: BrandConfig | null,
  tenantBrand?: BrandConfig | null,
): BrandConfig {
  return {
    siteName: tenantBrand?.siteName || platformBrand?.siteName,
    siteDescription:
      tenantBrand?.siteDescription || platformBrand?.siteDescription,
    logo: tenantBrand?.logo || platformBrand?.logo,
    logoDark: tenantBrand?.logoDark || platformBrand?.logoDark,
    favicon: tenantBrand?.favicon || platformBrand?.favicon,
    primaryColor: tenantBrand?.primaryColor || platformBrand?.primaryColor,
    loginBg: tenantBrand?.loginBg || platformBrand?.loginBg,
    copyright: tenantBrand?.copyright || platformBrand?.copyright,
    icp: tenantBrand?.icp || platformBrand?.icp,
  };
}

export function resolveCopyrightDisplay(preference: unknown): {
  companyName: string;
  meta: string;
  visible: boolean;
} {
  const value = (preference ?? {}) as CopyrightPreferencesLike;
  const companyName = value.companyName?.trim() ?? '';
  const meta = value.icp?.trim() || value.companySiteLink?.trim() || '';

  return {
    companyName,
    meta,
    visible: value.enable !== false && Boolean(companyName || meta),
  };
}
