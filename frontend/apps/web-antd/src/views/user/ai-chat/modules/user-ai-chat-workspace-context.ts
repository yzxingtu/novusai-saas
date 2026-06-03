import type { InjectionKey, Ref } from 'vue';

import type { UserAIChatContext } from './ai-chat-context';

import { inject, provide } from 'vue';

export interface UserAIChatWorkspaceContext {
  page: UserAIChatContext;
  previewImageUrl: Ref<string>;
  previewImageVisible: Ref<boolean>;
  openImagePreview: (url: string) => void;
  openMobileSidebar: () => void;
  onCopyMessage: (content: string) => Promise<void>;
  handleSendClick: () => void;
  handleKeyDown: (event: KeyboardEvent) => void;
  askSuggested: (question: string) => void;
}

const userAIChatWorkspaceContextKey: InjectionKey<UserAIChatWorkspaceContext> =
  Symbol('UserAIChatWorkspaceContext');

export function provideUserAIChatWorkspaceContext(
  context: UserAIChatWorkspaceContext,
) {
  provide(userAIChatWorkspaceContextKey, context);
  return context;
}

export function useUserAIChatWorkspaceContext(): UserAIChatWorkspaceContext {
  const context = inject(userAIChatWorkspaceContextKey);
  if (!context) {
    throw new Error('UserAIChatWorkspaceContext is not provided');
  }
  return context;
}
