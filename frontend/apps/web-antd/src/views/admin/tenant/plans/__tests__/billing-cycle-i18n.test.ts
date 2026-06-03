import type { adminApi } from '#/api';

import { describe, expect, it } from 'vitest';

import enTenant from '#/locales/langs/en-US/admin/tenant.json';
import zhTenant from '#/locales/langs/zh-CN/admin/tenant.json';

const billingCycles = [
  'monthly',
  'quarterly',
  'yearly',
  'lifetime',
  'one_time',
  'custom',
] as const satisfies readonly adminApi.BillingCycle[];

describe('tenant plan billing cycle i18n', () => {
  it('covers every billing cycle shown by admin plan pages', () => {
    for (const cycle of billingCycles) {
      expect(zhTenant.plan.billingCycleOptions[cycle]).toBeTruthy();
      expect(enTenant.plan.billingCycleOptions[cycle]).toBeTruthy();
    }
  });
});
