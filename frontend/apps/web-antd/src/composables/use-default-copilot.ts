/**
 * Default Copilot composable / 默认 Copilot 组合式函数
 *
 * Resolves and caches the default Copilot agent ID based on the current API prefix.
 * Admin endpoint → admin_copilot; Tenant endpoint → tenant_copilot.
 * 根据当前 API 前缀解析并缓存默认 Copilot 智能体 ID。
 */
import type { ComputedRef } from 'vue';

import { ref, watch } from 'vue';

import { resolveDefaultCopilotApi } from '#/api/shared/ai-chat';

/** Feature code constants / 功能代码常量 */
const FEATURE_CODE_ADMIN = 'admin_copilot';
const FEATURE_CODE_TENANT = 'tenant_copilot';

function resolveFeatureCode(apiPrefix: string): string {
  return apiPrefix === '/admin' ? FEATURE_CODE_ADMIN : FEATURE_CODE_TENANT;
}

export function useDefaultCopilot(apiPrefix: ComputedRef<string> | string) {
  const defaultCopilotAgentId = ref<null | number>(null);
  const defaultCopilotAgentName = ref<null | string>(null);
  const resolving = ref(false);

  async function resolveDefaultCopilot(): Promise<void> {
    const prefix = typeof apiPrefix === 'string' ? apiPrefix : apiPrefix.value;
    const featureCode = resolveFeatureCode(prefix);

    resolving.value = true;
    try {
      const result = await resolveDefaultCopilotApi(prefix, featureCode);
      if (result?.is_active && result.agent_id) {
        defaultCopilotAgentId.value = result.agent_id;
        defaultCopilotAgentName.value = result.agent_name;
      } else {
        defaultCopilotAgentId.value = null;
        defaultCopilotAgentName.value = null;
      }
    } catch {
      // Silently fail — fallback to existing behavior (first agent in list)
      // 静默失败 — 回退至现有行为（列表首个智能体）
      defaultCopilotAgentId.value = null;
      defaultCopilotAgentName.value = null;
    } finally {
      resolving.value = false;
    }
  }

  // Clear cache when apiPrefix changes / API 前缀变化时清除缓存
  watch(
    () => (typeof apiPrefix === 'string' ? apiPrefix : apiPrefix.value),
    () => {
      defaultCopilotAgentId.value = null;
      defaultCopilotAgentName.value = null;
      void resolveDefaultCopilot();
    },
    { immediate: true },
  );

  return {
    /** Resolved default Copilot agent ID / 已解析的默认 Copilot 智能体 ID */
    defaultCopilotAgentId,
    /** Resolved default Copilot agent name / 已解析的默认 Copilot 智能体名称 */
    defaultCopilotAgentName,
    /** Whether resolving is in progress / 是否正在解析中 */
    resolving,
    /** Re-resolve the default Copilot / 重新解析默认 Copilot */
    resolveDefaultCopilot,
  };
}
