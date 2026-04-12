// @vitest-environment happy-dom

import type { EnhancedFormFieldDescriptor } from '#/composables/ai-operation-types';
import type { TrackableFormApi } from '#/composables/use-form-state-tracker';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { formStateTracker } from '#/composables/use-form-state-tracker';

import { fillRuntimeForm, getRuntimeSnapshot, submitRuntimeForm } from '../runtime-bridge';
import { UIActionExecutor } from '../ui-action-executor';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
  i18n: {
    global: {
      locale: {
        value: 'en-US',
      },
    },
  },
}));

vi.mock('#/components/business/ai-runtime/page-key-utils', () => ({
  resolveRoutePageKey: (_route: unknown, pathname?: string) => {
    const normalizedPath = (pathname || '/').trim();
    const pageKey = normalizedPath
      .replace(/[?#].*$/g, '')
      .replace(/^\/+/, '')
      .replace(/\/+/g, '.');
    return pageKey || 'root';
  },
}));

vi.mock('#/composables/use-page-session', () => ({
  getActivePageSessionId: () => 'perf-page-session',
}));

const SAMPLE_COUNT = 20;
const WARMUP_COUNT = 2;
const FORM_FIELD_COUNT = 20;

function nowInMs(): number {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now();
  }
  return Date.now();
}

function percentile(values: number[], ratio: number): number {
  const sorted = [...values].sort((left, right) => left - right);
  const clamped = Math.min(Math.max(ratio, 0), 1);
  const index = Math.min(
    sorted.length - 1,
    Math.max(0, Math.ceil(sorted.length * clamped) - 1),
  );
  return sorted[index] ?? 0;
}

interface MetricSummary {
  p50: number;
  p95: number;
}

async function measureAsyncMetric(
  runner: () => Promise<void> | void,
): Promise<MetricSummary> {
  for (let index = 0; index < WARMUP_COUNT; index += 1) {
    await runner();
  }

  const samples: number[] = [];
  for (let index = 0; index < SAMPLE_COUNT; index += 1) {
    const start = nowInMs();
    await runner();
    samples.push(nowInMs() - start);
  }

  return {
    p50: percentile(samples, 0.5),
    p95: percentile(samples, 0.95),
  };
}

function expectMetricWithinThreshold(
  metric: MetricSummary,
  limits: { p50: number; p95: number },
): void {
  expect(metric.p50).toBeLessThan(limits.p50);
  expect(metric.p95).toBeLessThan(limits.p95);
}

function buildFieldDescriptors(
  count: number,
): Record<string, EnhancedFormFieldDescriptor> {
  const descriptors: Record<string, EnhancedFormFieldDescriptor> = {};
  for (let index = 1; index <= count; index += 1) {
    descriptors[`field_${index}`] = {
      component: 'input',
      description: `Performance field ${index}`,
      label: `Field ${index}`,
      required: true,
      type: 'string',
    };
  }
  return descriptors;
}

function buildFieldUpdates(count: number): Record<string, string> {
  const updates: Record<string, string> = {};
  for (let index = 1; index <= count; index += 1) {
    updates[`field_${index}`] = `value-${index}`;
  }
  return updates;
}

function setupFixedDom(pageKey: string, fieldCount: number): void {
  const inputs = Array.from({ length: fieldCount }, (_, index) => {
    const field = `field_${index + 1}`;
    return `<input name="${field}" data-testid="${field}" />`;
  }).join('');

  document.body.setAttribute('data-page-key', pageKey);
  document.body.innerHTML = `
    <main>
      <button data-testid="perf-toggle-drawer">Toggle Drawer</button>
      <section class="perf-form-shell">${inputs}</section>
    </main>
  `;

  const trigger = document.querySelector(
    '[data-testid="perf-toggle-drawer"]',
  ) as HTMLButtonElement | null;
  if (!trigger) {
    throw new Error('Performance drawer toggle button is missing');
  }

  trigger.addEventListener('click', () => {
    const existing = document.querySelector('.ant-drawer');
    if (existing) {
      existing.remove();
      return;
    }
    const drawer = document.createElement('div');
    drawer.className = 'ant-drawer';
    drawer.innerHTML = '<div class="ant-drawer-title">Perf Drawer</div>';
    document.body.appendChild(drawer);
  });
}

function setupTrackedForm(pageKey: string, fieldCount: number): {
  formApiState: { submitCount: number; values: Record<string, unknown> };
  sessionId: string;
  updates: Record<string, string>;
} {
  const formApiState = {
    submitCount: 0,
    values: {} as Record<string, unknown>,
  };

  const formApi: TrackableFormApi = {
    getValues: async () => ({ ...formApiState.values }),
    setValues: (values: Record<string, unknown>) => {
      formApiState.values = {
        ...formApiState.values,
        ...values,
      };
    },
    submitForm: async () => {
      formApiState.submitCount += 1;
    },
    validate: async () => ({ valid: true }),
  };

  const sessionId = formStateTracker.open(pageKey, {
    fieldDescriptors: buildFieldDescriptors(fieldCount),
    formApi,
    initialValues: {},
    mode: 'add',
  });

  return {
    formApiState,
    sessionId,
    updates: buildFieldUpdates(fieldCount),
  };
}

describe('ui-runtime performance acceptance', () => {
  beforeEach(() => {
    vi.useRealTimers();
    formStateTracker.clear();
    document.body.innerHTML = '';
  });

  afterEach(() => {
    formStateTracker.clear();
    document.body.innerHTML = '';
  });

  it('measures snapshot/click/fill/submit metrics against local targets', async () => {
    const pageKey = 'tenant.ai.agents';
    setupFixedDom(pageKey, FORM_FIELD_COUNT);
    const { formApiState, sessionId, updates } = setupTrackedForm(
      pageKey,
      FORM_FIELD_COUNT,
    );
    const actionExecutor = new UIActionExecutor();

    const snapshotMetric = await measureAsyncMetric(() => {
      const snapshot = getRuntimeSnapshot('compact');
      expect(snapshot.mode).toBe('compact');
    });

    const clickMetric = await measureAsyncMetric(async () => {
      const result = await actionExecutor.execute({
        action_type: 'ui_click',
        target_locator: 'testid:perf-toggle-drawer',
        wait_timeout_ms: 16,
      });
      expect(result.success).toBe(true);
      expect(result.diff.ui_epoch).toBeGreaterThan(0);
    });

    const fillMetric = await measureAsyncMetric(async () => {
      const result = await fillRuntimeForm({
        fields: updates,
        formSessionId: sessionId,
      });
      expect(result.success).toBe(true);
      expect((result.data?.fields_updated as string[] | undefined)?.length).toBe(
        FORM_FIELD_COUNT,
      );
    });

    const submitMetric = await measureAsyncMetric(async () => {
      const result = await submitRuntimeForm({
        confirm: true,
        formSessionId: sessionId,
      });
      expect(result.success).toBe(true);
      expect(result.error_type).toBeUndefined();
    });

    expectMetricWithinThreshold(snapshotMetric, {
      p50: 150,
      p95: 300,
    });
    expectMetricWithinThreshold(clickMetric, {
      p50: 250,
      p95: 500,
    });
    expectMetricWithinThreshold(fillMetric, {
      p50: 500,
      p95: 1000,
    });
    expectMetricWithinThreshold(submitMetric, {
      p50: 800,
      p95: 1500,
    });

    expect(formApiState.submitCount).toBeGreaterThan(0);
  });
});
