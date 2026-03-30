/**
 * AI conversation-level transient authorization cache
 * AI 对话级临时授权缓存
 *
 * Kept in-memory only for the current browser runtime.
 * Backend ExecutionTrustPolicy / ExecutionDecision remains the source of truth.
 * 仅保存在当前浏览器运行时内存中。
 * 后端 ExecutionTrustPolicy / ExecutionDecision 才是最终真相。
 */

const consentedActions = new Set<string>();

/**
 * Get the list of currently consented actions / 获取当前已授权的动作列表
 */
export function getConsentedActions(): string[] {
  return [...consentedActions];
}

/**
 * Add a consent / 添加授权
 */
export function addConsent(consentKey: string): void {
  if (!consentKey) {
    return;
  }
  consentedActions.add(consentKey);
}

/**
 * Check if an action is consented / 检查是否已授权
 */
export function hasConsent(consentKey: string): boolean {
  return consentedActions.has(consentKey);
}

/**
 * Clear all consents / 清除所有授权
 */
export function clearConsents(): void {
  consentedActions.clear();
}
