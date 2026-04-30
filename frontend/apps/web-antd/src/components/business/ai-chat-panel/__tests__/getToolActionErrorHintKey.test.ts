/**
 * error_type to i18n hint key mapping tests.
 * error_type 到 i18n 提示 key 的映射测试。
 */
import { describe, expect, it } from 'vitest';

import { getToolActionErrorHintKey } from '../toolActionErrorHints';

describe('getToolActionErrorHintKey', () => {
  it('maps timeout to toolActionTimeoutHint', () => {
    expect(getToolActionErrorHintKey('timeout')).toBe(
      'common.globalAiChat.toolActionTimeoutHint',
    );
  });

  it('maps user_cancelled to toolActionUserCancelledHint', () => {
    expect(getToolActionErrorHintKey('user_cancelled')).toBe(
      'common.globalAiChat.toolActionUserCancelledHint',
    );
  });

  it('maps not_registered to toolActionNotRegisteredHint', () => {
    expect(getToolActionErrorHintKey('not_registered')).toBe(
      'common.globalAiChat.toolActionNotRegisteredHint',
    );
  });

  it('maps invalid_input to toolActionInvalidInputHint', () => {
    expect(getToolActionErrorHintKey('invalid_input')).toBe(
      'common.globalAiChat.toolActionInvalidInputHint',
    );
  });

  it('maps invalid_input_empty_content to toolActionInvalidInputHint', () => {
    expect(getToolActionErrorHintKey('invalid_input_empty_content')).toBe(
      'common.globalAiChat.toolActionInvalidInputHint',
    );
  });

  it('maps session_not_found to toolActionSessionNotFoundHint', () => {
    expect(getToolActionErrorHintKey('session_not_found')).toBe(
      'common.globalAiChat.toolActionSessionNotFoundHint',
    );
  });

  it('maps pending_confirmation to toolActionPendingConfirmationHint', () => {
    expect(getToolActionErrorHintKey('pending_confirmation')).toBe(
      'common.globalAiChat.toolActionPendingConfirmationHint',
    );
  });

  it('maps execution_failed to toolActionExecFailedHint (no explicit key)', () => {
    expect(getToolActionErrorHintKey('execution_failed')).toBe(
      'common.globalAiChat.toolActionExecFailedHint',
    );
  });

  it('returns toolActionExecFailedHint for unknown error_type', () => {
    expect(getToolActionErrorHintKey('unknown_type')).toBe(
      'common.globalAiChat.toolActionExecFailedHint',
    );
  });

  it('returns toolActionExecFailedHint when errorType is empty', () => {
    expect(getToolActionErrorHintKey('')).toBe(
      'common.globalAiChat.toolActionExecFailedHint',
    );
    expect(getToolActionErrorHintKey(undefined)).toBe(
      'common.globalAiChat.toolActionExecFailedHint',
    );
  });
});
