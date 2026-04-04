import type { InstallManifestSummary } from '#/api/admin/plugin';

import { describe, expect, it } from 'vitest';

import {
  deriveInstallPreviewPluginType,
  summarizeInstallManifest,
} from '../plugin-preview';

describe('plugin preview helpers', () => {
  it('derives plugin type from install summary instead of manifest shape', () => {
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

  it('summarizes visible frontend extension counts with localized labels', () => {
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
});
