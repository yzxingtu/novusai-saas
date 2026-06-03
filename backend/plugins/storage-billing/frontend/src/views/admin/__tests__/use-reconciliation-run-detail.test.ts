import type {
  ReconciliationRunChargeListResponse,
  ReconciliationRunDetailResponse,
} from '../../../types';

import { ref } from 'vue';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@novus/plugin-shared', () => ({
  $t: (key: string) => key,
}));

import { useReconciliationRunDetail } from '../use-reconciliation-run-detail';

function createRunDetail(): ReconciliationRunDetailResponse {
  return {
    run: {
      billing_date: '2026-04-10',
      completed_at: '2026-04-11T00:10:00Z',
      error_message: null,
      id: 7,
      provider_codes: ['qiniu-kodo', 'tencent-cos'],
      requested_scope: {},
      run_key: 'run-7',
      started_at: '2026-04-11T00:00:00Z',
      status: 'completed',
      summary: {
        providers: [
          { provider_code: 'qiniu-kodo', source_status: 'completed' },
        ],
      },
      trigger_type: 'manual',
    },
    sources: [
      {
        amount_total: '10.00',
        billing_date: '2026-04-10',
        currency: 'CNY',
        driver_code: 'qiniu-kodo',
        error_message: null,
        fetched_at: '2026-04-11T00:00:00Z',
        id: 1,
        provider_code: 'qiniu-kodo',
        raw_payload_json: {},
        run_id: 7,
        source_key: 'stmt-1',
        source_ref: 'source-a',
        source_status: 'fetched',
        usage_bytes: 1024,
      },
      {
        amount_total: '8.00',
        billing_date: '2026-04-10',
        currency: 'CNY',
        driver_code: 'qiniu-kodo',
        error_message: null,
        fetched_at: '2026-04-11T00:00:00Z',
        id: 2,
        provider_code: 'qiniu-kodo',
        raw_payload_json: {
          allocation_audit: {
            unmatched_item_samples: ['tenant-9'],
          },
        },
        run_id: 7,
        source_key: 'stmt-2',
        source_ref: '',
        source_status: 'completed_with_gaps',
        usage_bytes: 512,
      },
      {
        amount_total: '5.00',
        billing_date: '2026-04-10',
        currency: 'CNY',
        driver_code: 'tencent-cos',
        error_message: null,
        fetched_at: '2026-04-11T00:00:00Z',
        id: 3,
        provider_code: 'tencent-cos',
        raw_payload_json: {},
        run_id: 7,
        source_key: 'stmt-3',
        source_ref: 'source-c',
        source_status: 'completed',
        usage_bytes: 256,
      },
    ],
  };
}

function createChargeResponse(): ReconciliationRunChargeListResponse {
  return {
    filters: {
      provider_code: 'qiniu-kodo',
      source_id: '2',
      tenant_id: '18',
      trigger_type: 'manual',
    },
    items: [],
    run_id: 7,
    total: 0,
  };
}

describe('useReconciliationRunDetail', () => {
  it('derives provider/source options and active filter badges from refs', () => {
    const selectedRunDetail = ref<null | ReconciliationRunDetailResponse>(
      createRunDetail(),
    );
    const selectedRunChargeResponse = ref<
      null | ReconciliationRunChargeListResponse
    >(createChargeResponse());

    const detail = useReconciliationRunDetail({
      providerLabelFromAny: (code) => `provider:${code}`,
      selectedRunChargeResponse,
      selectedRunDetail,
    });

    expect(detail.selectedRun.value?.id).toBe(7);
    expect(detail.selectedRunProviderResults.value).toEqual([
      { provider_code: 'qiniu-kodo', source_status: 'completed' },
    ]);
    expect(detail.auditedSources.value.map((source) => source.id)).toEqual([2]);
    expect(detail.runChargeProviderOptions.value).toEqual([
      { label: 'provider:qiniu-kodo', value: 'qiniu-kodo' },
      { label: 'provider:tencent-cos', value: 'tencent-cos' },
    ]);
    expect(detail.runChargeSourceOptions.value).toEqual([
      { label: 'provider:qiniu-kodo · source-a', value: 1 },
      { label: 'provider:qiniu-kodo · stmt-2', value: 2 },
      { label: 'provider:tencent-cos · source-c', value: 3 },
    ]);
    expect(detail.runChargeActiveFilters.value).toEqual([
      {
        key: 'provider_code',
        label: 'plugin.storage-billing.admin.runs.charges.filterProvider',
        value: 'provider:qiniu-kodo',
      },
      {
        key: 'source_id',
        label: 'plugin.storage-billing.admin.runs.charges.filterSource',
        value: '#2',
      },
      {
        key: 'tenant_id',
        label: 'plugin.storage-billing.admin.runs.charges.filterTenant',
        value: '#18',
      },
      {
        key: 'trigger_type',
        label: 'trigger_type',
        value: 'manual',
      },
    ]);
  });

  it('normalizes form filters, resets state, and resolves charge source labels', () => {
    const selectedRunDetail = ref<null | ReconciliationRunDetailResponse>(
      createRunDetail(),
    );
    const selectedRunChargeResponse = ref<
      null | ReconciliationRunChargeListResponse
    >(null);

    const detail = useReconciliationRunDetail({
      providerLabelFromAny: (code) => `provider:${code}`,
      selectedRunChargeResponse,
      selectedRunDetail,
    });

    detail.runChargeFilters.provider_code = 'qiniu-kodo';
    detail.runChargeFilters.source_id = 2;
    detail.runChargeFilters.tenant_id = ' 42 ';

    expect(detail.currentRunChargeFilters()).toEqual({
      provider_code: 'qiniu-kodo',
      source_id: 2,
      tenant_id: 42,
    });
    expect(
      detail.sourceLabelFromCharge({
        amount_total: '1.00',
        billing_date: '2026-04-10',
        charge_basis: 'bucket',
        currency: 'CNY',
        driver_code: 'qiniu-kodo',
        id: 1,
        provider_code: 'qiniu-kodo',
        source_id: 2,
        tenant_id: 9,
        usage_bytes: 1,
      }),
    ).toBe('stmt-2');
    expect(
      detail.sourceLabelFromCharge({
        amount_total: '1.00',
        billing_date: '2026-04-10',
        charge_basis: 'bucket',
        currency: 'CNY',
        driver_code: 'qiniu-kodo',
        id: 2,
        provider_code: 'qiniu-kodo',
        source_id: 999,
        tenant_id: 9,
        usage_bytes: 1,
      }),
    ).toBe('#999');

    detail.resetRunChargeFiltersState();

    expect(detail.runChargeFilters).toEqual({
      provider_code: '',
      source_id: null,
      tenant_id: '',
    });
  });
});
