/**
 * Agent Router Composable
 * 智能体路由 Composable
 *
 * Implements P1-P4 routing priority chain:
 * P1: pinnedAgentId direct pass-through (user manually pinned)
 * P2: @agent_name mention exact match
 * P3: Call /route API (with page_context), backend Router agent AI selection
 * P4: Backend fallback to default_chat
 * 实现 P1-P4 路由优先级链：
 * P1: pinnedAgentId 直通（用户手动固定）
 * P2: @agent_name mention 精确匹配
 * P3: 调用 /route API（含 page_context），后端 Router 智能体 AI 选择
 * P4: 后端 fallback 到 default_chat
 *
 * P3+P4 are combined into a single API call; backend handles degradation.
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

/** Routing method constants / 路由方式常量 */
export const ROUTED_BY = {
  DEFAULT: 'default',
  MENTION: 'mention',
  PINNED: 'pinned',
  ROUTER: 'router',
} as const;

/** Frontend routing result / 前端路由结果 */
export interface RouteResult {
  agentId: number;
  agentName: string;
  confidence: number;
  routedBy: string;
  /** Message with @mention prefix stripped (only set when routedBy='mention') */
  cleanedMessage?: string;
}

export interface UseAgentRouterOptions {
  /** API prefix / API 前缀 */
  apiPrefix: Ref<string> | string;
  /** Available agents list (for P2 @mention matching) / 可用智能体列表（用于 P2 @mention 匹配） */
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

  /**
   * Execute P1-P4 routing chain
   * 执行 P1-P4 路由链
   *
   * @param message - User message / 用户消息
   * @param pageContextKey - Optional page context registry key / 可选的页面上下文 registry key
   * @returns Routing result / 路由结果
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

    // ---- P2: @mention exact match / @mention 精确匹配 ----
    const mentionResult = _tryMentionMatch(message);
    if (mentionResult) {
      return mentionResult;
    }

    // ---- P3+P4: Backend routing (with fallback) / 后端路由（含 fallback） ----
    const pageCtx = pageContext ?? resolvePageContext(pageContextKey);
    return await _callRouteApi(message, pageCtx);
  }

  /**
   * P2: Parse @agent_name mention
   * Match rule: message starts with @name (case-insensitive),
   * name must exactly match an agent in the local agents list.
   * P2: 解析 @agent_name mention
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

    // Extract text after @ (up to space or newline) / 提取 @ 后的文本（到空格或换行为止）
    const mentionMatch = /^@(\S+)/.exec(trimmed);
    if (!mentionMatch) {
      return null;
    }

    const mentionName = mentionMatch[1]!.toLowerCase();

    // Exact match (case-insensitive) / 精确匹配（忽略大小写）
    const matched = agentList.find(
      (a) => a.name.toLowerCase() === mentionName,
    );

    if (matched) {
      // Strip @name prefix from message so LLM doesn't receive it
      const cleaned = trimmed.slice(mentionMatch[0]!.length).trimStart();
      return {
        agentId: matched.id,
        agentName: matched.name,
        confidence: 1.0,
        routedBy: ROUTED_BY.MENTION,
        cleanedMessage: cleaned || undefined,
      };
    }

    return null;
  }

  /**
   * P3+P4: Call backend /route API
   * Backend handles Router agent invocation and default_chat fallback.
   * P3+P4: 调用后端 /route API
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
    /** Whether routing is in progress / 是否正在路由中 */
    routing,
    /** Last routing result / 最近一次路由结果 */
    lastRouteResult,
    /** Execute routing / 执行路由 */
    routeMessage,
  };
}
