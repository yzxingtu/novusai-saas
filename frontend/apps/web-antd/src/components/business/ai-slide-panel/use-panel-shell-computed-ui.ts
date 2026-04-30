import type { Ref } from 'vue';

import { computed } from 'vue';

import { $t } from '#/locales';

type ChatAcceptAttribute = string | { value: string };

interface UsePanelShellComputedUIOptions {
  agentKBBindings: Ref<unknown[]>;
  agentsLoading: Ref<boolean>;
  chatAcceptAttribute: ChatAcceptAttribute;
  mentionCandidates: Ref<unknown[]>;
}

export function usePanelShellComputedUI(
  options: UsePanelShellComputedUIOptions,
) {
  const resolvedAttachmentAccept = computed(() =>
    typeof options.chatAcceptAttribute === 'string'
      ? options.chatAcceptAttribute
      : options.chatAcceptAttribute.value,
  );

  const mentionEmptyHint = computed(() =>
    options.mentionCandidates.value.length === 0 &&
    options.agentKBBindings.value.length === 0 &&
    !options.agentsLoading.value
      ? $t('common.globalAiChat.mentionKbNoneBound')
      : $t('common.globalAiChat.mentionAgentEmpty'),
  );

  return {
    mentionEmptyHint,
    resolvedAttachmentAccept,
  };
}
