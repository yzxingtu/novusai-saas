import { describe, expect, it, vi } from 'vitest';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/router', () => ({
  router: {
    push: vi.fn(),
  },
}));

import {
  createCreateRecordPageOperation,
  createOpenCurrentPageOperation,
  createOpenPageOperation,
  createPrefilledCreatePageOperation,
  createViewDetailPageOperation,
} from '../use-page-ai-operation-helpers';

describe('use-page-ai-operation-helpers legacy seam guards', () => {
  it('requires explicit names for helpers that previously emitted legacy defaults', () => {
    expect(() =>
      createCreateRecordPageOperation({
        action: () => undefined,
        name: '',
      }),
    ).toThrow(/requires an explicit operation name/i);

    expect(() =>
      createPrefilledCreatePageOperation({
        name: '   ',
        openCreate: () => undefined,
      }),
    ).toThrow(/requires an explicit operation name/i);

    expect(() =>
      createOpenPageOperation({
        name: '',
        to: '/admin/ai/agents',
      }),
    ).toThrow(/requires an explicit operation name/i);

    expect(() =>
      createOpenCurrentPageOperation({
        name: '',
        open: () => undefined,
      }),
    ).toThrow(/requires an explicit operation name/i);
  });

  it('keeps detail helpers explicit instead of silently falling back to read_row_detail', () => {
    const operation = createViewDetailPageOperation({
      name: 'ui_open_surface',
      openDetail: () => undefined,
    });

    expect(operation.name).toBe('ui_open_surface');
  });
});
