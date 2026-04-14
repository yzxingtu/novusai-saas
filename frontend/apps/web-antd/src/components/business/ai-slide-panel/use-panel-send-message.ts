import type { ComputedRef, Ref } from 'vue';

import type { PageContext } from '#/api/shared/ai-chat';
import type { AgentItem, InputVariable } from '#/types/ai-chat';

import { message } from 'ant-design-vue';

import { $t } from '#/locales';
import { getAgentInputVariables } from '#/types/ai-chat';
import { getErrorMessage } from '#/utils/error-helpers';

type PendingAttachmentKind = 'audio' | 'file' | 'image' | 'video';

interface PendingAttachmentLike {
  type: PendingAttachmentKind;
}

interface RouteAttachmentFlags {
  hasAudioAttachments?: boolean;
  hasFileAttachments?: boolean;
  hasImageAttachments?: boolean;
  hasVideoAttachments?: boolean;
}

interface UsePanelSendMessageOptions {
  activeConversationId: Ref<null | number>;
  agents: Ref<AgentItem[]>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  currentPageContext: ComputedRef<null | PageContext>;
  deferSendForMissingVariables: (payload: {
    agentId: number;
    agentName: string;
    consumeMention?: boolean;
    pageContext: null | PageContext;
    requiredVars: InputVariable[];
    routeSource?: string;
  }) => void;
  ensureAgentVarsLoaded: (agentId: number) => void;
  forceRerouteNextTurn: Ref<boolean>;
  inputMessage: Ref<string>;
  isPinned: ComputedRef<boolean>;
  manualNewConversationAgentId: Ref<null | number>;
  pageContextKey: Ref<string | undefined>;
  pendingAttachments: Ref<PendingAttachmentLike[]>;
  pinnedAgentId: Ref<null | number | undefined>;
  routeMessage: (
    message: string,
    pageContextKey?: string,
    pageContext?: null | PageContext,
    attachmentFlags?: RouteAttachmentFlags,
    forceReroute?: boolean,
  ) => Promise<{
    agentId: number;
    agentName: string;
    routedBy: string;
  }>;
  selectedAgentId: Ref<null | number>;
  sendMessage: (options?: {
    agentId?: number;
    pageContext?: null | PageContext;
    routeSource?: null | string;
    silent?: boolean;
  }) => Promise<boolean>;
  showRouteNotice: (text: string) => void;
}

function collectAttachmentFlags(attachments: PendingAttachmentLike[]) {
  const hasImageAttachments = attachments.some(
    (attachment) => attachment.type === 'image',
  );
  const hasAudioAttachments = attachments.some(
    (attachment) => attachment.type === 'audio',
  );
  const hasVideoAttachments = attachments.some(
    (attachment) => attachment.type === 'video',
  );
  const hasFileAttachments = attachments.some(
    (attachment) => attachment.type === 'file',
  );

  return {
    hasAnyAttachments: attachments.length > 0,
    hasAudioAttachments,
    hasCapabilitySensitiveAttachments:
      hasImageAttachments || hasAudioAttachments || hasVideoAttachments,
    hasFileAttachments,
    hasImageAttachments,
    hasVideoAttachments,
  };
}

function resolveMissingVariables(options: {
  agent: AgentItem | undefined;
  agentId: number;
  allAgentsVariables: Record<number, Record<string, string>>;
  ensureAgentVarsLoaded: (agentId: number) => void;
}) {
  const inputVariables = getAgentInputVariables(options.agent);
  const requiredVariables = inputVariables.filter(
    (variable) => variable.required,
  );
  if (requiredVariables.length === 0) {
    return null;
  }

  options.ensureAgentVarsLoaded(options.agentId);
  const existingValues = options.allAgentsVariables[options.agentId] ?? {};
  const missingVariables = requiredVariables.filter(
    (variable) => !existingValues[variable.name]?.trim(),
  );
  if (missingVariables.length === 0) {
    return null;
  }

  return {
    agentName: options.agent?.name ?? '',
    inputVariables,
  };
}

export function usePanelSendMessage(options: UsePanelSendMessageOptions) {
  async function handleSendMessage() {
    const text = options.inputMessage.value.trim();
    if (!text && options.pendingAttachments.value.length === 0) {
      return false;
    }

    const {
      hasAnyAttachments,
      hasAudioAttachments,
      hasCapabilitySensitiveAttachments,
      hasFileAttachments,
      hasImageAttachments,
      hasVideoAttachments,
    } = collectAttachmentFlags(options.pendingAttachments.value);
    const pageContext = options.currentPageContext.value;

    if (options.isPinned.value && options.pinnedAgentId.value) {
      const pinnedAgentId = options.pinnedAgentId.value;
      if (pinnedAgentId !== options.selectedAgentId.value) {
        options.selectedAgentId.value = pinnedAgentId;
      }

      const pinnedAgent = options.agents.value.find(
        (agent) => agent.id === pinnedAgentId,
      );
      const missingPinnedVariables = resolveMissingVariables({
        agent: pinnedAgent,
        agentId: pinnedAgentId,
        allAgentsVariables: options.allAgentsVariables.value,
        ensureAgentVarsLoaded: options.ensureAgentVarsLoaded,
      });
      if (missingPinnedVariables) {
        options.deferSendForMissingVariables({
          agentId: pinnedAgentId,
          agentName: missingPinnedVariables.agentName,
          pageContext,
          requiredVars: missingPinnedVariables.inputVariables,
        });
        return false;
      }

      return options.sendMessage({
        agentId: pinnedAgentId,
        pageContext,
      });
    }

    const forceReroute = options.forceRerouteNextTurn.value;
    if (forceReroute) {
      options.forceRerouteNextTurn.value = false;
    }

    if (
      !options.activeConversationId.value &&
      options.manualNewConversationAgentId.value &&
      options.selectedAgentId.value ===
        options.manualNewConversationAgentId.value
    ) {
      const explicitAgentId = options.manualNewConversationAgentId.value;
      options.manualNewConversationAgentId.value = null;
      return options.sendMessage({
        agentId: explicitAgentId,
        pageContext,
      });
    }

    if (
      options.activeConversationId.value &&
      options.selectedAgentId.value &&
      !forceReroute
    ) {
      return options.sendMessage({ pageContext });
    }

    try {
      const routeResult = await options.routeMessage(
        text || (hasAnyAttachments ? ' ' : ''),
        options.pageContextKey.value,
        pageContext,
        {
          hasAudioAttachments,
          hasFileAttachments,
          hasImageAttachments,
          hasVideoAttachments,
        },
        forceReroute,
      );

      options.manualNewConversationAgentId.value = null;

      if (routeResult.agentId !== options.selectedAgentId.value) {
        options.selectedAgentId.value = routeResult.agentId;
      }

      const routedPageContext = options.currentPageContext.value;
      if (routeResult.routedBy === 'router') {
        options.showRouteNotice(
          $t('common.aiPanel.routedTo', { agent: routeResult.agentName }),
        );
      }

      const routedAgent = options.agents.value.find(
        (agent) => agent.id === routeResult.agentId,
      );
      const missingRoutedVariables = resolveMissingVariables({
        agent: routedAgent,
        agentId: routeResult.agentId,
        allAgentsVariables: options.allAgentsVariables.value,
        ensureAgentVarsLoaded: options.ensureAgentVarsLoaded,
      });
      if (missingRoutedVariables) {
        options.deferSendForMissingVariables({
          agentId: routeResult.agentId,
          agentName: missingRoutedVariables.agentName,
          pageContext: routedPageContext,
          requiredVars: missingRoutedVariables.inputVariables,
        });
        return false;
      }

      return options.sendMessage({
        agentId: routeResult.agentId,
        pageContext: routedPageContext,
      });
    } catch (error: unknown) {
      if (options.selectedAgentId.value && !hasCapabilitySensitiveAttachments) {
        message.warning($t('common.globalAiChat.routeFailedFallback'));
        return options.sendMessage({ pageContext });
      }

      const baseMessage = getErrorMessage(
        error,
        'common.http.internalServerError',
      );
      message.error(
        `${baseMessage} ${$t('common.globalAiChat.routeFailedHint')}`,
      );
      return false;
    }
  }

  return {
    handleSendMessage,
  };
}
