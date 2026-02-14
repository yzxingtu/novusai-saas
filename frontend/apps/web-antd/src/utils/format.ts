/**
 * 通用格式化工具函数
 *
 * 统一 Token、费用等数值的展示格式，避免各模块重复定义。
 */

/**
 * 格式化 Token 数量
 * @param tokens Token 数量
 * @param fallback 空值显示，默认 '-'
 */
export function formatTokens(
  tokens: null | number | undefined,
  fallback = '-',
): string {
  if (tokens === null || tokens === undefined || tokens === 0) return fallback;
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(0)}K`;
  return `${tokens}`;
}

/**
 * 格式化费用（美元）
 * @param cost 费用金额
 * @param fallback 空值显示，默认 '-'
 */
export function formatCost(
  cost: null | number | undefined,
  fallback = '-',
): string {
  if (cost === null || cost === undefined) return fallback;
  if (cost === 0) return '$0';
  if (cost < 0.001) return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(4)}`;
}
