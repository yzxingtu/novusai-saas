// @vitest-environment happy-dom
import { describe, expect, it, vi } from 'vitest';

import { resolvePluginMetadataIcon } from '#/utils/plugin-metadata-icon';

vi.mock('#/router/access', () => ({
  getCurrentEndpoint: () => 'admin',
}));

describe('plugin-metadata-icon', () => {
  it('accepts plugin root icon.png path', () => {
    expect(
      resolvePluginMetadataIcon('weather-widget', 'icon.png', {
        endpoint: 'admin',
      }),
    ).toEqual({
      icon: 'lucide:plug',
      kind: 'image',
      src: '/plugin-icons/weather-widget/icon.png',
    });
  });

  it('accepts preview data png', () => {
    expect(
      resolvePluginMetadataIcon(
        'weather-widget',
        'data:image/png;base64,ZmFrZQ==',
      ),
    ).toEqual({
      icon: 'lucide:plug',
      kind: 'image',
      src: 'data:image/png;base64,ZmFrZQ==',
    });
  });

  it('falls back for non-png or external metadata icons', () => {
    expect(resolvePluginMetadataIcon('novusdoc', 'lucide:file-text')).toEqual({
      kind: 'fallback',
      icon: 'lucide:plug',
    });
    expect(
      resolvePluginMetadataIcon('novusdoc', 'https://cdn.example.com/icon.png'),
    ).toEqual({
      kind: 'fallback',
      icon: 'lucide:plug',
    });
  });
});
