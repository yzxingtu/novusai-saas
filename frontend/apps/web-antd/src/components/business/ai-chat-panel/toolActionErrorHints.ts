/**
 * Tool action error_type to i18n hint key mapping.
 * 工具动作 error_type 到 i18n 提示 key 的映射。
 */

const ERROR_TYPE_HINT_MAP: Record<string, string> = {
  timeout: 'common.globalAiChat.toolActionTimeoutHint',
  user_cancelled: 'common.globalAiChat.toolActionUserCancelledHint',
  not_registered: 'common.globalAiChat.toolActionNotRegisteredHint',
  invalid_input_empty_content: 'common.globalAiChat.toolActionInvalidInputHint',
  invalid_input: 'common.globalAiChat.toolActionInvalidInputHint',
  session_not_found: 'common.globalAiChat.toolActionSessionNotFoundHint',
  pending_confirmation: 'common.globalAiChat.toolActionPendingConfirmationHint',
};

/** Map tool action error_type to i18n hint key / 按工具动作错误类型映射提示 key */
export function getToolActionErrorHintKey(errorType?: string): string {
  if (errorType && ERROR_TYPE_HINT_MAP[errorType])
    return ERROR_TYPE_HINT_MAP[errorType];
  return 'common.globalAiChat.toolActionExecFailedHint';
}
