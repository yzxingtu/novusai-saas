import type { Ref } from 'vue';

import type { AgentRouteResponse, PageContext } from '#/api/shared/ai-chat';
import type { AgentItem } from '#/components/business/ai-chat-panel/types';

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

import { resolvePageContext } from './page-context-registry';

const ROUTE_CACHE_TTL_MS = 2 * 60 * 1000;

/** Simple string hash for cache key (djb2) / 简单字符串哈希用于缓存 key */
function _simpleHash(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h) ^ (s.codePointAt(i) ?? 0);
  }
  return (h >>> 0).toString(36);
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
   * @param pageContextKey - Optional page context registry key / 可选的页面上下文 registry key
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
    const pageCtx = pageContext ?? resolvePageContext(pageContextKey);
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
    const pageDataHash = pageContext?.page_data
      ? _simpleHash(JSON.stringify(pageContext.page_data))
      : '';
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

    const response: AgentRouteResponse = await routeMessageApi(prefix, {
      message,
      conversation_id: convId,
      page_context: pageContext,
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
