import type { InstallManifestSummary } from '#/api/admin/plugin';

import { describe, expect, it, vi } from 'vitest';

import { resolvePluginCompatibilityProfile } from '#/api/admin/plugin';

import {
  deriveInstallPreviewPluginType,
  summarizeInstallManifest,
} from '../plugin-preview';

vi.mock('#/utils/request', () => ({
  requestClient: {},
}));

describe('plugin preview helpers', () => {
  it('[structural] derives plugin type from install summary instead of manifest shape', () => {
    const installManifest: InstallManifestSummary = {
      skills: 1,
      api_routes: 2,
    };

    expect(deriveInstallPreviewPluginType(installManifest)).toBe('composite');
    expect(
      deriveInstallPreviewPluginType({
        api_routes: 1,
      }),
    ).toBe('api');
    expect(deriveInstallPreviewPluginType({})).toBe('basic');
  });

  it('[structural] summarizes visible frontend extension counts with localized labels', () => {
    const installManifest: InstallManifestSummary = {
      frontend_pages: 1,
      frontend_pages_details: ['Docs'],
      page_menus: 1,
      page_menus_details: ['Docs Menu'],
      header_widgets: 1,
      header_widgets_details: ['weather-header'],
      dashboard_widgets: 1,
      dashboard_widgets_details: ['Weather Overview'],
      settings_tabs: 0,
      settings_tabs_details: ['Should be ignored'],
    };

    const summary = summarizeInstallManifest(
      installManifest,
      (key) => `label:${key}`,
    );

    expect(summary).toEqual([
      {
        type: 'frontend_pages',
        count: 1,
        icon: 'lucide:file-stack',
        label: 'label:admin.plugin.structureType.frontend_pages',
        details: ['Docs'],
      },
      {
        type: 'page_menus',
        count: 1,
        icon: 'lucide:menu',
        label: 'label:admin.plugin.structureType.page_menus',
        details: ['Docs Menu'],
      },
      {
        type: 'header_widgets',
        count: 1,
        icon: 'lucide:panel-top',
        label: 'label:admin.plugin.structureType.header_widgets',
        details: ['weather-header'],
      },
      {
        type: 'dashboard_widgets',
        count: 1,
        icon: 'lucide:layout-dashboard',
        label: 'label:admin.plugin.structureType.dashboard_widgets',
        details: ['Weather Overview'],
      },
    ]);
  });

  it('[structural] resolves compatibility profile edition and tenant exposure fields', () => {
    const profile = resolvePluginCompatibilityProfile({
      scope: 'all_tenants',
      compatibility_profile: {
        editions: ['saas', 'single_management'],
        surfaces: ['admin', 'user'],
        tenant_assignment_required: true,
        tenant_exposure: 'selected_tenants',
      },
    });

    expect(profile).toEqual(
      expect.objectContaining({
        editions: ['saas', 'single_management'],
        saasCompatible: true,
        singleManagementCompatible: true,
        surfaces: ['admin', 'user'],
        tenantAssignmentRequired: true,
        tenantExposureMode: 'selected_tenants',
      }),
    );
  });

  it('[structural] ignores legacy compatibility profile sources and scope-derived exposure', () => {
    const legacySource = {
      compatibility: {
        editions: ['single_management'],
        tenant_exposure: 'selected_tenants',
      },
      manifest: {
        compatibility_profile: {
          editions: ['single_management'],
          tenant_exposure: 'selected_tenants',
        },
      },
      plugin_info: {
        compatibility_profile: {
          editions: ['single_management'],
          tenant_exposure: 'selected_tenants',
        },
      },
      scope: 'selected_tenants',
    };

    expect(resolvePluginCompatibilityProfile(legacySource)).toEqual({
      editions: ['saas'],
      saasCompatible: true,
      singleManagementCompatible: false,
      surfaces: [],
      tenantAssignmentRequired: false,
      tenantExposureMode: 'scope_default',
    });
  });

  it('[structural] accepts only canonical compatibility profile values', () => {
    const profile = resolvePluginCompatibilityProfile({
      compatibility_profile: {
        declared_editions: ['saas'],
        editions: ['single-management', 'single_management'],
        is_saas_compatible: true,
        is_single_management_compatible: false,
        surfaces: ['platform-admin', 'admin', 'Tenant', 'tenant'],
        tenant_assignment_required: false,
        tenant_exposure: 'specified_tenants',
      },
    });

    expect(profile).toEqual({
      editions: ['single_management'],
      saasCompatible: false,
      singleManagementCompatible: true,
      surfaces: ['admin', 'tenant'],
      tenantAssignmentRequired: false,
      tenantExposureMode: 'scope_default',
    });
  });
});
