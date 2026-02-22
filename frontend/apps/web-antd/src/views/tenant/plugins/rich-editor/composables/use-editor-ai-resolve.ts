/**
 * useEditorAIResolve 组合式函数
 *
 * 通过 resolve API 获取当前租户绑定的 AI 智能体信息。
 * 与 useEditorConfig 的 ai_enabled 开关配合：
 * - ai_enabled=false → 不调 resolve，直接隐藏 AI UI
 * - ai_enabled=true 但 resolve 返回 is_active=false → 显示「未配置」提示
 * - ai_enabled=true 且 resolve 成功 → 正常使用 AI
 */
import { ref } from 'vue';

import { requestClient } from '#/utils/request';

/** Resolve API 响应 */
export interface AIResolveResult {
  feature_code: string;
  agent_id: number | null;
  agent_name: string | null;
  config: Record<string, unknown> | null;
  is_active: boolean;
  is_override?: boolean;
}

/** AI 就绪状态 */
export type AIReadyState =
  | 'disabled'       // 插件配置关闭了 AI
  | 'not_configured' // AI 开启但未绑定智能体
  | 'ready'          // AI 就绪可用
  | 'loading';       // 正在加载

const FEATURE_CODE = 'rich_editor';

export function useEditorAIResolve() {
  const resolveResult = ref<AIResolveResult | null>(null);
  const resolveLoading = ref(false);
  const resolveError = ref<string | null>(null);

  /** AI 就绪状态 */
  const aiReadyState = ref<AIReadyState>('loading');
  /** 解析出的 agentId */
  const resolvedAgentId = ref<number | null>(null);
  /** 解析出的 agent 名称 */
  const resolvedAgentName = ref<string | null>(null);

  /**
   * 执行 resolve
   *
   * @param aiEnabled 插件配置中的 ai_enabled 开关
   * @returns AI 就绪状态
   */
  async function resolve(aiEnabled: boolean): Promise<AIReadyState> {
    // 插件配置关闭了 AI → 直接返回
    if (!aiEnabled) {
      aiReadyState.value = 'disabled';
      resolvedAgentId.value = null;
      resolvedAgentName.value = null;
      return 'disabled';
    }

    resolveLoading.value = true;
    resolveError.value = null;

    try {
      const res = await requestClient.get<AIResolveResult>(
        `/tenant/ai/agent-assignments/resolve/${FEATURE_CODE}`,
      );
      resolveResult.value = res;
      resolvedAgentId.value = res.agent_id;
      resolvedAgentName.value = res.agent_name;

      if (!res.is_active || !res.agent_id) {
        aiReadyState.value = 'not_configured';
        return 'not_configured';
      }

      aiReadyState.value = 'ready';
      return 'ready';
    } catch (err: unknown) {
      resolveError.value = (err as Error).message;
      aiReadyState.value = 'not_configured';
      resolvedAgentId.value = null;
      resolvedAgentName.value = null;
      return 'not_configured';
    } finally {
      resolveLoading.value = false;
    }
  }

  return {
    resolveResult,
    resolveLoading,
    resolveError,
    aiReadyState,
    resolvedAgentId,
    resolvedAgentName,
    resolve,
  };
}
