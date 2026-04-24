import type { ComputedRef, InjectionKey, Ref } from 'vue';

import type { useAIChat } from '#/components/business/ai-chat-panel/use-ai-chat';
import type { ConversationItem, InputVariable } from '#/types/ai-chat';

import { inject, provide } from 'vue';

export interface ConversationGroup {
  label: string;
  items: ConversationItem[];
}

export interface WorkspaceHighlight {
  icon: string;
  key: string;
  label: string;
  value: string;
}

export interface ExportMenuItem {
  key: string;
  label: string;
  onClick: () => void;
}

export interface VarsModalAgent {
  id: number;
  name: string;
  vars: InputVariable[];
}

export interface UserAIChatContext {
  apiPrefix: string;
  chat: ReturnType<typeof useAIChat>;
  mobileSidebarOpen: Ref<boolean>;
  conversationSearch: Ref<string>;
  groupedConversations: ComputedRef<ConversationGroup[]>;
  exportMenuItems: ComputedRef<ExportMenuItem[]>;
  editingConversationId: Ref<null | number>;
  editingTitle: Ref<string>;
  showMemoryPanel: Ref<boolean>;
  showWorkspaceHero: ComputedRef<boolean>;
  workspaceHighlights: ComputedRef<WorkspaceHighlight[]>;
  effectiveWelcomeMessage: ComputedRef<string>;
  effectiveSuggestedQuestions: ComputedRef<string[]>;
  chatHeaderSubtitle: ComputedRef<string>;
  agentsWithVarsInConversation: ComputedRef<
    Array<{
      id: number;
      input_variables?: InputVariable[] | null;
      name: string;
    }>
  >;
  headerHasVariables: ComputedRef<boolean>;
  headerVarsConfigured: ComputedRef<boolean>;
  multiVarsModalVisible: Ref<boolean>;
  multiVarsFormValues: Record<number, Record<string, string>>;
  multiVarsPersist: Ref<boolean>;
  varsModalVisible: Ref<boolean>;
  varsFormValues: Record<string, string>;
  varsModalAgent: Ref<null | VarsModalAgent>;
  varsPersist: Ref<boolean>;
  onSelectConversation: (convId: number) => void;
  onDeleteConversation: (convId: number) => void;
  onStartNewChat: () => void;
  onSelectAgent: (agentId: number) => void;
  startEditTitle: (conv: { id: number; title?: null | string }) => void;
  commitEditTitle: () => void;
  cancelEditTitle: () => void;
  onToggleMemory: () => Promise<void>;
  onClearMemory: () => void;
  onMultiPersistChange: (value: boolean) => void;
  onMultiVarValueChange: (payload: {
    agentId: number;
    name: string;
    value: string;
  }) => void;
  onMultiVarsCancel: () => void;
  onMultiVarsConfirm: () => void;
  onSinglePersistChange: (value: boolean) => void;
  onSingleVarValueChange: (payload: { name: string; value: string }) => void;
  openHeaderVarsModal: () => void;
  openSelectedAgentVarsModal: () => void;
  onVarsConfirm: () => void;
  onVarsCancel: () => void;
}

const userAIChatContextKey: InjectionKey<UserAIChatContext> =
  Symbol('UserAIChatContext');

export function provideUserAIChatContext(context: UserAIChatContext) {
  provide(userAIChatContextKey, context);
  return context;
}

export function useUserAIChatContext(): UserAIChatContext {
  const context = inject(userAIChatContextKey);
  if (!context) {
    throw new Error('UserAIChatContext is not provided');
  }
  return context;
}
