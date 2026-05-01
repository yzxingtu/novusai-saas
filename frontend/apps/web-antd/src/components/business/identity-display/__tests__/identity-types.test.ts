// Test type: structural
// Verifies: identity select option helpers preserve account AI availability.
import { describe, expect, it, vi } from 'vitest';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

import {
  identityModelFromOption,
  normalizeIdentitySelectOption,
} from '../types';

describe('identity select option AI availability mapping', () => {
  it('preserves snake_case ai_enabled=false from remote select extras', () => {
    const option = {
      label: 'Ops Admin',
      value: 42,
      extra: {
        ai_enabled: false,
        username: 'ops_admin',
      },
    };

    expect(identityModelFromOption(option).aiEnabled).toBe(false);
    expect(normalizeIdentitySelectOption(option).extra?.aiEnabled).toBe(false);
  });
});
