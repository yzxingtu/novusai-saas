import { onMounted, onUnmounted } from 'vue';

import {
  getActiveAIConversation,
  openAIPanel,
  registerPageContext,
  registerPageOperations,
  subscribeAIConversation,
} from '@novus/plugin-shared';

type WorkflowPageOperation = Parameters<typeof registerPageOperations>[1][number];

interface WorkflowPageAIContext {
  entityDescription?: string;
  entityTitle?: string;
  entityType?: string;
  pageData?: Record<string, unknown>;
  pageTitle?: string;
}

interface UseWorkflowPageAIOptions {
  buildContext: () => WorkflowPageAIContext;
  conversationScope?: string;
  operations?: WorkflowPageOperation[];
  pageKey: string;
}

interface WorkflowAIPanelOptions {
  agentId?: number;
  conversationId?: null | number;
  conversationScope?: string;
  message?: null | string;
  pageKey?: string;
  reuseStoredConversation?: boolean;
}

interface WorkflowAIConversationSnapshot {
  agentId: null | number;
  conversationId: null | number;
  pageContextKey?: null | string;
  routePath?: string;
  visible: boolean;
}

const WORKFLOW_AI_CONVERSATION_STORAGE_PREFIX =
  'workflow-orchestration.ai-conversation';

export const ADMIN_WORKFLOW_AI_CONVERSATION_SCOPE =
  'admin.workflow_orchestration.planner';
export const TENANT_WORKFLOW_AI_CONVERSATION_SCOPE =
  'tenant.workflow_orchestration.planner';

export function buildPrompt(sections: Array<null | string | undefined>): string {
  return sections
    .map((section) => section?.trim())
    .filter((section): section is string => Boolean(section))
    .join('\n\n');
}

function normalizeConversationId(value: unknown): null | number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    return null;
  }
  return value;
}

function resolveConversationScope(options: {
  conversationScope?: string;
  pageKey?: string;
}): string {
  return options.conversationScope?.trim() || options.pageKey?.trim() || '';
}

function getConversationStorageKey(scope: string): string {
  return `${WORKFLOW_AI_CONVERSATION_STORAGE_PREFIX}:${scope}`;
}

export function getStoredWorkflowAIConversationId(scopeOrPageKey: string): null | number {
  const scope = scopeOrPageKey.trim();
  if (!scope) {
    return null;
  }

  try {
    const raw = window.sessionStorage.getItem(getConversationStorageKey(scope));
    if (!raw) {
      return null;
    }
    return normalizeConversationId(Number(raw));
  } catch {
    return null;
  }
}

function persistWorkflowAIConversationId(scope: string, conversationId: number): void {
  try {
    window.sessionStorage.setItem(
      getConversationStorageKey(scope),
      String(conversationId),
    );
  } catch {
    // Ignore storage write failures. / 忽略 sessionStorage 写入失败
  }
}

function clearStoredWorkflowAIConversation(scope: string): void {
  try {
    window.sessionStorage.removeItem(getConversationStorageKey(scope));
  } catch {
    // Ignore storage write failures. / 忽略 sessionStorage 写入失败
  }
}

function syncWorkflowAIConversation(
  scope: string,
  snapshot: WorkflowAIConversationSnapshot,
): void {
  if (!scope || !snapshot.visible || !scopeMatchesSnapshot(scope, snapshot)) {
    return;
  }

  const conversationId = normalizeConversationId(snapshot.conversationId);
  if (conversationId) {
    persistWorkflowAIConversationId(scope, conversationId);
    return;
  }

  clearStoredWorkflowAIConversation(scope);
}

function getConversationScopeNamespace(scope: string): string {
  const normalizedScope = scope.trim();
  if (!normalizedScope) {
    return '';
  }

  if (normalizedScope.endsWith('.planner')) {
    return normalizedScope.slice(0, -'.planner'.length);
  }

  return normalizedScope;
}

function scopeMatchesSnapshot(
  scope: string,
  snapshot: WorkflowAIConversationSnapshot,
): boolean {
  const scopeNamespace = getConversationScopeNamespace(scope);
  if (!scopeNamespace) {
    return false;
  }

  const pageContextKey = snapshot.pageContextKey?.trim();
  return pageContextKey ? pageContextKey.startsWith(scopeNamespace) : false;
}

export function openWorkflowAIPanel(options: WorkflowAIPanelOptions): void {
  const scope = resolveConversationScope(options);
  const conversationId =
    options.conversationId !== undefined
      ? options.conversationId
      : options.reuseStoredConversation === false
        ? null
        : getStoredWorkflowAIConversationId(scope);

  openAIPanel({
    agentId: options.agentId,
    conversationId,
    message: options.message,
  });
}

export function useWorkflowPageAI(options: UseWorkflowPageAIOptions): void {
  let cleanupContext = () => {};
  let cleanupOperations = () => {};
  let cleanupConversation = () => {};

  onMounted(() => {
    const scope = resolveConversationScope({
      conversationScope: options.conversationScope,
      pageKey: options.pageKey,
    });

    if (scope) {
      cleanupConversation = subscribeAIConversation(
        (snapshot: WorkflowAIConversationSnapshot) => {
          syncWorkflowAIConversation(scope, snapshot);
        },
      );

      syncWorkflowAIConversation(scope, getActiveAIConversation());
    }

    cleanupContext = registerPageContext(options.pageKey, () => {
      const context = options.buildContext();
      return {
        entity_description: context.entityDescription,
        entity_title: context.entityTitle ?? context.pageTitle,
        entity_type: context.entityType,
        page_data: context.pageData ?? {},
        page_key: options.pageKey,
        page_title: context.pageTitle ?? context.entityTitle ?? options.pageKey,
      };
    });

    cleanupOperations =
      options.operations && options.operations.length > 0
        ? registerPageOperations(options.pageKey, options.operations)
        : () => {};
  });

  onUnmounted(() => {
    cleanupConversation();
    cleanupContext();
    cleanupOperations();
  });
}
