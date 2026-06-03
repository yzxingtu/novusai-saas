// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: TokenStorage fails closed before namespace initialization and uses namespaced endpoint keys after init.
// Mock strategy: No mocks; localStorage behavior is exercised directly.
import { describe, expect, it, vi } from 'vitest';

describe('token storage namespace behavior', () => {
  it('does not read or write bare token keys before namespace initialization', async () => {
    vi.resetModules();
    const { TokenStorage } = await import('../token-storage');
    localStorage.clear();
    localStorage.setItem('admin_token', 'bare-admin-token');
    localStorage.setItem('admin_refresh_token', 'bare-admin-refresh-token');
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    expect(TokenStorage.getToken('admin')).toBeNull();
    expect(TokenStorage.getRefreshToken('admin')).toBeNull();

    TokenStorage.setToken('admin', 'new-admin-token');
    TokenStorage.setRefreshToken('admin', 'new-admin-refresh-token');
    expect(localStorage.getItem('admin_token')).toBe('bare-admin-token');
    expect(localStorage.getItem('admin_refresh_token')).toBe(
      'bare-admin-refresh-token',
    );

    TokenStorage.clearToken('admin');
    expect(localStorage.getItem('admin_token')).toBe('bare-admin-token');
    expect(localStorage.getItem('admin_refresh_token')).toBe(
      'bare-admin-refresh-token',
    );
    warnSpy.mockRestore();
  });

  it('stores and clears only namespaced endpoint tokens after initialization', async () => {
    vi.resetModules();
    const { TokenStorage } = await import('../token-storage');
    localStorage.clear();
    TokenStorage.init('vitest_ns');

    TokenStorage.setToken('tenant', 'tenant-token');
    TokenStorage.setRefreshToken('tenant', 'tenant-refresh-token');

    expect(localStorage.getItem('tenant_admin_token')).toBeNull();
    expect(TokenStorage.getToken('tenant')).toBe('tenant-token');
    expect(TokenStorage.getRefreshToken('tenant')).toBe('tenant-refresh-token');

    TokenStorage.clearToken('tenant');
    expect(TokenStorage.getToken('tenant')).toBeNull();
    expect(TokenStorage.getRefreshToken('tenant')).toBeNull();
  });
});
