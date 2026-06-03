// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { adminRoutes } from '../admin';
import { coreRoutes } from '../core';
import { rootRoutes } from '../root';
import { tenantRoutes } from '../tenant';
import { userRoutes } from '../user';

const currentDir = dirname(fileURLToPath(import.meta.url));
const appSrcDir = resolve(currentDir, '../../..');
const legacyCodegenAccessCode = ['action', 'codegen', ''].join('.');

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

function findRouteByName(routes: any[], name: string): any | undefined {
  for (const route of routes) {
    if (route?.name === name) {
      return route;
    }
    if (Array.isArray(route?.children)) {
      const child = findRouteByName(route.children, name);
      if (child) {
        return child;
      }
    }
  }
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

describe('admin codegen permissions', () => {
  it('uses backend permission codes for static codegen routes', () => {
    expect(
      findRouteByName(adminRoutes, 'AdminSystemCodegen')?.meta,
    ).toMatchObject({
      accessCodes: ['codegen:list'],
    });
    expect(
      findRouteByName(adminRoutes, 'AdminSystemCodegenNew')?.meta,
    ).toMatchObject({
      accessCodes: ['codegen:create', 'codegen:options'],
      accessCodesMode: 'all',
    });
    expect(
      findRouteByName(adminRoutes, 'AdminSystemCodegenEdit')?.meta,
    ).toMatchObject({
      accessCodes: ['codegen:detail', 'codegen:options', 'codegen:update'],
      accessCodesMode: 'all',
    });
  });

  it('does not gate codegen UI with action i18n keys', () => {
    const files = [
      'router/routes/admin/index.ts',
      'views/admin/system/codegen/builder.vue',
      'views/admin/system/codegen/data.ts',
      'views/admin/system/codegen/index.vue',
      'views/admin/system/codegen/sections/BuilderWorkflowDialogs.vue',
    ];

    for (const file of files) {
      const source = readFileSync(resolve(appSrcDir, file), 'utf8');
      expect(source, file).not.toContain(legacyCodegenAccessCode);
    }
  });
});
