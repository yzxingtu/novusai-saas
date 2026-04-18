import type { ComputedRef, Ref } from 'vue';

import { computed } from 'vue';

import { $t } from '#/locales';

type ChatAcceptAttribute = string | { value: string };

interface UsePanelShellComputedUIOptions {
  agentKBBindings: Ref<unknown[]>;
  agents: Ref<unknown[]>;
  agentsLoading: Ref<boolean>;
  capturing: Ref<boolean>;
  chatAcceptAttribute: ChatAcceptAttribute;
  mentionCandidates: Ref<unknown[]>;
  sending: Ref<boolean>;
  showAttachments: ComputedRef<boolean> | Ref<boolean>;
  supportsVision: ComputedRef<boolean>;
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

  const screenshotDisabled = computed(
    () =>
      options.agents.value.length === 0 ||
      options.sending.value ||
      options.capturing.value,
  );

  const showScreenshotButton = computed(
    () => options.showAttachments.value && options.supportsVision.value,
  );

  return {
    mentionEmptyHint,
    resolvedAttachmentAccept,
    screenshotDisabled,
    showScreenshotButton,
  };
}
