import type { PageOperation } from '#/components/business/ai-runtime/page-operation-types';

import type { CrudOperationExecutorContext } from './use-ai-operations-executor-types';

import { resolveRemoteOptions } from './use-ai-operations-remote-options';
import { buildCrudFormOperations, buildCrudFormStateOperation } from './use-ai-operations-executor-crud-form';
import { buildCrudListOperations } from './use-ai-operations-executor-crud-list';
import { buildCrudNavigationOperations } from './use-ai-operations-executor-crud-navigation';

export function buildStandardCrudOperations(
  context: CrudOperationExecutorContext,
): PageOperation[] {
  const { resource, rawFormSchema, formParamsMap } = context;

  // Lazy-load remote options once and merge into formParamsMap
  // 惰性加载远程选项并合并到 formParamsMap
  let _remoteResolved = false;
  let _remoteResolvePromise: null | Promise<void> = null;
  async function ensureRemoteOptions(): Promise<void> {
    if (_remoteResolved || rawFormSchema.length === 0) return;
    if (_remoteResolvePromise) {
      await _remoteResolvePromise;
      return;
    }
    _remoteResolvePromise = (async () => {
      const remoteOpts = await resolveRemoteOptions(rawFormSchema, resource);
      for (const [field, options] of remoteOpts) {
        const existing = formParamsMap[field];
        if (existing && !existing.options) {
          existing.options = options;
        }
      }
      _remoteResolved = true;
    })();
    try {
      await _remoteResolvePromise;
    } finally {
      _remoteResolvePromise = null;
    }
  }
  // Fire-and-forget preload / 触发后台预加载
  if (
    rawFormSchema.some(
      (s) =>
        s.component === 'ApiSelect' ||
        s.component === 'ApiTreeSelect' ||
        s.component === 'IdentityRemoteSelect',
    )
  ) {
    ensureRemoteOptions();
  }

  const operations: PageOperation[] = [
    ...buildCrudListOperations(context),
    ...buildCrudFormOperations(context),
    ...buildCrudNavigationOperations(context),
  ];

  const formStateOperation = buildCrudFormStateOperation(context);
  if (formStateOperation) {
    operations.push(formStateOperation);
  }

  return operations;
}
