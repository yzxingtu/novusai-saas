import type { AgentAssignmentResolveResult } from '#/api/shared/agent-assignments';

import { computed, onMounted, ref } from 'vue';

import { resolveAgentAssignmentApi } from '#/api/shared/agent-assignments';

import { RICH_TEXT_AI_FEATURE_CODE } from './types';

export type RichTextAiAssignmentStatus =
  | 'active_assigned'
  | 'inactive'
  | 'unassigned'
  | 'unresolved';

export interface UseRichTextAiAssignmentOptions {
  apiPrefix?: string;
  immediate?: boolean;
}

export function getRichTextAiAssignmentStatus(
  assignment: AgentAssignmentResolveResult | null,
): RichTextAiAssignmentStatus {
  if (!assignment) {
    return 'unresolved';
  }
  if (!assignment.is_active) {
    return 'inactive';
  }
  if (!assignment.agent_id) {
    return 'unassigned';
  }
  return 'active_assigned';
}

export function useRichTextAiAssignment(
  options: UseRichTextAiAssignmentOptions = {},
) {
  const apiPrefix = options.apiPrefix ?? '/admin';
  const assignment = ref<AgentAssignmentResolveResult | null>(null);
  const loading = ref(false);

  const status = computed(() =>
    getRichTextAiAssignmentStatus(assignment.value),
  );
  const assignedAgentName = computed(
    () => assignment.value?.agent_name ?? null,
  );
  const assignedAgentId = computed(() => assignment.value?.agent_id ?? null);
  const resolvedFeatureCode = computed(
    () => assignment.value?.feature_code ?? RICH_TEXT_AI_FEATURE_CODE,
  );

  async function loadAssignment() {
    loading.value = true;
    assignment.value = null;

    try {
      assignment.value = await resolveAgentAssignmentApi(
        apiPrefix,
        RICH_TEXT_AI_FEATURE_CODE,
      );
    } catch {
      assignment.value = null;
    } finally {
      loading.value = false;
    }
  }

  if (options.immediate !== false) {
    onMounted(() => {
      void loadAssignment();
    });
  }

  return {
    assignedAgentId,
    assignedAgentName,
    assignment,
    featureCode: RICH_TEXT_AI_FEATURE_CODE,
    loadAssignment,
    loading,
    resolvedFeatureCode,
    status,
  };
}
