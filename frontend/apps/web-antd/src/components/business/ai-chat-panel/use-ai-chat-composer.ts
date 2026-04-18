import type { Ref } from 'vue';

import type { MentionCandidate } from './types';
import type { UseAIChatOptions } from './use-ai-chat-options';

import type { ChatKBBindingInfo } from '#/api/shared/ai-chat';

import { computed, ref, unref, watch } from 'vue';

import { getChatAgentKBBindingsApi } from '#/api/shared/ai-chat';

import {
  extractLeadingAgentMentionDraft,
  filterKnowledgeBasesByMentionQuery,
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

  /** @ 候选：仅当前智能体已绑定知识库 / Only KBs bound to the current agent */
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

  function removeSelectedKnowledgeBase(knowledgeBaseId: number) {
    selectedKBIds.value = selectedKBIds.value.filter(
      (k) => k !== knowledgeBaseId,
    );
  }

  function clearMentionDraft() {
    mentionQuery.value = '';
    mentionActiveIndex.value = 0;
  }

  async function loadAgentKBBindings(agentId: number) {
    try {
      const prefix = unref(options.apiPrefix) as string;
      const items = await getChatAgentKBBindingsApi(prefix, agentId);
      agentKBBindings.value = items.filter((b) => b.enabled);
    } catch {
      agentKBBindings.value = [];
    }
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
      if (target) {
        selectMentionKnowledgeBase(target.binding as ChatKBBindingInfo);
      }
      return true;
    }
    return false;
  }

  return {
    agentKBBindings,
    clearMentionDraft,
    handleInputKeyDown,
    inputMessage,
    loadAgentKBBindings,
    mentionActiveIndex,
    mentionCandidates,
    mentionOpen,
    removeSelectedKnowledgeBase,
    selectMentionKnowledgeBase,
    selectedKBIds,
  };
}
