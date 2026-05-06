// 中文: 测试类型 behavioral，覆盖定时任务绑定覆盖草稿与载荷合同。
// EN: Test type behavioral, covering periodic task binding override draft and payload contracts.
// 中文: 纯 helper 测试，不 mock 组件或 API。
// EN: Pure helper tests without component or API mocks.
import { describe, expect, it } from 'vitest';

import {
  reconcileBindingOverrideDrafts,
  toBindingOverridePayload,
} from '../binding-overrides';

describe('periodic task binding override helpers', () => {
  it('keeps disabled tenant bindings selected and preserves edited draft values', () => {
    const drafts = reconcileBindingOverrideDrafts(
      [
        {
          tenantId: 3,
          tenantName: 'Old',
          isEnabled: false,
          disabledReason: 'edited reason',
          scheduleTypeOverride: null,
          cronExpressionOverride: '',
          intervalSecondsOverride: null,
          kwargsOverrideText: '{"local":true}',
          configOverrideText: '',
          effectiveScheduleType: null,
          effectiveCronExpression: null,
          effectiveIntervalSeconds: null,
        },
      ],
      [3, 4],
      [
        { label: 'Acme', value: 3 },
        { label: 'Beta', value: 4 },
      ],
      [
        {
          id: 44,
          tenantId: 4,
          tenantName: 'Beta',
          isEnabled: false,
          disabledReason: 'from backend',
          scheduleTypeOverride: 'interval',
          cronExpressionOverride: null,
          intervalSecondsOverride: 600,
          kwargsOverride: null,
          configOverride: { mode: 'safe' },
          effectiveScheduleType: 'interval',
          effectiveCronExpression: null,
          effectiveIntervalSeconds: 600,
          lastRunAt: null,
          nextRunAt: null,
        },
      ],
    );

    expect(drafts).toEqual([
      expect.objectContaining({
        tenantId: 3,
        tenantName: 'Acme',
        isEnabled: false,
        disabledReason: 'edited reason',
        kwargsOverrideText: '{"local":true}',
      }),
      expect.objectContaining({
        tenantId: 4,
        tenantName: 'Beta',
        isEnabled: false,
        disabledReason: 'from backend',
        scheduleTypeOverride: 'interval',
        intervalSecondsOverride: 600,
        configOverrideText: '{\n  "mode": "safe"\n}',
      }),
    ]);
  });

  it('serializes schedule and JSON overrides into API payload shape', () => {
    const result = toBindingOverridePayload({
      tenantId: 3,
      tenantName: 'Acme',
      isEnabled: false,
      disabledReason: 'paused',
      scheduleTypeOverride: 'cron',
      cronExpressionOverride: '0 2 * * *',
      intervalSecondsOverride: 600,
      kwargsOverrideText: '{"tier":"pro"}',
      configOverrideText: '{"retries":2}',
      effectiveScheduleType: null,
      effectiveCronExpression: null,
      effectiveIntervalSeconds: null,
    });

    expect(result.errors).toEqual([]);
    expect(result.payload).toEqual({
      tenantId: 3,
      isEnabled: false,
      disabledReason: 'paused',
      scheduleTypeOverride: 'cron',
      cronExpressionOverride: '0 2 * * *',
      intervalSecondsOverride: null,
      kwargsOverride: { tier: 'pro' },
      configOverride: { retries: 2 },
    });
  });

  it('reports non-object JSON override text as contract errors', () => {
    const result = toBindingOverridePayload({
      tenantId: 3,
      tenantName: 'Acme',
      isEnabled: true,
      disabledReason: '',
      scheduleTypeOverride: null,
      cronExpressionOverride: '',
      intervalSecondsOverride: null,
      kwargsOverrideText: '[]',
      configOverrideText: '{"ok":true}',
      effectiveScheduleType: null,
      effectiveCronExpression: null,
      effectiveIntervalSeconds: null,
    });

    expect(result.errors).toEqual(['kwargs']);
    expect(result.payload).toMatchObject({
      tenantId: 3,
      isEnabled: true,
      disabledReason: null,
      configOverride: { ok: true },
    });
  });
});
