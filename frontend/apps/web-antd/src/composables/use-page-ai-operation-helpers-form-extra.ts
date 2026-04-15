import type { AnyRecord } from './use-page-ai-operation-helpers-core';

import {
  expandDotKeys,
  hasOwnKeys,
} from './use-page-ai-operation-helpers-core';

interface BuildPageAIFormExtraDataOptions {
  baseDefaults?: AnyRecord;
  defaults?: AnyRecord;
  overrides?: AnyRecord;
  pageKey: string;
  resource?: string;
}

export function buildPageAIFormExtraData(
  options: BuildPageAIFormExtraDataOptions,
): Record<string, unknown> {
  const defaults = {
    ...options.baseDefaults,
    ...options.defaults,
  };

  return {
    _pageKey: options.pageKey,
    ...(options.resource ? { _resource: options.resource } : {}),
    ...(hasOwnKeys(defaults) ? { _defaults: expandDotKeys(defaults) } : {}),
    ...(hasOwnKeys(options.overrides)
      ? { _overrides: expandDotKeys(options.overrides) }
      : {}),
  };
}
