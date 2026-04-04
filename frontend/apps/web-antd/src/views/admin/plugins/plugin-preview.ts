import type {
  InstallManifestCountKey,
  InstallManifestDetailKey,
  InstallManifestSummary,
} from '#/api/admin/plugin';

import { $t } from '#/locales';

export interface PreviewStructureSummaryItem {
  count: number;
  details: string[];
  icon: string;
  label: string;
  type: InstallManifestCountKey;
}

const PREVIEW_STRUCTURE_CONFIG: Array<{
  icon: string;
  type: InstallManifestCountKey;
}> = [
  { type: 'skills', icon: 'lucide:sparkles' },
  { type: 'api_routes', icon: 'lucide:route' },
  { type: 'hooks', icon: 'lucide:anchor' },
  { type: 'events', icon: 'lucide:radio' },
  { type: 'webhooks', icon: 'lucide:webhook' },
  { type: 'tasks', icon: 'lucide:clock' },
  { type: 'adapters', icon: 'lucide:cpu' },
  { type: 'storage_drivers', icon: 'lucide:database' },
  { type: 'notifications', icon: 'lucide:bell' },
  { type: 'permissions', icon: 'lucide:shield' },
  { type: 'frontend_pages', icon: 'lucide:file-stack' },
  { type: 'page_menus', icon: 'lucide:menu' },
  { type: 'header_widgets', icon: 'lucide:panel-top' },
  { type: 'dashboard_widgets', icon: 'lucide:layout-dashboard' },
  { type: 'settings_tabs', icon: 'lucide:settings-2' },
  { type: 'floating_panels', icon: 'lucide:panel-right-open' },
  { type: 'notification_ui', icon: 'lucide:bell-ring' },
];

const PREVIEW_TYPE_SIGNALS: Array<{
  pluginType: string;
  type: InstallManifestCountKey;
}> = [
  { type: 'skills', pluginType: 'skill' },
  { type: 'hooks', pluginType: 'hook' },
  { type: 'api_routes', pluginType: 'api' },
  { type: 'webhooks', pluginType: 'webhook' },
  { type: 'events', pluginType: 'event' },
];

function getInstallManifestCount(
  installManifest: InstallManifestSummary | null | undefined,
  key: InstallManifestCountKey,
): number {
  const raw = installManifest?.[key];
  return typeof raw === 'number' && raw > 0 ? raw : 0;
}

function getInstallManifestDetails(
  installManifest: InstallManifestSummary | null | undefined,
  key: InstallManifestCountKey,
): string[] {
  const detailsKey = `${key}_details` as InstallManifestDetailKey;
  const raw = installManifest?.[detailsKey];
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.filter(
    (detail): detail is string => typeof detail === 'string' && detail.length > 0,
  );
}

export function deriveInstallPreviewPluginType(
  installManifest: InstallManifestSummary | null | undefined,
): string {
  const matchedTypes = PREVIEW_TYPE_SIGNALS.filter(
    ({ type }) => getInstallManifestCount(installManifest, type) > 0,
  );
  if (matchedTypes.length === 0) {
    return 'basic';
  }
  if (matchedTypes.length > 1) {
    return 'composite';
  }
  return matchedTypes[0]?.pluginType || 'basic';
}

export function summarizeInstallManifest(
  installManifest: InstallManifestSummary | null | undefined,
  translate: (key: string) => string = $t,
): PreviewStructureSummaryItem[] {
  return PREVIEW_STRUCTURE_CONFIG.flatMap(({ icon, type }) => {
    const count = getInstallManifestCount(installManifest, type);
    if (count <= 0) {
      return [];
    }
    return [
      {
        type,
        count,
        icon,
        label: translate(`admin.plugin.structureType.${type}`),
        details: getInstallManifestDetails(installManifest, type),
      },
    ];
  });
}
