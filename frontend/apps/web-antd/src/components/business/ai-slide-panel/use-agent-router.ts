import type { Ref } from 'vue';

import type { AgentRouteResponse, PageContext } from '#/api/shared/ai-chat';
import type { AgentItem } from '#/types/ai-chat';

/** Route cache TTL: 2 minutes (shorter to avoid wrong agent reuse) / 路由缓存 TTL 2 分钟 */
/**
 * Agent Router Composable
 * 智能体路由 Composable
 *
 * Implements P1-P3 routing priority chain:
 * P1: pinnedAgentId direct pass-through (user manually pinned)
 * P2: Call /route API (with page_context), backend Router agent AI selection
 * P3: Backend fallback to default_chat
 * 实现 P1-P3 路由优先级链：
 * P1: pinnedAgentId 直通（用户手动固定）
 * P2: 调用 /route API（含 page_context），后端 Router 智能体 AI 选择
 * P3: 后端 fallback 到 default_chat
 *
 * P3+P4 are combined into a single API call; backend handles degradation.
 * P3+P4 合并为一次 API 调用，后端自行处理降级。
 */
import { ref, unref, watch } from 'vue';

import { routeMessageApi } from '#/api/shared/ai-chat';
import { getRuntimeThinPageContext } from '#/components/business/ai-runtime/runtime-bridge';

const ROUTE_CACHE_TTL_MS = 2 * 60 * 1000;
const ROUTE_PAGE_CONTEXT_NAV_LIMIT = 6;
const ROUTE_PAGE_CONTEXT_SURFACE_LIMIT = 4;
const ROUTE_PAGE_CONTEXT_REQUIRED_FIELD_LIMIT = 4;

function _normalizeRouteText(value: unknown): string {
  return String(value ?? '')
    .toLocaleLowerCase()
    .replaceAll(/[^\p{L}\p{N}]+/gu, ' ')
    .trim();
}

function _routeMessageTokens(message: string): string[] {
  const normalized = _normalizeRouteText(message);
  if (!normalized) {
    return [];
  }
  return normalized
    .split(/\s+/)
    .filter((token) => token.length >= 2)
    .slice(0, 8);
}

function _trimNonEmptyString(value: unknown): string | undefined {
  const normalized = String(value ?? '').trim();
  return normalized || undefined;
}

function _trimBreadcrumb(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => _trimNonEmptyString(item))
    .filter((item): item is string => !!item)
    .slice(0, ROUTE_PAGE_CONTEXT_REQUIRED_FIELD_LIMIT);
}

function _scoreRouteNavigationEntry(
  entry: {
    breadcrumb?: string[];
    page_key?: string;
    path?: string;
    title?: string;
  },
  options: {
    currentPageKey?: string;
    currentPath?: string;
    messageTokens: string[];
    order: number;
  },
): number {
  const { currentPageKey, currentPath, messageTokens, order } = options;
  const pageKey = _trimNonEmptyString(entry.page_key);
  const path = _trimNonEmptyString(entry.path);
  const haystack = _normalizeRouteText(
    [
      entry.title,
      pageKey,
      path,
      ..._trimBreadcrumb(entry.breadcrumb),
    ].join(' '),
  );

  let score = Math.max(0, 40 - order);
  if (pageKey && pageKey === currentPageKey) {
    score += 400;
  }
  if (path && path === currentPath) {
    score += 360;
  }
  for (const token of messageTokens) {
    if (!token || !haystack.includes(token)) {
      continue;
    }
    score += 120;
  }
  return score;
}

function _selectRouteNavigationCatalog(
  message: string,
  pageContext: PageContext,
): Array<{
  breadcrumb: string[];
  page_key: string;
  path: string;
  title: string;
}> {
  const pageData = pageContext.page_data;
  if (!pageData?.navigation_catalog?.length) {
    return [];
  }

  const currentPageKey =
    _trimNonEmptyString(pageData.navigation_context?.page_key) ??
    _trimNonEmptyString(pageContext.page_key);
  const currentPath = _trimNonEmptyString(pageData.navigation_context?.path);
  const messageTokens = _routeMessageTokens(message);

  return pageData.navigation_catalog
    .map((entry, index) => ({
      entry,
      score: _scoreRouteNavigationEntry(entry, {
        currentPageKey,
        currentPath,
        messageTokens,
        order: index,
      }),
    }))
    .sort((left, right) => right.score - left.score)
    .slice(0, ROUTE_PAGE_CONTEXT_NAV_LIMIT)
    .map(({ entry }) => ({
      breadcrumb: _trimBreadcrumb(entry.breadcrumb),
      page_key: entry.page_key,
      path: entry.path,
      title: entry.title,
    }));
}

function buildRouteRequestPageContext(
  message: string,
  pageContext?: null | PageContext,
): null | PageContext {
  if (!pageContext) {
    return null;
  }

  const pageData = pageContext.page_data;
  const trimmedSurfaceStack = pageContext.surface_stack?.slice(
    0,
    ROUTE_PAGE_CONTEXT_SURFACE_LIMIT,
  );
  const trimmedActiveFormSummary = pageContext.active_form_summary
    ? {
        can_submit: pageContext.active_form_summary.can_submit,
        entity_name: pageContext.active_form_summary.entity_name,
        form_session_id: pageContext.active_form_summary.form_session_id,
        mode: pageContext.active_form_summary.mode,
        remaining_required_fields:
          pageContext.active_form_summary.remaining_required_fields?.slice(
            0,
            ROUTE_PAGE_CONTEXT_REQUIRED_FIELD_LIMIT,
          ),
        stage: pageContext.active_form_summary.stage,
        submit_policy: pageContext.active_form_summary.submit_policy,
      }
    : undefined;
  const trimmedNavigationCatalog = _selectRouteNavigationCatalog(
    message,
    pageContext,
  );

  return {
    active_form_session_id: pageContext.active_form_session_id,
    ...(trimmedActiveFormSummary
      ? {
          active_form_summary: trimmedActiveFormSummary,
        }
      : {}),
    active_surface_id: pageContext.active_surface_id,
    locale: pageContext.locale,
    ...(pageData
      ? {
          page_data: {
            ...(pageData.navigation_context
              ? {
                  navigation_context: {
                    breadcrumb: _trimBreadcrumb(
                      pageData.navigation_context.breadcrumb,
                    ),
                    endpoint: pageData.navigation_context.endpoint,
                    page_key: pageData.navigation_context.page_key,
                    path: pageData.navigation_context.path,
                  },
                }
              : {}),
            ...(trimmedNavigationCatalog.length > 0
              ? {
                  navigation_catalog: trimmedNavigationCatalog,
                }
              : {}),
          },
        }
      : {}),
    page_key: pageContext.page_key,
    page_session_id: pageContext.page_session_id,
    page_title: pageContext.page_title,
    ...(trimmedSurfaceStack?.length
      ? {
          surface_stack: trimmedSurfaceStack,
        }
      : {}),
    ui_epoch: pageContext.ui_epoch,
  };
}

/** Simple string hash for cache key (djb2) / 简单字符串哈希用于缓存 key */
function _simpleHash(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h) ^ (s.codePointAt(i) ?? 0);
  }
  return (h >>> 0).toString(36);
}

export function buildRouteCachePageDataFingerprint(
  pageContext?: null | PageContext,
): string {
  if (!pageContext) {
    return '';
  }

  const thinContext: Record<string, unknown> = {
    page_key: pageContext.page_key,
  };
  const uiEpoch = (pageContext as unknown as Record<string, unknown>).ui_epoch;
  if (typeof uiEpoch === 'number') {
    thinContext.ui_epoch = uiEpoch;
  }
  const activeSurfaceId = (pageContext as unknown as Record<string, unknown>)
    .active_surface_id;
  if (typeof activeSurfaceId === 'string' && activeSurfaceId) {
    thinContext.active_surface_id = activeSurfaceId;
  }
  const activeFormSessionId = (
    pageContext as unknown as Record<string, unknown>
  ).active_form_session_id;
  if (typeof activeFormSessionId === 'string' && activeFormSessionId) {
    thinContext.active_form_session_id = activeFormSessionId;
  }
  const surfaceStack = (pageContext as unknown as Record<string, unknown>)
    .surface_stack;
  if (Array.isArray(surfaceStack) && surfaceStack.length > 0) {
    thinContext.surface_stack = surfaceStack.slice(0, 4).map((item) => {
      if (!item || typeof item !== 'object') {
        return item;
      }
      const surface = item as Record<string, unknown>;
      return {
        kind: surface.kind,
        surface_id: surface.surface_id,
        title: surface.title,
      };
    });
  }
  const activeFormSummary = (pageContext as unknown as Record<string, unknown>)
    .active_form_summary;
  if (activeFormSummary && typeof activeFormSummary === 'object') {
    const summary = activeFormSummary as Record<string, unknown>;
    thinContext.active_form_summary = {
      can_submit: summary.can_submit,
      entity_name: summary.entity_name,
      mode: summary.mode,
      stage: summary.stage,
    };
  }
  const pageData = (pageContext as unknown as Record<string, unknown>).page_data;
  if (pageData && typeof pageData === 'object') {
    const navigationContext = (
      pageData as Record<string, unknown>
    ).navigation_context;
    if (navigationContext && typeof navigationContext === 'object') {
      const context = navigationContext as Record<string, unknown>;
      thinContext.navigation_context = {
        breadcrumb: Array.isArray(context.breadcrumb)
          ? context.breadcrumb.slice(0, 4)
          : [],
        page_key: context.page_key,
        path: context.path,
      };
    }
    const navigationCatalog = (
      pageData as Record<string, unknown>
    ).navigation_catalog;
    if (Array.isArray(navigationCatalog) && navigationCatalog.length > 0) {
      thinContext.navigation_catalog = navigationCatalog.slice(0, 8).map((item) => {
        if (!item || typeof item !== 'object') {
          return item;
        }
        const entry = item as Record<string, unknown>;
        return {
          page_key: entry.page_key,
          path: entry.path,
          title: entry.title,
        };
      });
    }
  }

  return _simpleHash(JSON.stringify(thinContext));
}

/** Routing method constants / 路由方式常量 */
export const ROUTED_BY = {
  DEFAULT: 'default',
  PINNED: 'pinned',
  ROUTER: 'router',
} as const;

/** Frontend routing result / 前端路由结果 */
export interface RouteResult {
  agentId: number;
  agentName: string;
  confidence: number;
  routedBy: string;
}

export interface RouteAttachmentFlags {
  hasAudioAttachments?: boolean;
  hasFileAttachments?: boolean;
  hasImageAttachments?: boolean;
  hasVideoAttachments?: boolean;
}

export interface UseAgentRouterOptions {
  /** API prefix / API 前缀 */
  apiPrefix: Ref<string> | string;
  /** Available agents list / 可用智能体列表 */
  agents: Ref<AgentItem[]>;
  /** Pinned agent ID / 固定的智能体 ID */
  pinnedAgentId: Ref<null | number>;
  /** Pinned agent name / 固定的智能体名称 */
  pinnedAgentName: Ref<null | string>;
  /** Active conversation ID / 活跃对话 ID */
  activeConversationId?: Ref<null | number>;
}

export function useAgentRouter(options: UseAgentRouterOptions) {
  const routing = ref(false);
  const lastRouteResult = ref<null | RouteResult>(null);
  /** Route cache: key = pageKey-convId, force_reroute requests bypass cache / 路由缓存，force_reroute 时跳过 */
  const routeCache = new Map<
    string,
    { expiresAt: number; result: RouteResult }
  >();

  function clearRouteCache() {
    routeCache.clear();
  }

  if (options.activeConversationId) {
    watch(options.activeConversationId, () => clearRouteCache());
  }

  /**
   * Execute P1-P3 routing chain
   * 执行 P1-P3 路由链
   *
   * @param message - User message / 用户消息
   * @param pageContextKey - Optional page context key / 可选页面上下文 key
   * @returns Routing result / 路由结果
   */
  async function routeMessage(
    message: string,
    pageContextKey?: string,
    pageContext?: null | PageContext,
    attachmentFlags?: RouteAttachmentFlags,
    forceReroute = false,
  ): Promise<RouteResult> {
    routing.value = true;
    lastRouteResult.value = null;

    try {
      const result = await _executeRouteChain(
        message,
        pageContextKey,
        pageContext,
        attachmentFlags,
        forceReroute,
      );
      lastRouteResult.value = result;
      return result;
    } finally {
      routing.value = false;
    }
  }

  async function _executeRouteChain(
    message: string,
    pageContextKey?: string,
    pageContext?: null | PageContext,
    attachmentFlags?: RouteAttachmentFlags,
    forceReroute = false,
  ): Promise<RouteResult> {
    const pinId = unref(options.pinnedAgentId);
    const pinName = unref(options.pinnedAgentName);

    // ---- P1: Pinned agent / P1：已固定智能体 ----
    if (pinId && pinName) {
      return {
        agentId: pinId,
        agentName: pinName,
        confidence: 1,
        routedBy: ROUTED_BY.PINNED,
      };
    }

    // ---- P2+P3: Backend routing (with fallback) / 后端路由（含 fallback） ----
    const pageCtx = pageContext ?? getRuntimeThinPageContext(pageContextKey);
    return await _callRouteApi(
      message,
      pageContextKey,
      pageCtx,
      attachmentFlags,
      forceReroute,
    );
  }

  /**
   * P2+P3: Call backend /route API (with cache)
   * Backend handles Router agent invocation and default_chat fallback.
   * Cache key includes message hash + page context to avoid wrong agent reuse.
   * 缓存 key 纳入消息哈希和页面上下文，避免不同问题错误复用同一 agent。
   */
  async function _callRouteApi(
    message: string,
    pageContextKey: string | undefined,
    pageContext: null | PageContext,
    attachmentFlags?: RouteAttachmentFlags,
    forceReroute = false,
  ): Promise<RouteResult> {
    const normalizedAttachmentFlags = {
      hasAudioAttachments: Boolean(attachmentFlags?.hasAudioAttachments),
      hasFileAttachments: Boolean(attachmentFlags?.hasFileAttachments),
      hasImageAttachments: Boolean(attachmentFlags?.hasImageAttachments),
      hasVideoAttachments: Boolean(attachmentFlags?.hasVideoAttachments),
    };
    const convId = options.activeConversationId
      ? unref(options.activeConversationId)
      : null;
    const pageKey = pageContextKey ?? pageContext?.page_key ?? 'global';
    const pageDataHash = buildRouteCachePageDataFingerprint(pageContext);
    const msgHash = _simpleHash(message.trim().slice(0, 200));
    const attachmentKey = [
      `img${normalizedAttachmentFlags.hasImageAttachments ? '1' : '0'}`,
      `aud${normalizedAttachmentFlags.hasAudioAttachments ? '1' : '0'}`,
      `vid${normalizedAttachmentFlags.hasVideoAttachments ? '1' : '0'}`,
      `file${normalizedAttachmentFlags.hasFileAttachments ? '1' : '0'}`,
    ].join('-');
    const cacheKey = `${pageKey}-${convId ?? 'new'}-${msgHash}-${pageDataHash}-${attachmentKey}`;

    const now = Date.now();
    if (!forceReroute) {
      const cached = routeCache.get(cacheKey);
      if (cached && cached.expiresAt > now) {
        return cached.result;
      }
    }

    const prefix = unref(options.apiPrefix);
    const pinId = unref(options.pinnedAgentId);
    const routePageContext = buildRouteRequestPageContext(message, pageContext);

    const response: AgentRouteResponse = await routeMessageApi(prefix, {
      message,
      conversation_id: convId,
      page_context: routePageContext,
      pinned_agent_id: pinId,
      force_reroute: forceReroute,
      has_image_attachments: normalizedAttachmentFlags.hasImageAttachments,
      has_audio_attachments: normalizedAttachmentFlags.hasAudioAttachments,
      has_video_attachments: normalizedAttachmentFlags.hasVideoAttachments,
      has_file_attachments: normalizedAttachmentFlags.hasFileAttachments,
    });

    const result: RouteResult = {
      agentId: response.agent_id,
      agentName: response.agent_name,
      confidence: response.confidence,
      routedBy: response.routed_by,
    };
    if (!forceReroute) {
      routeCache.set(cacheKey, {
        result,
        expiresAt: now + ROUTE_CACHE_TTL_MS,
      });
    }
    return result;
  }

  return {
    /** Whether routing is in progress / 是否正在路由中 */
    routing,
    /** Last routing result / 最近一次路由结果 */
    lastRouteResult,
    /** Execute routing / 执行路由 */
    routeMessage,
  };
}
