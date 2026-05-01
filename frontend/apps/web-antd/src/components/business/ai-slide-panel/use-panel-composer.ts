import type { ComputedRef, Ref } from 'vue';

import type { ChatKBBindingInfo } from '#/api/shared/ai-chat';
import type {
  ChatAttachment,
  MentionCandidate,
  MentionSkillPackageBinding,
  SelectedSkillPackageChip,
} from '#/types/ai-chat';

import { computed } from 'vue';

import { $t } from '#/locales';
import { getFileIcon } from '#/utils/file';

interface UsePanelComposerOptions {
  agents: Ref<Array<{ id: number }>>;
  agentKBBindings: Ref<ChatKBBindingInfo[]>;
  inputMessage: Ref<string>;
  mentionActiveIndex: Ref<number>;
  mentionCandidates:
    | ComputedRef<MentionCandidate[]>
    | Readonly<Ref<MentionCandidate[]>>;
  pendingAttachments: Ref<ChatAttachment[]>;
  routing: Ref<boolean>;
  selectedKBIds: Ref<number[]>;
  selectedSkillNames: Ref<string[]>;
  selectMentionKnowledgeBase: (
    binding: Pick<ChatKBBindingInfo, 'knowledge_base_id'>,
  ) => void;
  selectMentionSkillPackage: (
    binding: Pick<MentionSkillPackageBinding, 'package_name' | 'skill_name'>,
  ) => void;
  sending: Ref<boolean>;
  showAttachments: ComputedRef<boolean> | Ref<boolean>;
  streaming: Ref<boolean>;
  uploading: Ref<boolean>;
}

export function usePanelComposer(options: UsePanelComposerOptions) {
  const composerAttachments = computed(() =>
    options.pendingAttachments.value.map((attachment, index) => ({
      icon:
        attachment.type === 'image'
          ? undefined
          : getFileIcon(attachment.name || '', attachment.mime_type),
      key: attachment.url || `${attachment.type}-${index}`,
      name: attachment.name || '',
      previewUrl: attachment.preview || attachment.url,
      type: attachment.type,
    })),
  );

  const composerBoundKnowledgeBases = computed(() =>
    options.agentKBBindings.value.map((binding) => ({
      id: binding.knowledge_base_id,
      label: binding.kb_name || `KB#${binding.knowledge_base_id}`,
    })),
  );

  const composerSelectedKnowledgeBases = computed(() =>
    options.selectedKBIds.value.map((knowledgeBaseId) => ({
      id: knowledgeBaseId,
      label:
        options.agentKBBindings.value.find(
          (binding) => binding.knowledge_base_id === knowledgeBaseId,
        )?.kb_name || `KB#${knowledgeBaseId}`,
    })),
  );

  const composerSelectedSkillPackages = computed<SelectedSkillPackageChip[]>(
    () =>
      options.selectedSkillNames.value.map((skillName) => ({
        id: skillName,
        label: skillName,
        value: skillName,
      })),
  );

  const composerMentionCandidates = computed(() =>
    options.mentionCandidates.value.map((candidate, candidateIndex) => {
      if (candidate.kind === 'skill_package') {
        return {
          active: candidateIndex === options.mentionActiveIndex.value,
          id: candidate.binding.package_id ?? candidate.binding.skill_id,
          kind: candidate.kind,
          subtitle: $t('common.globalAiChat.mentionSkillPickHint'),
          title:
            candidate.binding.package_name ||
            candidate.binding.skill_name ||
            `Skill#${candidate.binding.skill_id}`,
        };
      }
      return {
        active: candidateIndex === options.mentionActiveIndex.value,
        id: candidate.binding.knowledge_base_id,
        kind: candidate.kind,
        subtitle: $t('common.globalAiChat.mentionKbPickHint'),
        title:
          candidate.binding.kb_name ||
          `KB#${candidate.binding.knowledge_base_id}`,
      };
    }),
  );

  const composerSendState = computed(() => {
    if (options.streaming.value) {
      return 'streaming' as const;
    }
    if (options.routing.value) {
      return 'routing' as const;
    }
    if (options.sending.value || options.uploading.value) {
      return 'sending' as const;
    }
    return 'idle' as const;
  });

  const composerSendDisabled = computed(
    () =>
      (!options.inputMessage.value.trim() &&
        options.pendingAttachments.value.length === 0) ||
      options.agents.value.length === 0 ||
      options.sending.value ||
      options.uploading.value,
  );

  const composerAttachmentLimitHint = computed(() =>
    options.showAttachments.value && options.pendingAttachments.value.length > 0
      ? $t('common.globalAiChat.attachmentCount', {
          count: options.pendingAttachments.value.length,
          max: 5,
        })
      : '',
  );

  function onSelectMentionCandidate(payload: {
    id: number;
    kind: 'knowledge_base' | 'skill_package';
  }) {
    if (payload.kind === 'skill_package') {
      const skillCandidate = options.mentionCandidates.value.find(
        (candidate) =>
          candidate.kind === 'skill_package' &&
          (candidate.binding.package_id ?? candidate.binding.skill_id) ===
            payload.id,
      );
      if (skillCandidate?.kind === 'skill_package') {
        options.selectMentionSkillPackage(skillCandidate.binding);
      }
      return;
    }
    const knowledgeBaseCandidate = options.mentionCandidates.value.find(
      (candidate) =>
        candidate.kind === 'knowledge_base' &&
        candidate.binding.knowledge_base_id === payload.id,
    );
    if (knowledgeBaseCandidate?.kind === 'knowledge_base') {
      options.selectMentionKnowledgeBase(knowledgeBaseCandidate.binding);
    }
  }

  return {
    composerAttachmentLimitHint,
    composerAttachments,
    composerBoundKnowledgeBases,
    composerMentionCandidates,
    composerSelectedKnowledgeBases,
    composerSelectedSkillPackages,
    composerSendDisabled,
    composerSendState,
    onSelectMentionCandidate,
  };
}
