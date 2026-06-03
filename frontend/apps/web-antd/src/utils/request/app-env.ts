/**
 * App environment helpers for request/error presentation.
 * 应用环境辅助：用于请求/错误展示策略。
 */

/**
 * Whether current UI should display debug details for errors.
 * 当前界面是否展示错误调试细节。
 */
export function isDevErrorMode(): boolean {
  return Boolean(import.meta.env.DEV);
}
