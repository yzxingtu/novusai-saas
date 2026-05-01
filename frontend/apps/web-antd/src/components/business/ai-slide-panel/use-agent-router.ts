import type { Ref } from 'vue';

import type { AgentRouteResponse } from '#/api/shared/ai-chat';
import type { AgentItem } from '#/types/ai-chat';

import { ref, unref, watch } from 'vue';

import { routeMessageApi } from '#/api/shared/ai-chat';

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

  async function routeMessage(
    message: string,
    attachmentFlags?: RouteAttachmentFlags,
    forceReroute = false,
  ): Promise<RouteResult> {
    routing.value = true;
    lastRouteResult.value = null;

    try {
      const result = await _executeRouteChain(
        message,
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
    attachmentFlags?: RouteAttachmentFlags,
    forceReroute = false,
  ): Promise<RouteResult> {
    const pinId = unref(options.pinnedAgentId);
    const pinName = unref(options.pinnedAgentName);

    if (pinId && pinName) {
      return {
        agentId: pinId,
        agentName: pinName,
        confidence: 1,
        routedBy: ROUTED_BY.PINNED,
      };
    }

    return await _callRouteApi(
      message,
      attachmentFlags,
      forceReroute,
    );
  }

  async function _callRouteApi(
    message: string,
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
    const msgHash = _simpleHash(message.trim().slice(0, 200));
    const attachmentKey = [
      `img${normalizedAttachmentFlags.hasImageAttachments ? '1' : '0'}`,
      `aud${normalizedAttachmentFlags.hasAudioAttachments ? '1' : '0'}`,
      `vid${normalizedAttachmentFlags.hasVideoAttachments ? '1' : '0'}`,
      `file${normalizedAttachmentFlags.hasFileAttachments ? '1' : '0'}`,
    ].join('-');
    const cacheKey = `global-${convId ?? 'new'}-${msgHash}-${attachmentKey}`;

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
