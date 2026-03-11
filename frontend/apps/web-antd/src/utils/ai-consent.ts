/**
 * AI conversation-level authorization management
 * AI 会话级别授权管理
 *
 * Stored in sessionStorage, automatically cleared on browser refresh.
 * Used to manage temporary authorizations during AI conversations,
 * e.g., user confirming resource read permissions.
 * 基于 sessionStorage 存储，浏览器刷新后自动清除。
 * 用于管理 AI 对话中的临时授权，例如用户确认读取资源权限。
 */

const STORAGE_KEY = 'ai_consented_actions';

/**
 * Get the list of currently consented actions / 获取当前已授权的动作列表
 */
export function getConsentedActions(): string[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

/**
 * Add a consent / 添加授权
 */
export function addConsent(consentKey: string): void {
  const actions = new Set(getConsentedActions());
  actions.add(consentKey);
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...actions]));
}

/**
 * Check if an action is consented / 检查是否已授权
 */
export function hasConsent(consentKey: string): boolean {
  return getConsentedActions().includes(consentKey);
}

/**
 * Clear all consents / 清除所有授权（浏览器刷新时自动清除，也可手动调用）
 */
export function clearConsents(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}
