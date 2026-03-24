import { describe, expect, it } from 'vitest';

import { adminRoutes } from '../admin';
import { coreRoutes } from '../core';
import { rootRoutes } from '../root';
import { tenantRoutes } from '../tenant';
import { userRoutes } from '../user';

function collectMetaTitles(routes: any[]): string[] {
  const titles: string[] = [];

  for (const route of routes) {
    if (typeof route?.meta?.title === 'string') {
      titles.push(route.meta.title);
    }
    if (Array.isArray(route?.children) && route.children.length > 0) {
      titles.push(...collectMetaTitles(route.children));
    }
  }

  return titles;
}

describe('route meta titles', () => {
  it('stores locale keys instead of translated snapshots for localized routes', () => {
    const titles = [
      ...collectMetaTitles(coreRoutes),
      ...collectMetaTitles(rootRoutes),
      ...collectMetaTitles(adminRoutes),
      ...collectMetaTitles(tenantRoutes),
      ...collectMetaTitles(userRoutes),
    ];

    expect(titles).toEqual(
      expect.arrayContaining([
        'page.auth.login',
        'page.dashboard.title',
        'admin.analytics.title',
        'tenant.analytics.title',
        'public.platformHome.title',
        'user.home.title',
      ]),
    );
    expect(titles).not.toContain('登录');
    expect(titles).not.toContain('Dashboard');
  });
});
