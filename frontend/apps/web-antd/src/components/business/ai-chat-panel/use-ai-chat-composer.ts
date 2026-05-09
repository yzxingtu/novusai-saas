import type { Ref } from 'vue';

import type { AgentSkillBindingSummary, MentionCandidate } from './types';
import type { UseAIChatOptions } from './use-ai-chat-options';

import type {
  ChatKBBindingInfo,
  ChatSkillBindingInfo,
} from '#/api/shared/ai-chat';

import { computed, ref, unref, watch } from 'vue';

import {
  getChatAgentKBBindingsApi,
  getChatAgentSkillsApi,
} from '#/api/shared/ai-chat';

import {
  extractLeadingAgentMentionDraft,
  filterKnowledgeBasesByMentionQuery,
  filterSkillPackagesByMentionQuery,
} from './chat-input-utils';

interface UseAIChatComposerDeps {
  options: UseAIChatOptions;
  selectedAgentId: Ref<null | number>;
}

export function useAIChatComposer(deps: UseAIChatComposerDeps) {
  const { options, selectedAgentId } = deps;

  const inputMessage = ref('');
  const mentionQuery = ref('');
  const mentionActiveIndex = ref(0);
  const selectedKBIds = ref<number[]>([]);
  const agentKBBindings = ref<ChatKBBindingInfo[]>([]);
  const agentKBBindingsByAgentId = ref<Record<number, ChatKBBindingInfo[]>>({});
  const agentSkillBindingsByAgentId = ref<
    Record<number, AgentSkillBindingSummary[]>
  >({});
  const pendingAgentKBBindingLoads = new Map<
    number,
    Promise<ChatKBBindingInfo[]>
  >();
  const pendingAgentSkillBindingLoads = new Map<
    number,
    Promise<AgentSkillBindingSummary[]>
  >();
  let endpointGeneration = 0;

  function skillPackageSelectionValue(
    binding: Pick<AgentSkillBindingSummary, 'package_name' | 'skill_name'>,
  ): string {
    return String(binding.package_name || binding.skill_name || '').trim();
  }

  function currentAgentSkillBindings(): AgentSkillBindingSummary[] {
    const agentId = selectedAgentId.value;
    if (typeof agentId !== 'number' || !Number.isFinite(agentId)) {
      return [];
    }
    return agentSkillBindingsByAgentId.value[agentId] ?? [];
  }

  function currentMentionSkillPackages(): AgentSkillBindingSummary[] {
    const seen = new Set<string>();
    const out: AgentSkillBindingSummary[] = [];
    for (const binding of currentAgentSkillBindings()) {
      const skillId = Number(binding.skill_id);
      if (!Number.isFinite(skillId)) {
        continue;
      }
      const value = skillPackageSelectionValue(binding);
      if (!value) {
        continue;
      }
      const key =
        binding.package_id === null || binding.package_id === undefined
          ? `skill:${skillId}`
          : `package:${binding.package_id}`;
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      out.push(binding);
    }
    return out;
  }

  /** @ 候选：当前智能体已绑定知识库与技能包 / KBs and skill packages bound to the current agent */
  const mentionCandidates = computed<MentionCandidate[]>(() => {
    const draft = extractLeadingAgentMentionDraft(inputMessage.value);
    if (draft === null) {
      return [];
    }
    const kbMatches = filterKnowledgeBasesByMentionQuery(
      agentKBBindings.value,
      draft,
    );
    const out: MentionCandidate[] = [];
    for (const binding of kbMatches) {
      out.push({ kind: 'knowledge_base', binding });
    }
    const skillMatches = filterSkillPackagesByMentionQuery(
      currentMentionSkillPackages()
        .filter((binding) => Number.isFinite(Number(binding.skill_id)))
        .map((binding) => ({
          package_id: binding.package_id ?? null,
          package_name: binding.package_name ?? null,
          skill_id: Number(binding.skill_id),
          skill_name: binding.skill_name ?? binding.name ?? null,
        })),
      draft,
    );
    for (const binding of skillMatches) {
      out.push({ kind: 'skill_package', binding });
    }
    return out;
  });
  const mentionOpen = computed(
    () => extractLeadingAgentMentionDraft(inputMessage.value) !== null,
  );

  watch(inputMessage, (value) => {
    const draft = extractLeadingAgentMentionDraft(value);
    if (draft === null) {
      mentionQuery.value = '';
      mentionActiveIndex.value = 0;
      return;
    }
    mentionQuery.value = draft;
  });

  watch(mentionCandidates, (candidates) => {
    if (candidates.length === 0) {
      mentionActiveIndex.value = 0;
      return;
    }
    if (mentionActiveIndex.value >= candidates.length) {
      mentionActiveIndex.value = candidates.length - 1;
    }
  });

  function selectMentionKnowledgeBase(
    binding: Pick<ChatKBBindingInfo, 'knowledge_base_id'>,
  ) {
    const id = binding.knowledge_base_id;
    if (!selectedKBIds.value.includes(id)) {
      selectedKBIds.value = [...selectedKBIds.value, id];
    }
    mentionQuery.value = '';
    mentionActiveIndex.value = 0;
    inputMessage.value = '';
  }

  function selectMentionSkillPackage(
    binding: Pick<AgentSkillBindingSummary, 'package_name' | 'skill_name'>,
  ) {
    const value = skillPackageSelectionValue(binding);
    mentionQuery.value = '';
    mentionActiveIndex.value = 0;
    inputMessage.value = value ? `@${value} ` : '';
  }

  function removeSelectedKnowledgeBase(knowledgeBaseId: number) {
    selectedKBIds.value = selectedKBIds.value.filter(
      (k) => k !== knowledgeBaseId,
    );
  }

  function resetComposerEndpointState() {
    endpointGeneration += 1;
    pendingAgentKBBindingLoads.clear();
    pendingAgentSkillBindingLoads.clear();
    inputMessage.value = '';
    mentionQuery.value = '';
    mentionActiveIndex.value = 0;
    selectedKBIds.value = [];
    agentKBBindings.value = [];
    agentKBBindingsByAgentId.value = {};
    agentSkillBindingsByAgentId.value = {};
  }

  function clearMentionDraft() {
    mentionQuery.value = '';
    mentionActiveIndex.value = 0;
  }

  function updateAgentKBBindings(
    agentId: number,
    items: ChatKBBindingInfo[],
  ): ChatKBBindingInfo[] {
    agentKBBindingsByAgentId.value = {
      ...agentKBBindingsByAgentId.value,
      [agentId]: items,
    };
    if (selectedAgentId.value === agentId) {
      agentKBBindings.value = items;
    }
    return items;
  }

  function getAgentKBBindings(agentId: null | number | undefined) {
    if (typeof agentId !== 'number' || !Number.isFinite(agentId)) {
      return null;
    }
    return agentKBBindingsByAgentId.value[agentId] ?? null;
  }

  function updateAgentSkillBindings(
    agentId: number,
    items: AgentSkillBindingSummary[],
  ): AgentSkillBindingSummary[] {
    agentSkillBindingsByAgentId.value = {
      ...agentSkillBindingsByAgentId.value,
      [agentId]: items,
    };
    return items;
  }

  function normalizeAgentSkillBinding(
    binding: ChatSkillBindingInfo,
  ): AgentSkillBindingSummary {
    return {
      enabled: binding.enabled,
      id: binding.id ?? undefined,
      name: binding.skill_name ?? undefined,
      package_id: binding.package_id ?? undefined,
      package_name: binding.package_name ?? undefined,
      skill_id: binding.skill_id ?? undefined,
      skill_key: binding.skill_key ?? undefined,
      skill_name: binding.skill_name ?? undefined,
      type: binding.skill_type ?? undefined,
    };
  }

  function getAgentSkillBindings(agentId: null | number | undefined) {
    if (typeof agentId !== 'number' || !Number.isFinite(agentId)) {
      return null;
    }
    return agentSkillBindingsByAgentId.value[agentId] ?? null;
  }

  async function loadAgentKBBindings(agentId: number) {
    const cached = getAgentKBBindings(agentId);
    if (cached) {
      if (selectedAgentId.value === agentId) {
        agentKBBindings.value = cached;
      }
      return cached;
    }

    const pending = pendingAgentKBBindingLoads.get(agentId);
    if (pending) {
      return pending;
    }
    const generation = endpointGeneration;

    const request = (async () => {
      try {
        const prefix = unref(options.apiPrefix) as string;
        const items = await getChatAgentKBBindingsApi(prefix, agentId);
        if (generation !== endpointGeneration) {
          return [];
        }
        return updateAgentKBBindings(
          agentId,
          items.filter((binding) => binding.enabled),
        );
      } catch {
        if (generation !== endpointGeneration) {
          return [];
        }
        return updateAgentKBBindings(agentId, []);
      } finally {
        pendingAgentKBBindingLoads.delete(agentId);
      }
    })();

    pendingAgentKBBindingLoads.set(agentId, request);
    return request;
  }

  async function loadAgentSkillBindings(agentId: number) {
    const cached = getAgentSkillBindings(agentId);
    if (cached) {
      return cached;
    }

    const pending = pendingAgentSkillBindingLoads.get(agentId);
    if (pending) {
      return pending;
    }
    const generation = endpointGeneration;

    const request = (async () => {
      try {
        const prefix = unref(options.apiPrefix) as string;
        const items = await getChatAgentSkillsApi(prefix, agentId);
        if (generation !== endpointGeneration) {
          return [];
        }
        return updateAgentSkillBindings(
          agentId,
          items
            .filter((binding) => binding.enabled !== false)
            .map((binding) => normalizeAgentSkillBinding(binding)),
        );
      } catch {
        if (generation !== endpointGeneration) {
          return [];
        }
        return updateAgentSkillBindings(agentId, []);
      } finally {
        pendingAgentSkillBindingLoads.delete(agentId);
      }
    })();

    pendingAgentSkillBindingLoads.set(agentId, request);
    return request;
  }

  /**
   * KB 绑定随当前选中智能体加载。
   * Bindings follow the currently selected agent.
   */
  const effectiveKbAgentId = computed(() => selectedAgentId.value ?? null);

  watch(
    effectiveKbAgentId,
    async (id) => {
      if (!id) {
        agentKBBindings.value = [];
        return;
      }
      await loadAgentKBBindings(id);
      void loadAgentSkillBindings(id);
      const allowed = new Set(
        agentKBBindings.value.map((b) => b.knowledge_base_id),
      );
      selectedKBIds.value = selectedKBIds.value.filter((kid) =>
        allowed.has(kid),
      );
    },
    { immediate: true },
  );

  function handleInputKeyDown(e: KeyboardEvent): boolean {
    if (!mentionOpen.value) {
      return false;
    }
    const candidates = mentionCandidates.value;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (candidates.length > 0) {
        mentionActiveIndex.value =
          (mentionActiveIndex.value + 1) % candidates.length;
      }
      return true;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (candidates.length > 0) {
        mentionActiveIndex.value =
          (mentionActiveIndex.value - 1 + candidates.length) %
          candidates.length;
      }
      return true;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      inputMessage.value = '';
      clearMentionDraft();
      return true;
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      const target = candidates[mentionActiveIndex.value] ?? candidates[0];
      if (target?.kind === 'knowledge_base') {
        selectMentionKnowledgeBase(target.binding as ChatKBBindingInfo);
      } else if (target?.kind === 'skill_package') {
        selectMentionSkillPackage(target.binding);
      }
      return true;
    }
    return false;
  }

  return {
    agentKBBindings,
    agentKBBindingsByAgentId,
    agentSkillBindingsByAgentId,
    clearMentionDraft,
    getAgentKBBindings,
    getAgentSkillBindings,
    handleInputKeyDown,
    inputMessage,
    loadAgentKBBindings,
    loadAgentSkillBindings,
    mentionActiveIndex,
    mentionCandidates,
    mentionOpen,
    removeSelectedKnowledgeBase,
    resetComposerEndpointState,
    selectMentionKnowledgeBase,
    selectMentionSkillPackage,
    selectedKBIds,
  };
}
