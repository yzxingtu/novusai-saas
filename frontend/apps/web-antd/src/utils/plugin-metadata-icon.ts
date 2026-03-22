import type { ApiEndpoint } from '#/api';

import { buildPluginIconUrl } from '#/utils/plugin-asset';

const PLUGIN_METADATA_FALLBACK_ICON = 'lucide:plug';

interface ResolvePluginMetadataIconOptions {
  endpoint?: ApiEndpoint;
}

type ResolvedPluginMetadataIcon =
  {
    icon: string;
    kind: 'fallback' | 'image';
    src?: string;
  };

function isDataPngIcon(value: string): boolean {
  return /^data:image\/png(?:;|,)/i.test(value.trim());
}

function isPluginMetadataPngPath(value: string): boolean {
  const raw = value.trim();
  if (!raw || /^https?:\/\//i.test(raw) || raw.startsWith('blob:')) {
    return false;
  }

  const [pathname] = raw.split(/[?#]/, 1);
  if (!pathname) {
    return false;
  }

  return pathname === 'icon.png' || /(?:^|\/)icon\.png$/i.test(pathname);
}

export function resolvePluginMetadataIcon(
  pluginName: string,
  icon: null | string | undefined,
  options: ResolvePluginMetadataIconOptions = {},
): ResolvedPluginMetadataIcon {
  const raw = (icon || '').trim();

  if (isDataPngIcon(raw)) {
    return {
      icon: PLUGIN_METADATA_FALLBACK_ICON,
      kind: 'image',
      src: raw,
    };
  }

  if (isPluginMetadataPngPath(raw)) {
    return {
      icon: PLUGIN_METADATA_FALLBACK_ICON,
      kind: 'image',
      src: buildPluginIconUrl(pluginName, raw, {
        endpoint: options.endpoint,
      }),
    };
  }

  return {
    kind: 'fallback',
    icon: PLUGIN_METADATA_FALLBACK_ICON,
  };
}
