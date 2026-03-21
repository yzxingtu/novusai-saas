import type { MaybeRefOrGetter } from 'vue';

import type { PageOperation } from '#/components/business/ai-slide-panel/page-operation-registry';

import { getCurrentScope, onScopeDispose, toValue, watch } from 'vue';
import { useRoute } from 'vue-router';

import {
  appendPageOperations,
  normalizePageKey,
  registerPageContext,
  registerPageContextExtras,
  registerPageOperations,
} from '#/components/business/ai-slide-panel';

export interface UsePageAIRegistrationOptions {
  contextStrategy?: 'extras' | 'primary';
  data?: MaybeRefOrGetter<Record<string, unknown>>;
  enabled?: MaybeRefOrGetter<boolean>;
  entityDescription?: MaybeRefOrGetter<string>;
  entityName?: MaybeRefOrGetter<string>;
  operations?: MaybeRefOrGetter<PageOperation[] | undefined>;
  operationStrategy?: 'append' | 'primary';
  pageKey?: MaybeRefOrGetter<string | undefined>;
  registerContext?: boolean;
  registerOperations?: boolean;
  resource?: MaybeRefOrGetter<string>;
  title?: MaybeRefOrGetter<string>;
}

export function usePageAIRegistration(
  options: UsePageAIRegistrationOptions,
): void {
  const route = useRoute();
  let cleanupContext: (() => void) | null = null;
  let cleanupOperations: (() => void) | null = null;

  function cleanupRegistrations() {
    cleanupContext?.();
    cleanupContext = null;
    cleanupOperations?.();
    cleanupOperations = null;
  }

  function resolveRegisteredOperations(): PageOperation[] {
    return toValue(options.operations) ?? [];
  }

  function resolveOperationSignature(): string {
    return resolveRegisteredOperations()
      .map((operation) =>
        JSON.stringify({
          description: operation.description ?? '',
          label: operation.label,
          name: operation.name,
          params: operation.params ?? null,
          readonly: operation.readonly,
        }),
      )
      .join('|');
  }

  watch(
    [
      () => toValue(options.enabled) ?? true,
      () => {
        const resolvedPageKey =
          toValue(options.pageKey) ??
          ((route.meta?.ai as Record<string, unknown> | undefined)
            ?.pageContextKey as string | undefined) ??
          route.path;
        return resolvedPageKey ? normalizePageKey(resolvedPageKey) : undefined;
      },
      () => options.contextStrategy ?? 'primary',
      () => options.operationStrategy ?? 'primary',
      () => options.registerContext !== false,
      () => options.registerOperations !== false,
      () => resolveOperationSignature(),
    ],
    (
      [
        enabled,
        pageKey,
        contextStrategy,
        operationStrategy,
        shouldRegisterContext,
        shouldRegisterOperations,
      ],
      _previousValues,
      onCleanup,
    ) => {
      cleanupRegistrations();

      if (!enabled || !pageKey) {
        return;
      }

      const resolver = () => {
        const title =
          toValue(options.title) ??
          toValue(options.entityName) ??
          (route.meta?.title as string | undefined) ??
          pageKey;
        const resource = toValue(options.resource);
        const entityName = toValue(options.entityName);
        const entityDescription = toValue(options.entityDescription);
        const data = toValue(options.data);
        const pageData =
          contextStrategy === 'extras'
            ? {
                ...(entityDescription
                  ? { entity_description_append: entityDescription }
                  : {}),
                ...data,
              }
            : {
                ...(resource ? { resource } : {}),
                ...(entityName ? { entity_name: entityName } : {}),
                ...(entityDescription
                  ? { entity_description: entityDescription }
                  : {}),
                ...data,
              };

        return {
          page_key: pageKey,
          page_title: title,
          page_data: pageData,
        };
      };

      if (shouldRegisterContext) {
        cleanupContext =
          contextStrategy === 'extras'
            ? registerPageContextExtras(pageKey, resolver)
            : registerPageContext(pageKey, resolver);
      }

      const operations = resolveRegisteredOperations();
      if (shouldRegisterOperations && operations.length > 0) {
        cleanupOperations =
          operationStrategy === 'append'
            ? appendPageOperations(pageKey, operations)
            : registerPageOperations(pageKey, operations);
      }

      onCleanup(() => {
        cleanupRegistrations();
      });
    },
    { immediate: true },
  );

  if (getCurrentScope()) {
    onScopeDispose(() => {
      cleanupRegistrations();
    });
  }
}
