/**
 * AI 会话级授权管理
 *
 * 使用 sessionStorage 存储授权，浏览器刷新后清空。
 * 格式: "read:agents", "create:agents", "update:agents", "delete:agents"
 */

const STORAGE_KEY = 'ai_consented_actions';

/**
 * 获取所有已授权操作列表
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
 * 添加授权操作
 */
export function addConsent(consentKey: string): void {
  const actions = new Set(getConsentedActions());
  actions.add(consentKey);
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...actions]));
}

/**
 * 检查是否已授权
 */
export function hasConsent(consentKey: string): boolean {
  return getConsentedActions().includes(consentKey);
}

/**
 * 清除所有授权（浏览器刷新时自动清除，也可手动调用）
 */
export function clearConsents(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}
