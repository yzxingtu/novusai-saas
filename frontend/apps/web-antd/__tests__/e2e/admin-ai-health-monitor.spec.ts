// Test type: behavioral
// 中文: Mock 管理端健康 API 传输层，真实运行页面渲染与浏览器断言。
// EN: Mock admin health API transport while exercising real page rendering and browser assertions.
import { expect, test } from '@playwright/test';

import { hasAdminCredentials, loginAsAdmin } from './common/admin-auth';

const adminTestsEnabled = hasAdminCredentials();

const providerStatuses = [
  {
    provider_id: 101,
    provider_code: 'gpt-5.4',
    provider_name: '1倍率 GPT-5.4',
    provider_icon: null,
    primary_wire_api: 'responses',
    is_healthy: true,
    is_available: true,
    base_connectivity_healthy: true,
    tool_calling_healthy: true,
    response_time_ms: 1770,
    consecutive_failures: 0,
    error_message: null,
    checked_at: '2026-05-08T15:16:35Z',
  },
  {
    provider_id: 202,
    provider_code: 'gpt-5.4-mini',
    provider_name: '快速 GPT-5.4 Mini',
    provider_icon: null,
    primary_wire_api: 'responses',
    is_healthy: false,
    is_available: true,
    base_connectivity_healthy: true,
    tool_calling_healthy: false,
    response_time_ms: 2460,
    consecutive_failures: 1,
    error_message: 'Tool probe degraded',
    checked_at: '2026-05-08T15:15:35Z',
  },
  {
    provider_id: 303,
    provider_code: 'no-history-provider',
    provider_name: 'No history provider',
    provider_icon: null,
    primary_wire_api: 'responses',
    is_healthy: false,
    is_available: false,
    base_connectivity_healthy: false,
    tool_calling_healthy: false,
    response_time_ms: 0,
    consecutive_failures: 2,
    error_message: 'history lookup failed',
    checked_at: '2026-05-08T15:14:35Z',
  },
];

function buildHealthHistory() {
  return Array.from({ length: 60 }, (_, index) => {
    const checkedAt = new Date(
      Date.UTC(2026, 4, 8, 14, 16 - index, 35),
    ).toISOString();
    if (index >= 55) {
      return {
        primary_wire_api: 'responses',
        is_healthy: false,
        is_available: false,
        base_connectivity_healthy: false,
        tool_calling_healthy: false,
        response_time_ms: 0,
        error_message: 'provider unavailable',
        checked_at: checkedAt,
      };
    }
    if (index >= 45) {
      return {
        primary_wire_api: 'responses',
        is_healthy: false,
        is_available: true,
        base_connectivity_healthy: true,
        tool_calling_healthy: false,
        response_time_ms: 3200 + index,
        error_message: 'tool probe degraded',
        checked_at: checkedAt,
      };
    }
    return {
      primary_wire_api: 'responses',
      is_healthy: true,
      is_available: true,
      base_connectivity_healthy: true,
      tool_calling_healthy: true,
      response_time_ms: 1700 + index,
      error_message: null,
      checked_at: checkedAt,
    };
  });
}

function buildUnavailableHealthHistory(length: number) {
  return Array.from({ length }, (_, index) => ({
    primary_wire_api: 'responses',
    is_healthy: false,
    is_available: false,
    base_connectivity_healthy: false,
    tool_calling_healthy: false,
    response_time_ms: 0,
    error_message: 'provider unavailable',
    checked_at: new Date(
      Date.UTC(2026, 4, 8, 14, 16 - index, 35),
    ).toISOString(),
  }));
}

test.describe('Admin AI Health Monitor smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!adminTestsEnabled, 'Admin credentials are not configured');
    await loginAsAdmin(page);
  });

  test('renders provider health cards with one-hour history bars', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const historyRequestLimits: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.route('**/admin/ai/health', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        json: { code: 0, data: providerStatuses, message: 'ok' },
      });
    });
    await page.route('**/admin/ai/health/*/history*', async (route) => {
      const requestUrl = new URL(route.request().url());
      historyRequestLimits.push(requestUrl.searchParams.get('limit') ?? '');
      const providerId = /\/admin\/ai\/health\/(\d+)\/history/.exec(
        requestUrl.pathname,
      )?.[1];
      if (providerId === '303') {
        await route.fulfill({
          contentType: 'application/json',
          json: { code: 500, data: null, message: 'history lookup failed' },
        });
        return;
      }
      await route.fulfill({
        contentType: 'application/json',
        json: {
          code: 0,
          data:
            providerId === '202'
              ? buildUnavailableHealthHistory(35)
              : buildHealthHistory(),
          message: 'ok',
        },
      });
    });

    await page.goto('/admin/ai/monitor/health');
    await page.waitForLoadState('networkidle');

    const cards = page.locator('[data-testid="health-provider-card"]');
    await expect(cards).toHaveCount(3);

    const firstCard = cards.first();
    await expect(firstCard.getByText('1倍率 GPT-5.4')).toBeVisible();
    await expect(firstCard.getByText(/服务层|Service/)).toBeVisible();
    await expect(firstCard.getByText('TTFB')).toBeVisible();
    await expect(firstCard.getByText('1770 ms')).toBeVisible();
    await expect(firstCard.getByText('LATEST')).toBeVisible();
    await expect(firstCard.getByText('Availability (1h)')).toBeVisible();
    await expect(firstCard.getByText('75.00%')).toBeVisible();
    await expect(firstCard.getByText(/45\/60\s*(成功|success)/)).toBeVisible();
    await expect(firstCard.getByText('HISTORY (60 PTS)')).toBeVisible();
    await expect(
      firstCard.locator('[data-testid="health-history-chart"]'),
    ).toBeVisible();
    await expect(
      firstCard.locator('[data-testid="health-history-point"]'),
    ).toHaveCount(60);
    expect([...historyRequestLimits].toSorted()).toEqual(['60', '60', '60']);

    const historyPointSizes = await firstCard
      .locator('[data-testid="health-history-point"]')
      .evaluateAll((points) =>
        points.map((point) => {
          const rect = point.getBoundingClientRect();
          return {
            className: point.getAttribute('class') ?? '',
            height: rect.height,
            width: rect.width,
          };
        }),
      );
    const historyPointWidths = historyPointSizes.map((item) => item.width);
    const historyPointHeights = historyPointSizes.map((item) => item.height);
    expect(Math.min(...historyPointWidths)).toBeGreaterThan(1);
    expect(Math.max(...historyPointWidths)).toBeLessThan(10);
    expect(
      Math.max(...historyPointWidths) - Math.min(...historyPointWidths),
    ).toBeLessThanOrEqual(1);
    expect(new Set(historyPointHeights)).toEqual(new Set([32]));
    expect(
      historyPointSizes.every(
        (item) =>
          item.className.includes('h-8') &&
          item.className.includes('rounded-[2px]'),
      ),
    ).toBe(true);

    const historyColorState = await firstCard
      .locator('[data-testid="health-history-point"]')
      .evaluateAll((points) => {
        const state = { amber: false, emerald: false, rose: false };
        for (const point of points) {
          const className = point.getAttribute('class') ?? '';
          state.amber ||= className.includes('bg-amber-400');
          state.emerald ||= className.includes('bg-emerald-500');
          state.rose ||= className.includes('bg-rose-600');
        }
        return state;
      });
    expect(historyColorState).toEqual({
      amber: true,
      emerald: true,
      rose: true,
    });

    const secondCard = cards.nth(1);
    await expect(
      secondCard.locator('[data-testid="health-availability"]'),
    ).toHaveText('0.00%');
    await expect(secondCard.getByText(/0\/35\s*(成功|success)/)).toBeVisible();
    await expect(
      secondCard.locator('[data-testid="health-history-point"]'),
    ).toHaveCount(60);
    const secondCardHistoryState = await secondCard
      .locator('[data-testid="health-history-point"]')
      .evaluateAll((points) => {
        const state = { missing: 0, unavailable: 0 };
        for (const point of points) {
          const className = point.getAttribute('class') ?? '';
          if (className.includes('bg-muted-foreground/20')) state.missing += 1;
          if (className.includes('bg-rose-600')) state.unavailable += 1;
        }
        return state;
      });
    expect(secondCardHistoryState).toEqual({
      missing: 25,
      unavailable: 35,
    });

    const thirdCard = cards.nth(2);
    await expect(
      thirdCard.locator('[data-testid="health-availability"]'),
    ).toHaveText('--');
    await expect(
      thirdCard.locator('[data-testid="health-success-summary"]'),
    ).toHaveText(/History unavailable|历史数据不可用/);
    await expect(
      thirdCard.locator('[data-testid="health-history-error"]'),
    ).toContainText(/history lookup failed|History unavailable|历史数据不可用/);
    await expect(
      thirdCard.locator('[data-testid="health-history-point"]'),
    ).toHaveCount(0);
    expect(consoleErrors).toEqual([]);
  });
});
