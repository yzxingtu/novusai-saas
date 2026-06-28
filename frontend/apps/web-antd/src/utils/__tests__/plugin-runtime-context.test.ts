// @vitest-environment happy-dom
import { beforeEach, describe, expect, it } from 'vitest';

import {
  buildPluginApiBase,
  getActivePluginHostEndpoint,
  getPluginHostEndpoint,
  setActivePluginHostEndpoint,
} from '../plugin-runtime-context';

describe('plugin-runtime-context', () => {
  beforeEach(() => {
    setActivePluginHostEndpoint(null);
    window.history.replaceState({}, '', '/admin/dashboard');
  });

  it('builds plugin API base from the active admin host endpoint', () => {
    setActivePluginHostEndpoint('admin');

    expect(getActivePluginHostEndpoint()).toBe('admin');
    expect(buildPluginApiBase('weather-widget')).toBe(
      '/admin/plugins/weather-widget/api',
    );
  });

  it('builds plugin API base from the active tenant host endpoint', () => {
    setActivePluginHostEndpoint('tenant');

    expect(getActivePluginHostEndpoint()).toBe('tenant');
    expect(buildPluginApiBase('weather-widget')).toBe(
      '/tenant/plugins/weather-widget/api',
    );
  });

  it('falls back only for explicit admin or tenant route paths', () => {
    expect(getPluginHostEndpoint('/admin/system/logs')).toBe('admin');
    expect(getPluginHostEndpoint('/tenant/dashboard')).toBe('tenant');
    expect(getPluginHostEndpoint('/plugin-assets/weather-widget/index.js')).toBe(
      null,
    );
  });

  it('does not default unknown plugin host paths to tenant APIs', () => {
    window.history.replaceState(
      {},
      '',
      '/plugin-assets/weather-widget/index.js',
    );

    expect(() => buildPluginApiBase('weather-widget')).toThrow(
      /Cannot resolve host endpoint/,
    );
  });

  it('keeps the active endpoint while resolving public plugin asset paths', () => {
    setActivePluginHostEndpoint('admin');

    expect(getPluginHostEndpoint('/plugin-assets/captcha/index.js')).toBe(
      'admin',
    );
    expect(buildPluginApiBase('weather-widget')).toBe(
      '/admin/plugins/weather-widget/api',
    );
  });
});
