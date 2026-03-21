/**
 * Detail Page AI Operations Composable
 * 详情页 AI 操作 composable
 *
 * Provides automatic registration of standard detail page operations:
 * 为详情页提供标准操作自动注册：
 * - refresh_detail: reload detail data / 刷新详情数据
 * - navigate_back: go back to list page / 返回列表页
 *
 * Usage:
 * ```ts
 * useDetailPageAi({
 *   refreshFn: () => loadAgent(),
 *   backRoute: '/admin/ai/agents',
 *   extra: [{ name: 'save_model_params', ... }],
 * });
 * ```
 */
import type { PageOperation } from '#/components/business/ai-slide-panel/page-operation-registry';

import { useRouter } from 'vue-router';

import { $t } from '#/locales';
import { usePageAIRegistration } from './use-page-ai-registration';

/**
 * Options for useDetailPageAi
 * useDetailPageAi 配置选项
 */
export interface DetailPageAiOptions {
  /**
   * Page key override (defaults to normalizePageKey of route.meta.ai?.pageContextKey or route.path)
   * 页面标识覆盖（默认通过 normalizePageKey 推导为点号格式）
   */
  pageKey?: string;
  /**
   * Refresh detail data callback (required)
   * 刷新详情数据回调（必填）
   */
  refreshFn: () => Promise<unknown>;
  /**
   * Back route path (e.g. '/admin/ai/agents') — enables navigate_back
   * 返回路由路径 — 启用 navigate_back 操作
   */
  backRoute?: string;
  /**
   * Operations to disable / 禁用的操作名称列表
   */
  disabled?: string[];
  /**
   * Extra custom operations (overrides same-named standard ops)
   * 额外自定义操作（可覆盖同名标准操作）
   */
  extra?: PageOperation[];
}

/**
 * Register standard AI operations for a detail page
 * 为详情页注册标准 AI 操作
 *
 * Auto-registers: refresh_detail, navigate_back (if backRoute provided)
 * 自动注册：refresh_detail、navigate_back（有 backRoute 时）
 */
export function useDetailPageAi(opts: DetailPageAiOptions): void {
  const {
    refreshFn,
    backRoute,
    disabled = [],
    extra = [],
  } = opts;

  const router = useRouter();

  const isDisabled = (name: string) => disabled.includes(name);

  const operations: PageOperation[] = [];

  // ── 1. refresh_detail ──
  if (!isDisabled('refresh_detail')) {
    operations.push({
      name: 'refresh_detail',
      label: $t('shared.pageOperation.refreshDetail'),
      description:
        'Reload the current detail data / 刷新当前详情数据',
      readonly: true,
      handler: async () => {
        await refreshFn();
        return { success: true, message: $t('shared.pageOperation.msg.detailRefreshed') };
      },
    });
  }

  // ── 2. navigate_back ──
  if (!isDisabled('navigate_back') && backRoute) {
    operations.push({
      name: 'navigate_back',
      label: $t('shared.pageOperation.navigateTo'),
      description:
        'Navigate back to the list page / 返回列表页',
      readonly: true,
      handler: async () => {
        router.push(backRoute);
        return {
          success: true,
          message: $t('shared.pageOperation.msg.navigatedTo', { path: backRoute }),
        };
      },
    });
  }

  // Merge extra operations (extra overrides same-named standard ops)
  // 合并额外操作（extra 可覆盖同名标准操作）
  for (const op of extra) {
    const existingIdx = operations.findIndex((o) => o.name === op.name);
    if (existingIdx >= 0) {
      operations[existingIdx] = op;
    } else {
      operations.push(op);
    }
  }

  usePageAIRegistration({
    pageKey: opts.pageKey,
    registerContext: false,
    operations,
  });
}
