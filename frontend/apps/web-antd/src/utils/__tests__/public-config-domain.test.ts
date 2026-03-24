import { describe, expect, it } from 'vitest';

import { shouldRequestTenantPublicConfig } from '#/utils/public-config-domain';

describe('shouldRequestTenantPublicConfig', () => {
  it('returns false before domain detection completes', () => {
    expect(shouldRequestTenantPublicConfig(false, null)).toBe(false);
    expect(shouldRequestTenantPublicConfig(false, false)).toBe(false);
    expect(shouldRequestTenantPublicConfig(false, true)).toBe(false);
  });

  it('returns false on detected platform domains', () => {
    expect(shouldRequestTenantPublicConfig(true, false)).toBe(false);
  });

  it('returns true on detected tenant domains', () => {
    expect(shouldRequestTenantPublicConfig(true, true)).toBe(true);
  });
});
