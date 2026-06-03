// @vitest-environment happy-dom
import { beforeEach, describe, expect, it } from 'vitest';

import {
  clearPersistedTabbarStorage,
  sanitizePersistedTabbarStorage,
} from '../tabbar-storage';

describe('tabbar-storage', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it('sanitizes only the current namespaced tabbar key', () => {
    sessionStorage.setItem('core-tabbar', 'bare-tabbar');
    sessionStorage.setItem(
      'other-core-tabbar',
      JSON.stringify([{ path: '/other' }]),
    );
    sessionStorage.setItem(
      'vitest-core-tabbar',
      JSON.stringify([
        { fullPath: '/users?page=1', path: '/users' },
        { fullPath: '/users?page=2', path: '/users' },
        { fullPath: '/settings', path: '/settings' },
      ]),
    );

    sanitizePersistedTabbarStorage('vitest');

    expect(
      JSON.parse(sessionStorage.getItem('vitest-core-tabbar') ?? ''),
    ).toEqual([
      { fullPath: '/users?page=2', path: '/users' },
      { fullPath: '/settings', path: '/settings' },
    ]);
    expect(sessionStorage.getItem('core-tabbar')).toBe('bare-tabbar');
    expect(
      JSON.parse(sessionStorage.getItem('other-core-tabbar') ?? ''),
    ).toEqual([{ path: '/other' }]);
  });

  it('clears namespaced tabbar keys without touching bare core keys', () => {
    sessionStorage.setItem('core-tabbar', 'bare-tabbar');
    sessionStorage.setItem('vitest-core-tabbar', JSON.stringify([]));

    clearPersistedTabbarStorage();

    expect(sessionStorage.getItem('vitest-core-tabbar')).toBeNull();
    expect(sessionStorage.getItem('core-tabbar')).toBe('bare-tabbar');
  });
});
