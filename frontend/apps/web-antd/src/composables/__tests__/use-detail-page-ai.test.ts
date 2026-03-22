import { effectScope } from 'vue';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  clearPageOperationRegistry,
  executePageOperation,
  listPageOperations,
} from '#/components/business/ai-slide-panel/page-operation-registry';

const { pushMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({
    meta: {
      ai: {
        pageContextKey: 'tenant.ai.samples.detail',
      },
    },
    path: '/tenant/ai/samples/42',
  }),
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock('#/locales', () => ({
  $t: (key: string, params?: Record<string, unknown>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

import { useDetailPageAi } from '../use-detail-page-ai';

describe('useDetailPageAi', () => {
  afterEach(() => {
    clearPageOperationRegistry();
    pushMock.mockReset();
  });

  it('registers standard detail operations via the unified page AI registration layer', async () => {
    const refreshFn = vi.fn().mockResolvedValue(undefined);

    const scope = effectScope();
    scope.run(() => {
      useDetailPageAi({
        refreshFn,
        backRoute: '/tenant/ai/samples',
      });
    });

    const names = listPageOperations('tenant.ai.samples.detail').map(
      (op) => op.name,
    );
    expect(names).toEqual([
      'read_current_view',
      'read_current_sections',
      'refresh_detail',
      'navigate_back',
    ]);

    await executePageOperation('tenant.ai.samples.detail', 'refresh_detail');
    expect(refreshFn).toHaveBeenCalledTimes(1);

    await executePageOperation('tenant.ai.samples.detail', 'navigate_back');
    expect(pushMock).toHaveBeenCalledWith('/tenant/ai/samples');

    scope.stop();
  });

  it('respects disabled operations and extra overrides', () => {
    const scope = effectScope();
    scope.run(() => {
      useDetailPageAi({
        pageKey: 'admin.ai.custom.detail',
        refreshFn: async () => undefined,
        backRoute: '/admin/ai/custom',
        disabled: ['navigate_back'],
        extra: [
          {
            name: 'refresh_detail',
            label: 'Custom Refresh',
            readonly: true,
            handler: async () => ({
              success: true,
              message: 'custom refresh',
            }),
          },
          {
            name: 'publish_detail',
            label: 'Publish',
            readonly: false,
            handler: async () => ({
              success: true,
              message: 'published',
            }),
          },
        ],
      });
    });

    const ops = listPageOperations('admin.ai.custom.detail');
    expect(ops.map((op) => op.name)).toEqual([
      'read_current_view',
      'read_current_sections',
      'refresh_detail',
      'publish_detail',
    ]);
    expect(ops[2]?.label).toBe('Custom Refresh');

    scope.stop();
  });
});
