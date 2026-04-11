import { describe, expect, it, vi } from 'vitest';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/common', () => ({
  formatDate: (value: string | null | undefined) =>
    value ? `date:${value}` : null,
  formatRelativeTime: (value: string | null | undefined) =>
    value ? `relative:${value}` : null,
}));

vi.mock('../data', () => ({
  getManifestStatusText: (present: boolean) =>
    present ? 'manifest.present' : 'manifest.absent',
}));

import {
  buildWorkbenchItemMessage,
  buildWorkbenchStats,
  getActionErrorMessage,
  getActiveWorkbenchItems,
  getWorkbenchFilterConfig,
} from '../workbench-utils';

describe('codegen workbench utils', () => {
  it('builds item messages from errors, delete guards, and generation time', () => {
    expect(
      buildWorkbenchItemMessage({
        delete_allowed: true,
        id: 1,
        last_error: 'render failed',
        manifest_present: false,
        name: 'Article',
        resource: 'article',
        status: 'draft',
      } as never),
    ).toBe('render failed');

    expect(
      buildWorkbenchItemMessage({
        delete_allowed: false,
        delete_reason_message: 'guarded',
        id: 2,
        manifest_present: false,
        name: 'Comment',
        resource: 'comment',
        status: 'generated',
      } as never),
    ).toBe('guarded');

    expect(
      buildWorkbenchItemMessage({
        delete_allowed: true,
        id: 3,
        last_generated_at: '2026-04-11T10:00:00Z',
        manifest_present: true,
        name: 'Invoice',
        resource: 'invoice',
        status: 'applied',
      } as never),
    ).toBe('manifest.present · relative:2026-04-11T10:00:00Z');
  });

  it('extracts action error messages in transport priority order', () => {
    expect(
      getActionErrorMessage(
        { response: { data: { message: 'top-level message' } } },
        'fallback',
      ),
    ).toBe('top-level message');

    expect(
      getActionErrorMessage(
        { response: { data: { detail: { error: 'nested detail error' } } } },
        'fallback',
      ),
    ).toBe('nested detail error');

    expect(getActionErrorMessage(new Error('plain error'), 'fallback')).toBe(
      'plain error',
    );
  });

  it('builds stats/filter config and active items from summary', () => {
    const summary = {
      sections: {
        applied: [],
        attention: [
          {
            delete_allowed: true,
            id: 8,
            last_error: 'needs review',
            manifest_present: false,
            name: 'Alert',
            resource: 'alert',
            status: 'draft',
          },
        ],
        draft: [
          {
            delete_allowed: false,
            delete_reason_message: 'guarded',
            id: 3,
            manifest_present: false,
            name: 'Draft',
            resource: 'draft',
            status: 'draft',
          },
        ],
        generated: [],
        rollback: [
          {
            delete_allowed: true,
            id: 4,
            last_generated_at: '2026-04-11T12:00:00Z',
            manifest_present: true,
            name: 'Rollback',
            resource: 'rollback',
            status: 'generated',
          },
        ],
      },
      stats: {
        applied: 0,
        attention: 1,
        draft: 1,
        generated: 0,
        rollback: 1,
        total: 2,
      },
    } as const;

    const stats = buildWorkbenchStats(summary as never);
    expect(stats.map((item) => item.key)).toEqual([
      'draft',
      'generated',
      'applied',
      'rollback',
      'attention',
    ]);

    expect(getWorkbenchFilterConfig('rollback', stats)).toMatchObject({
      label: 'admin.system.codegen.workbench.rollbackReady',
      mode: 'panel',
    });

    expect(getActiveWorkbenchItems(summary as never, 'draft')).toMatchObject([
      {
        message: 'guarded',
        resource: 'draft',
        severity: 'warning',
      },
    ]);
    expect(getActiveWorkbenchItems(summary as never, 'all')).toMatchObject([
      {
        message: 'needs review',
        resource: 'alert',
        severity: 'error',
      },
    ]);
  });
});
