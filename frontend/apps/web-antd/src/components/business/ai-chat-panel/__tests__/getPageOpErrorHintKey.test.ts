/**
 * error_type to i18n hint key mapping tests.
 * error_type 到 i18n 提示 key 的映射测试。
 */
import { describe, expect, it } from 'vitest';

import { getPageOpErrorHintKey } from '../pageOpErrorHints';

describe('getPageOpErrorHintKey', () => {
  it('maps timeout to pageOpTimeoutHint', () => {
    expect(getPageOpErrorHintKey('timeout')).toBe(
      'common.globalAiChat.pageOpTimeoutHint',
    );
  });

  it('maps user_cancelled to pageOpUserCancelledHint', () => {
    expect(getPageOpErrorHintKey('user_cancelled')).toBe(
      'common.globalAiChat.pageOpUserCancelledHint',
    );
  });

  it('maps not_registered to pageOpNotRegisteredHint', () => {
    expect(getPageOpErrorHintKey('not_registered')).toBe(
      'common.globalAiChat.pageOpNotRegisteredHint',
    );
  });

  it('maps invalid_input to pageOpInvalidInputHint', () => {
    expect(getPageOpErrorHintKey('invalid_input')).toBe(
      'common.globalAiChat.pageOpInvalidInputHint',
    );
  });

  it('maps invalid_input_empty_content to pageOpInvalidInputHint', () => {
    expect(getPageOpErrorHintKey('invalid_input_empty_content')).toBe(
      'common.globalAiChat.pageOpInvalidInputHint',
    );
  });

  it('maps session_not_found to pageOpSessionNotFoundHint', () => {
    expect(getPageOpErrorHintKey('session_not_found')).toBe(
      'common.globalAiChat.pageOpSessionNotFoundHint',
    );
  });

  it('maps pending_confirmation to pageOpPendingConfirmationHint', () => {
    expect(getPageOpErrorHintKey('pending_confirmation')).toBe(
      'common.globalAiChat.pageOpPendingConfirmationHint',
    );
  });

  it('maps execution_failed to pageOpExecFailedHint (no explicit key)', () => {
    expect(getPageOpErrorHintKey('execution_failed')).toBe(
      'common.globalAiChat.pageOpExecFailedHint',
    );
  });

  it('returns pageOpExecFailedHint for unknown error_type', () => {
    expect(getPageOpErrorHintKey('unknown_type')).toBe(
      'common.globalAiChat.pageOpExecFailedHint',
    );
  });

  it('returns pageOpExecFailedHint when errorType is empty', () => {
    expect(getPageOpErrorHintKey('')).toBe(
      'common.globalAiChat.pageOpExecFailedHint',
    );
    expect(getPageOpErrorHintKey(undefined)).toBe(
      'common.globalAiChat.pageOpExecFailedHint',
    );
  });
});
