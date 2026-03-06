/**
 * 智能体路由 Composable
 *
 * 实现 P1-P4 路由优先级链：
 * P1: pinnedAgentId 直通（用户手动固定）
 * P2: @agent_name mention 精确匹配
 * P3: 调用 /route API（含 page_context），后端 Router 智能体 AI 选择
 * P4: 后端 fallback 到 default_chat
 *
 * P3+P4 合并为一次 API 调用，后端自行处理降级。
 */
import { type Ref, ref, unref } from 'vue';

import type {
  AgentRouteResponse,
  PageContext,
} from '#/api/shared/ai-chat';
import type { AgentItem } from '#/components/business/ai-chat-panel/types';

import { routeMessageApi } from '#/api/shared/ai-chat';

import { resolvePageContext } from './page-context-registry';

/** 路由方式常量 */
export const ROUTED_BY = {
  DEFAULT: 'default',
  MENTION: 'mention',
  PINNED: 'pinned',
  ROUTER: 'router',
} as const;

/** 前端路由结果 */
export interface RouteResult {
  agentId: number;
  agentName: string;
  confidence: number;
  routedBy: string;
}

export interface UseAgentRouterOptions {
  /** API 前缀 */
  apiPrefix: Ref<string> | string;
  /** 可用智能体列表（用于 P2 @mention 匹配） */
  agents: Ref<AgentItem[]>;
  /** 固定的智能体 ID */
  pinnedAgentId: Ref<null | number>;
  /** 固定的智能体名称 */
  pinnedAgentName: Ref<null | string>;
  /** 活跃对话 ID */
  activeConversationId?: Ref<null | number>;
}

export function useAgentRouter(options: UseAgentRouterOptions) {
  const routing = ref(false);
  const lastRouteResult = ref<null | RouteResult>(null);

  /**
   * 执行 P1-P4 路由链
   *
   * @param message 用户消息
   * @param pageContextKey 可选的页面上下文 registry key
   * @returns 路由结果
   */
  async function routeMessage(
    message: string,
    pageContextKey?: string,
    pageContext?: null | PageContext,
  ): Promise<RouteResult> {
    routing.value = true;
    lastRouteResult.value = null;

    try {
      const result = await _executeRouteChain(
        message,
        pageContextKey,
        pageContext,
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
  ): Promise<RouteResult> {
    const pinId = unref(options.pinnedAgentId);
    const pinName = unref(options.pinnedAgentName);

    // ---- P1: Pinned agent ----
    if (pinId && pinName) {
      return {
        agentId: pinId,
        agentName: pinName,
        confidence: 1.0,
        routedBy: ROUTED_BY.PINNED,
      };
    }

    // ---- P2: @mention 精确匹配 ----
    const mentionResult = _tryMentionMatch(message);
    if (mentionResult) {
      return mentionResult;
    }

    // ---- P3+P4: 后端路由（含 fallback） ----
    const pageCtx = pageContext ?? resolvePageContext(pageContextKey);
    return await _callRouteApi(message, pageCtx);
  }

  /**
   * P2: 解析 @agent_name mention
   *
   * 匹配规则：消息以 @name 开头（忽略大小写），
   * name 必须在本地 agents 列表中精确匹配。
   */
  function _tryMentionMatch(message: string): null | RouteResult {
    const trimmed = message.trimStart();
    if (!trimmed.startsWith('@')) {
      return null;
    }

    const agentList = unref(options.agents);
    if (agentList.length === 0) {
      return null;
    }

    // 提取 @ 后的文本（到空格或换行为止）
    const mentionMatch = /^@(\S+)/.exec(trimmed);
    if (!mentionMatch) {
      return null;
    }

    const mentionName = mentionMatch[1]!.toLowerCase();

    // 精确匹配（忽略大小写）
    const matched = agentList.find(
      (a) => a.name.toLowerCase() === mentionName,
    );

    if (matched) {
      return {
        agentId: matched.id,
        agentName: matched.name,
        confidence: 1.0,
        routedBy: ROUTED_BY.MENTION,
      };
    }

    return null;
  }

  /**
   * P3+P4: 调用后端 /route API
   *
   * 后端处理 Router 智能体调用和 default_chat fallback。
   */
  async function _callRouteApi(
    message: string,
    pageContext: null | PageContext,
  ): Promise<RouteResult> {
    const prefix = unref(options.apiPrefix);
    const conversationId = options.activeConversationId
      ? unref(options.activeConversationId)
      : null;
    const pinId = unref(options.pinnedAgentId);

    const response: AgentRouteResponse = await routeMessageApi(prefix, {
      message,
      conversation_id: conversationId,
      page_context: pageContext,
      pinned_agent_id: pinId,
    });

    return {
      agentId: response.agent_id,
      agentName: response.agent_name,
      confidence: response.confidence,
      routedBy: response.routed_by,
    };
  }

  return {
    /** 是否正在路由中 */
    routing,
    /** 最近一次路由结果 */
    lastRouteResult,
    /** 执行路由 */
    routeMessage,
  };
}
