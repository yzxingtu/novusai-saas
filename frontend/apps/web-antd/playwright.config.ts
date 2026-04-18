import type { PlaywrightTestConfig } from '@playwright/test';

import { devices } from '@playwright/test';

function normalizeHost(value?: string) {
  if (!value) return '';
  return value
    .trim()
    .replace(/^https?:\/\//, '')
    .replace(/\/.*$/, '')
    .replace(/:\d+$/, '')
    .toLowerCase();
}

function resolveTenantHost() {
  const tenantCode = (process.env.TENANT_ADMIN_TENANT_CODE || '').trim();
  if (tenantCode) {
    const suffix =
      (
        process.env.TENANT_ADMIN_DOMAIN_SUFFIX ||
        process.env.TENANT_DOMAIN_SUFFIX ||
        '.app.local'
      ).trim() || '.app.local';
    const normalizedSuffix = suffix.startsWith('.') ? suffix : `.${suffix}`;
    return `${tenantCode}${normalizedSuffix}`.toLowerCase();
  }

  return normalizeHost(
    process.env.TENANT_E2E_DOMAIN ||
      process.env.TENANT_ADMIN_DOMAIN ||
      process.env.TENANT_ADMIN_BASE_URL,
  );
}

const useTenantDomain = process.env.TENANT_E2E_USE_DOMAIN === 'true';
const tenantHost = useTenantDomain ? resolveTenantHost() : '';
const useDedicatedTenantServer = Boolean(tenantHost);
const defaultPort = useDedicatedTenantServer ? '5667' : '5666';
const configuredPort = Number.parseInt(
  process.env.TENANT_E2E_PORT ?? defaultPort,
  10,
);
const tenantPort =
  Number.isFinite(configuredPort) && configuredPort > 0 ? configuredPort : 5666;
const E2E_BASE_URL =
  process.env.E2E_BASE_URL ||
  (tenantHost
    ? `http://${tenantHost}:${tenantPort}`
    : `http://localhost:${tenantPort}`);
const extraLaunchArgs =
  process.env.PLAYWRIGHT_LAUNCH_ARGS?.split(/\s+/).filter(Boolean) ?? [];
const baseLaunchArgs = ['--no-proxy-server'];
const launchArgs = tenantHost
  ? [
      ...baseLaunchArgs,
      `--host-resolver-rules=MAP ${tenantHost} 127.0.0.1`,
      ...extraLaunchArgs,
    ]
  : [...baseLaunchArgs, ...extraLaunchArgs];

const workerCount = Number.parseInt(process.env.E2E_WORKERS ?? '1', 10);
const resolvedWorkerCount =
  Number.isFinite(workerCount) && workerCount > 0 ? workerCount : 1;

const config: PlaywrightTestConfig = {
  expect: {
    timeout: 5000,
  },
  forbidOnly: !!process.env.CI,
  outputDir: 'node_modules/.e2e/test-results',
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: launchArgs.length > 0 ? { args: launchArgs } : undefined,
      },
    },
  ],
  reporter: [
    ['list'],
    ['html', { outputFolder: 'node_modules/.e2e/test-results' }],
  ],
  retries: process.env.CI ? 2 : 0,
  testDir: './__tests__/e2e',
  timeout: 30 * 1000,
  use: {
    actionTimeout: 0,
    baseURL: E2E_BASE_URL,
    headless: !!process.env.CI,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `pnpm vite --mode development --host 0.0.0.0 --port ${tenantPort}`,
    port: tenantPort,
    reuseExistingServer: useDedicatedTenantServer ? false : !process.env.CI,
  },
  workers: process.env.CI ? 1 : resolvedWorkerCount,
};

export default config;
