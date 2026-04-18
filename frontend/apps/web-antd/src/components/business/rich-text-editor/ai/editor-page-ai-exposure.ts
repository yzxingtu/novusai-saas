import type {
  RichTextPageAIOperation,
  RichTextPageAIOperationResult,
} from './editor-page-ai-operations';

import { ref } from 'vue';

import { $t } from '@vben/locales';

import { normalizeRuntimePageKey } from './page-key';

export interface RichTextPageAIExposure {
  editorInstanceId?: string;
  getContextData?: () => Record<string, unknown>;
  getOperations?: () => RichTextPageAIOperation[];
  pageKey: string;
  priority?: number;
  providerId: string;
}

export interface WaitForRichTextPageAIOperationOptions {
  operationName?: string;
  pollMs?: number;
  timeoutMs?: number;
  warnOnTimeout?: boolean;
}

const DEFAULT_EDITOR_OPERATION_NAME = 'get_editor_html';
const DEFAULT_POLL_MS = 80;
const DEFAULT_TIMEOUT_MS = 2000;

const pageAIExposures = new Map<string, RichTextPageAIExposure>();
export const richTextPageAIExposureVersion = ref(0);

function bumpExposureVersion() {
  richTextPageAIExposureVersion.value += 1;
}

function stableProviderOrder(
  a: RichTextPageAIExposure,
  b: RichTextPageAIExposure,
): number {
  const priorityDiff = (b.priority ?? 0) - (a.priority ?? 0);
  if (priorityDiff !== 0) return priorityDiff;
  return a.providerId.localeCompare(b.providerId);
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function listProvidersForPage(pageKey: string, editorInstanceId?: string) {
  const normalizedPageKey = normalizeRuntimePageKey(pageKey);
  return [...pageAIExposures.values()]
    .filter((provider) => {
      if (normalizeRuntimePageKey(provider.pageKey) !== normalizedPageKey) {
        return false;
      }
      if (!editorInstanceId) {
        return true;
      }
      return (
        !provider.editorInstanceId ||
        provider.editorInstanceId === editorInstanceId
      );
    })
    .toSorted(stableProviderOrder);
}

export function clearRichTextPageAIExposures() {
  pageAIExposures.clear();
  bumpExposureVersion();
}

export function registerRichTextPageAIExposure(
  provider: RichTextPageAIExposure,
): () => void {
  pageAIExposures.set(provider.providerId, provider);
  bumpExposureVersion();

  return () => {
    const current = pageAIExposures.get(provider.providerId);
    if (!current) return;
    pageAIExposures.delete(provider.providerId);
    bumpExposureVersion();
  };
}

export function listRichTextPageAIExposures(
  pageKey?: string,
  editorInstanceId?: string,
): RichTextPageAIExposure[] {
  if (!pageKey) {
    return [...pageAIExposures.values()].toSorted(stableProviderOrder);
  }
  return listProvidersForPage(pageKey, editorInstanceId);
}

export function listRichTextPageAIOperations(
  pageKey: string,
  editorInstanceId?: string,
): RichTextPageAIOperation[] {
  const deduped = new Map<string, RichTextPageAIOperation>();

  for (const provider of listProvidersForPage(pageKey, editorInstanceId)) {
    const operations = provider.getOperations?.() ?? [];
    for (const operation of operations) {
      if (!operation?.name || deduped.has(operation.name)) {
        continue;
      }
      deduped.set(operation.name, operation);
    }
  }

  return [...deduped.values()];
}

export function collectRichTextPageAIContextData(
  pageKey: string,
  editorInstanceId?: string,
): Record<string, unknown> {
  const merged: Record<string, unknown> = {};
  for (const provider of listProvidersForPage(pageKey, editorInstanceId)) {
    const data = provider.getContextData?.();
    if (!isPlainRecord(data)) {
      continue;
    }
    Object.assign(merged, data);
  }
  return merged;
}

export async function executeRichTextPageAIOperation(input: {
  editorInstanceId?: string;
  operationName: string;
  pageKey: string;
  params?: Record<string, unknown>;
}): Promise<RichTextPageAIOperationResult> {
  const operations = listRichTextPageAIOperations(
    input.pageKey,
    input.editorInstanceId,
  );
  const operation = operations.find(
    (item) => item.name === input.operationName,
  );

  if (!operation || !operation.handler) {
    const normalizedPageKey = normalizeRuntimePageKey(input.pageKey);
    return {
      success: false,
      message: $t('shared.pageOperation.msg.operationNotRegistered', {
        op: input.operationName,
        page: normalizedPageKey,
      }),
      error_type: 'not_registered',
    };
  }

  return operation.handler(input.params ?? {});
}

export async function waitForRichTextPageAIOperation(
  pageKey: string,
  options: WaitForRichTextPageAIOperationOptions = {},
): Promise<boolean> {
  const operationName = options.operationName ?? DEFAULT_EDITOR_OPERATION_NAME;
  const pollMs = options.pollMs ?? DEFAULT_POLL_MS;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const operations = listRichTextPageAIOperations(pageKey);
    if (operations.some((operation) => operation.name === operationName)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }

  if (options.warnOnTimeout !== false) {
    console.warn(
      '[RichTextPageAI] waitForRichTextPageAIOperation timed out for "%s" while waiting for "%s".',
      pageKey,
      operationName,
    );
  }

  return false;
}
