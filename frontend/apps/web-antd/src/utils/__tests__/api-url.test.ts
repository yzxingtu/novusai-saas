import { describe, expect, it, vi } from 'vitest';

import { resolveApiUrl } from '#/utils/api-url';

vi.mock('@vben/hooks', () => ({
  useAppConfig: vi.fn(() => ({
    apiURL: '',
  })),
}));

describe('resolveApiUrl', () => {
  it('returns an empty string when api url config is missing', () => {
    expect(resolveApiUrl(undefined)).toBe('');
  });

  it('keeps explicit non-loopback api hosts in development', () => {
    expect(
      resolveApiUrl('http://192.168.31.129:8000/', {
        currentHostname: 'localhost',
      }),
    ).toBe('http://192.168.31.129:8000');
  });

  it('rewrites loopback api hosts to the current page hostname in development', () => {
    expect(
      resolveApiUrl('http://127.0.0.1:8000', {
        currentHostname: 'tenant.demo.local',
      }),
    ).toBe('http://tenant.demo.local:8000');
  });

  it('preserves loopback api hosts when the current page also uses loopback', () => {
    expect(
      resolveApiUrl('http://localhost:8000/', {
        currentHostname: 'localhost',
      }),
    ).toBe('http://localhost:8000');
  });

  it('does not rewrite api hosts in production mode', () => {
    expect(
      resolveApiUrl('http://127.0.0.1:8000/', {
        currentHostname: 'tenant.demo.local',
        isProduction: true,
      }),
    ).toBe('http://127.0.0.1:8000');
  });
});
