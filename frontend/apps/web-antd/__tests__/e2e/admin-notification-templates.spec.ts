import { expect, test, type Response } from '@playwright/test';

import { hasAdminCredentials, loginAsAdmin } from './common/admin-auth';

// 中文: 测试类型 smoke，覆盖登录态通知模板治理页面的真实路由/API/表格呈现。
// EN: Test type smoke, covering the authenticated notification-template governance page route/API/table rendering.
const adminTestsEnabled = hasAdminCredentials();

function hasGovernanceKey(
  item: Record<string, unknown>,
  snakeKey: string,
  camelKey: string,
) {
  return snakeKey in item || camelKey in item;
}

function isTemplateListResponse(response: Response) {
  let pathname = '';
  try {
    pathname = new URL(response.url()).pathname;
  } catch {
    return false;
  }
  return (
    pathname.endsWith('/admin/notification-templates') &&
    response.request().method() === 'GET' &&
    response.status() === 200 &&
    (response.headers()['content-type'] || '').includes('application/json')
  );
}

test.describe('Admin Notification Templates smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!adminTestsEnabled, 'Admin credentials are not configured');
    await loginAsAdmin(page);
  });

  test('renders governance columns and effective preview controls', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    const listResponsePromise = page.waitForResponse(isTemplateListResponse);

    await page.goto('/admin/system/notification-templates');
    await page.waitForLoadState('networkidle');

    const listResponse = await listResponsePromise;
    const listBody = (await listResponse.json()) as {
      code?: number;
      data?: { items?: Array<Record<string, unknown>> };
      items?: Array<Record<string, unknown>>;
    };
    const listData = listBody.data ?? listBody;
    const items = listData.items ?? [];

    const table = page.locator('.vxe-table').first();
    const headers = table.locator('.vxe-header--column');
    await expect(table).toBeVisible();
    await expect(
      headers.filter({ hasText: /模板代码|Template Code/ }).first(),
    ).toBeAttached();
    await expect(
      headers.filter({ hasText: /作用域|Scope/ }).first(),
    ).toBeAttached();
    await expect(
      headers.filter({ hasText: /企业|Tenant/ }).first(),
    ).toBeAttached();
    await expect(
      headers.filter({ hasText: /插件|Plugin/ }).first(),
    ).toBeAttached();
    await expect(
      headers.filter({ hasText: /来源|Source/ }).first(),
    ).toBeAttached();
    await expect(
      headers.filter({ hasText: /覆盖模板|Override/ }).first(),
    ).toBeAttached();

    expect(items.length).toBeGreaterThan(0);
    const [first] = items;
    expect(first).toBeDefined();
    if (!first) {
      return;
    }
    expect(hasGovernanceKey(first, 'tenant_id', 'tenantId')).toBe(true);
    expect(hasGovernanceKey(first, 'tenant_name', 'tenantName')).toBe(true);
    expect(hasGovernanceKey(first, 'plugin_name', 'pluginName')).toBe(true);
    expect(hasGovernanceKey(first, 'source', 'source')).toBe(true);
    expect(hasGovernanceKey(first, 'is_override', 'isOverride')).toBe(true);
    expect(hasGovernanceKey(first, 'effective_preview', 'effectivePreview')).toBe(
      true,
    );

    expect(consoleErrors).toEqual([]);
  });
});
