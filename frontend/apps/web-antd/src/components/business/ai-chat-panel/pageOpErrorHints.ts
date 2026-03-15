/**
 * Page operation error_type to i18n hint key mapping.
 * 页面操作 error_type 到 i18n 提示 key 的映射。
 */

const ERROR_TYPE_HINT_MAP: Record<string, string> = {
  timeout: 'common.globalAiChat.pageOpTimeoutHint',
  user_cancelled: 'common.globalAiChat.pageOpUserCancelledHint',
  not_registered: 'common.globalAiChat.pageOpNotRegisteredHint',
  invalid_input_empty_content: 'common.globalAiChat.pageOpInvalidInputHint',
  invalid_input: 'common.globalAiChat.pageOpInvalidInputHint',
  session_not_found: 'common.globalAiChat.pageOpSessionNotFoundHint',
  pending_confirmation: 'common.globalAiChat.pageOpPendingConfirmationHint',
};

/** Map page op error_type to i18n hint key / 按页面操作错误类型映射提示 key */
export function getPageOpErrorHintKey(errorType?: string): string {
  if (errorType && ERROR_TYPE_HINT_MAP[errorType])
    return ERROR_TYPE_HINT_MAP[errorType];
  return 'common.globalAiChat.pageOpExecFailedHint';
}
