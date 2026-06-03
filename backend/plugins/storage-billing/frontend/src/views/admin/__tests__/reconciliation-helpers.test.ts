import type {
  ReconciliationRequestedScope,
  ReconciliationRun,
  ReconciliationSourceRecord,
} from '../../../types';

import { describe, expect, it } from 'vitest';

import {
  formatBytes,
  formatTimestamp,
  hasAuditSamples,
  normalizeNumber,
  scopeProviderCodes,
  scopeProviderPlans,
  selectedRunScopePayload,
  selectedRunScopeSummary,
  sourceAllocationAudit,
  sourceAllocationSummary,
} from '../reconciliation-helpers';

function createSource(
  overrides: Partial<ReconciliationSourceRecord> = {},
): ReconciliationSourceRecord {
  return {
    amount_total: '12.50',
    billing_date: '2026-04-10',
    currency: 'CNY',
    driver_code: 'qiniu-kodo',
    error_message: null,
    fetched_at: '2026-04-11T00:00:00Z',
    id: 1,
    provider_code: 'qiniu-kodo',
    raw_payload_json: {},
    run_id: 9,
    source_key: 'statement-1',
    source_ref: 'stmt-1',
    source_status: 'fetched',
    usage_bytes: 2048,
    ...overrides,
  };
}

function createRun(
  requestedScope: ReconciliationRequestedScope,
): ReconciliationRun {
  return {
    billing_date: '2026-04-10',
    completed_at: '2026-04-11T00:10:00Z',
    error_message: null,
    id: 9,
    provider_codes: ['qiniu-kodo', 'tencent-cos'],
    requested_scope: requestedScope,
    run_key: 'run-9',
    started_at: '2026-04-11T00:00:00Z',
    status: 'completed',
    summary: {},
    trigger_type: 'manual',
  };
}

describe('storage-billing reconciliation helpers', () => {
  it('formats timestamps, byte sizes, and numeric inputs consistently', () => {
    expect(formatTimestamp('2026-04-11T03:00:00Z')).toBe('2026-04-11 03:00:00');
    expect(formatTimestamp(null)).toBe('-');
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1024)).toBe('1.00 KB');
    expect(formatBytes(1536)).toBe('1.50 KB');
    expect(normalizeNumber(12)).toBe(12);
    expect(normalizeNumber(' 18 ')).toBe(18);
    expect(normalizeNumber('abc')).toBeNull();
  });

  it('tolerates partial allocation payloads and detects audit samples', () => {
    const source = createSource({
      raw_payload_json: {
        allocation_audit: {
          ambiguous_item_samples: [{ key: 'ambiguous-1' }],
          unmatched_item_samples: ['source-a'],
        },
        allocation_summary: {
          matched_items: '6',
          unmatched_items: 2,
          written_charge_rows: '3',
        },
      },
    });

    expect(sourceAllocationSummary(source)).toEqual({
      ambiguous_items: 0,
      matched_items: 6,
      unmatched_items: 2,
      written_charge_rows: 3,
    });
    expect(sourceAllocationAudit(source)).toEqual({
      ambiguous_item_samples: [{ key: 'ambiguous-1' }],
      unmatched_item_samples: ['source-a'],
    });
    expect(hasAuditSamples(source)).toBe(true);
    expect(hasAuditSamples(createSource())).toBe(false);
  });

  it('normalizes scope provider plans and builds readable run summaries', () => {
    const requestedScope: ReconciliationRequestedScope = {
      billing_date: '2026-04-10',
      billing_month: '2026-04',
      job: 'manual-trigger',
      official_billing_lag_days: 2,
      official_target_rule: 'T+2',
      provider_codes: ['qiniu-kodo', 'tencent-cos', null as never, '  ' as never],
      provider_plans: [
        {
          billing_date: '2026-04-10',
          official_billing_lag_days: '2' as never,
          official_target_rule: 'T+2',
          provider_code: 'qiniu-kodo',
        },
        {
          billing_date: '2026-04-11',
          provider_code: 'tencent-cos',
        },
        {
          billing_date: '',
          provider_code: 'aliyun-oss',
        } as never,
      ],
      scheduled_provider_code: 'qiniu-kodo',
    };
    const run = createRun(requestedScope);
    const labelFromAny = (code: string) => `provider:${code}`;

    expect(scopeProviderCodes(requestedScope)).toEqual([
      'qiniu-kodo',
      'tencent-cos',
    ]);
    expect(scopeProviderPlans(requestedScope)).toEqual([
      {
        billing_date: '2026-04-10',
        cron: undefined,
        local_time: undefined,
        official_billing_lag_days: 2,
        official_target_rule: 'T+2',
        provider_code: 'qiniu-kodo',
      },
      {
        billing_date: '2026-04-11',
        cron: undefined,
        local_time: undefined,
        official_billing_lag_days: null,
        official_target_rule: undefined,
        provider_code: 'tencent-cos',
      },
    ]);
    expect(selectedRunScopeSummary(run, labelFromAny)).toBe(
      'job=manual-trigger | billing_date=2026-04-10 | billing_month=2026-04 | scheduled_provider=provider:qiniu-kodo | providers=provider:qiniu-kodo, provider:tencent-cos | rule=T+2 | lag=2 | plans=provider:qiniu-kodo T+2 (2026-04-10) / provider:tencent-cos (2026-04-11)',
    );
    expect(selectedRunScopePayload(run)).toBe(JSON.stringify(requestedScope, null, 2));
  });
});
