import { afterEach, describe, expect, it, vi } from 'vitest';

const { messageErrorMock } = vi.hoisted(() => ({
  messageErrorMock: vi.fn(),
}));

vi.mock('ant-design-vue', () => ({
  message: {
    error: messageErrorMock,
  },
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

import { getErrorMessage, showRequestError } from '../error-helpers';

describe('error-helpers', () => {
  afterEach(() => {
    messageErrorMock.mockReset();
  });

  it('formats request errors with trace id suffix', () => {
    const text = getErrorMessage(
      {
        response: {
          data: {
            message: 'Provider failed',
            trace_id: 'trace-test-1',
          },
          status: 500,
        },
      },
      'common.requestFailed',
    );

    expect(text).toContain('Provider failed');
    expect(text).toContain('trace-test-1');
  });

  it('shows formatted request error through unified message entry', () => {
    const text = showRequestError(
      {
        response: {
          data: {
            message: 'Save failed',
            trace_id: 'trace-test-2',
          },
          status: 500,
        },
      },
      'common.saveFailed',
    );

    expect(text).toContain('trace-test-2');
    expect(messageErrorMock).toHaveBeenCalledWith(text);
  });
});
