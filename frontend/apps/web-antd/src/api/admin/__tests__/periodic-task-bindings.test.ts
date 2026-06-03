// Test type: behavioral
// 中文: 测试类型 behavioral，覆盖定时任务企业绑定 API 当前 snake_case 转换。
// EN: Test type behavioral, covering current snake_case periodic task binding API transforms.
// 中文: Mock 请求传输层，真实运行 API 适配映射。
// EN: Mock request transport while running the real API adapter mapping.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getPeriodicTaskBindingsApi,
  getPeriodicTaskListApi,
  syncPeriodicTaskBindingsApi,
  updatePeriodicTaskBindingApi,
} from '../periodic-task';

const { requestGetMock, requestPatchMock, requestPutMock } = vi.hoisted(() => ({
  requestGetMock: vi.fn(),
  requestPatchMock: vi.fn(),
  requestPutMock: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
  $te: () => false,
}));

vi.mock('#/utils/request', () => ({
  requestClient: {
    get: requestGetMock,
    patch: requestPatchMock,
    put: requestPutMock,
  },
}));

describe('periodic task binding api', () => {
  beforeEach(() => {
    requestGetMock.mockReset();
    requestPatchMock.mockReset();
    requestPutMock.mockReset();
  });

  it('normalizes periodic task default priority from backend fields', async () => {
    requestGetMock.mockResolvedValue({
      items: [
        {
          id: 8,
          name: 'Nightly cleanup',
          task_path: 'app.tasks.cleanup',
          schedule_type: 'interval',
          cron_expression: null,
          interval_seconds: 600,
          is_active: true,
          last_run_at: null,
          next_run_at: null,
          description: null,
          created_at: '2026-05-01T00:00:00Z',
          scope: 'admin_only',
          owner_tenant_id: null,
          is_locked: false,
          is_editable: true,
          default_priority: 7,
          required_feature_codes: ['ai_runtime'],
          required_plugin_names: ['analytics'],
          max_retries: 0,
          retry_delay: 60,
          timeout: 3600,
          notify_on_failure: false,
          notify_emails: null,
        },
      ],
      page: 1,
      page_size: 20,
      total: 1,
    });

    const result = await getPeriodicTaskListApi();

    expect(result.items[0]).toMatchObject({
      id: 8,
      defaultPriority: 7,
      requiredFeatureCodes: ['ai_runtime'],
      requiredPluginNames: ['analytics'],
    });
  });

  it('normalizes disabled binding overrides from backend fields', async () => {
    requestGetMock.mockResolvedValue([
      {
        id: 12,
        tenant_id: 3,
        tenant_name: 'Acme',
        is_enabled: false,
        disabled_reason: 'maintenance',
        schedule_type_override: 'cron',
        cron_expression_override: '0 3 * * *',
        interval_seconds_override: null,
        kwargs_override: { plan: 'pro' },
        config_override: { retries: 1 },
        effective_schedule_type: 'cron',
        effective_cron_expression: '0 3 * * *',
        effective_interval_seconds: null,
        last_run_at: '2026-05-01T00:00:00Z',
        next_run_at: '2026-05-02T00:00:00Z',
      },
    ]);

    const result = await getPeriodicTaskBindingsApi(7);

    expect(requestGetMock).toHaveBeenCalledWith(
      '/admin/periodic-tasks/7/bindings',
      undefined,
    );
    expect(result).toEqual([
      expect.objectContaining({
        id: 12,
        tenantId: 3,
        tenantName: 'Acme',
        isEnabled: false,
        disabledReason: 'maintenance',
        scheduleTypeOverride: 'cron',
        cronExpressionOverride: '0 3 * * *',
        kwargsOverride: { plan: 'pro' },
        configOverride: { retries: 1 },
        effectiveScheduleType: 'cron',
      }),
    ]);
  });

  it('serializes sync payload with per-tenant overrides', async () => {
    requestPutMock.mockResolvedValue({ added: 0, reenabled: 1, removed: 0 });

    await syncPeriodicTaskBindingsApi(7, {
      scope: 'selected_tenants',
      tenant_ids: [3],
      bindings: [
        {
          tenantId: 3,
          isEnabled: false,
          disabledReason: 'paused',
          scheduleTypeOverride: 'interval',
          intervalSecondsOverride: 900,
          kwargsOverride: { tier: 'enterprise' },
          configOverride: null,
        },
      ],
    });

    expect(requestPutMock).toHaveBeenCalledWith(
      '/admin/periodic-tasks/7/bindings',
      {
        scope: 'selected_tenants',
        tenant_ids: [3],
        bindings: [
          {
            tenant_id: 3,
            is_enabled: false,
            disabled_reason: 'paused',
            schedule_type_override: 'interval',
            interval_seconds_override: 900,
            kwargs_override: { tier: 'enterprise' },
            config_override: null,
          },
        ],
      },
      undefined,
    );
  });

  it('updates one tenant binding through the tenant-specific endpoint', async () => {
    requestPatchMock.mockResolvedValue({
      tenant_id: 5,
      tenant_name: 'Beta',
      is_enabled: true,
    });

    const result = await updatePeriodicTaskBindingApi(7, 5, {
      isEnabled: true,
      scheduleTypeOverride: null,
    });

    expect(requestPatchMock).toHaveBeenCalledWith(
      '/admin/periodic-tasks/7/bindings/5',
      {
        is_enabled: true,
        schedule_type_override: null,
      },
      undefined,
    );
    expect(result).toMatchObject({
      tenantId: 5,
      tenantName: 'Beta',
      isEnabled: true,
    });
  });
});
