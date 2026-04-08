import type {
  RichTextRuntimeOperation,
  RichTextRuntimeOperationResult,
} from './runtime-operation-types';

import { ref } from 'vue';

import { $t } from '@vben/locales';

import { normalizeRuntimePageKey } from './page-key';

export interface RichTextRuntimeProvider {
  editorInstanceId?: string;
  getContextData?: () => Record<string, unknown>;
  getOperations?: () => RichTextRuntimeOperation[];
  pageKey: string;
  priority?: number;
  providerId: string;
}

export interface WaitForRichTextRuntimeOperationOptions {
  operationName?: string;
  pollMs?: number;
  timeoutMs?: number;
  warnOnTimeout?: boolean;
}

const DEFAULT_EDITOR_OPERATION_NAME = 'get_editor_html';
const DEFAULT_POLL_MS = 80;
const DEFAULT_TIMEOUT_MS = 2000;

const providers = new Map<string, RichTextRuntimeProvider>();
export const richTextRuntimeRegistryVersion = ref(0);

function bumpRegistryVersion() {
  richTextRuntimeRegistryVersion.value += 1;
}

function stableProviderOrder(
  a: RichTextRuntimeProvider,
  b: RichTextRuntimeProvider,
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
  return [...providers.values()]
    .filter((provider) => {
      if (normalizeRuntimePageKey(provider.pageKey) !== normalizedPageKey) {
        return false;
      }
      if (!editorInstanceId) {
        return true;
      }
      return (
        !provider.editorInstanceId || provider.editorInstanceId === editorInstanceId
      );
    })
    .sort(stableProviderOrder);
}

export function clearRichTextRuntimeAdapterRegistry() {
  providers.clear();
  bumpRegistryVersion();
}

export function registerRichTextRuntimeProvider(
  provider: RichTextRuntimeProvider,
): () => void {
  providers.set(provider.providerId, provider);
  bumpRegistryVersion();

  return () => {
    const current = providers.get(provider.providerId);
    if (!current) return;
    providers.delete(provider.providerId);
    bumpRegistryVersion();
  };
}

export function listRichTextRuntimeProviders(
  pageKey?: string,
  editorInstanceId?: string,
): RichTextRuntimeProvider[] {
  if (!pageKey) {
    return [...providers.values()].sort(stableProviderOrder);
  }
  return listProvidersForPage(pageKey, editorInstanceId);
}

export function listRichTextRuntimeOperations(
  pageKey: string,
  editorInstanceId?: string,
): RichTextRuntimeOperation[] {
  const deduped = new Map<string, RichTextRuntimeOperation>();

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

export function collectRichTextRuntimeContextData(
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

export async function executeRichTextRuntimeOperation(input: {
  editorInstanceId?: string;
  operationName: string;
  pageKey: string;
  params?: Record<string, unknown>;
}): Promise<RichTextRuntimeOperationResult> {
  const operations = listRichTextRuntimeOperations(
    input.pageKey,
    input.editorInstanceId,
  );
  const operation = operations.find((item) => item.name === input.operationName);

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

export async function waitForRichTextRuntimeOperation(
  pageKey: string,
  options: WaitForRichTextRuntimeOperationOptions = {},
): Promise<boolean> {
  const operationName = options.operationName ?? DEFAULT_EDITOR_OPERATION_NAME;
  const pollMs = options.pollMs ?? DEFAULT_POLL_MS;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const operations = listRichTextRuntimeOperations(pageKey);
    if (operations.some((operation) => operation.name === operationName)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }

  if (options.warnOnTimeout !== false) {
    console.warn(
      '[RichTextRuntimeAdapter] waitForRichTextRuntimeOperation timed out for "%s" while waiting for "%s".',
      pageKey,
      operationName,
    );
  }

  return false;
}
