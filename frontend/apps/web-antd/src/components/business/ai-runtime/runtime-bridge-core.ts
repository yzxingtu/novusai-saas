import type { AIRouteSecurityPolicy } from './security-policy';
import type { UIRouteLike } from './types';
import type { UIRuntime } from './ui-runtime';
import type { UISnapshot } from './ui-snapshot-generator';

import type { PageContext } from '#/api/shared/ai-chat';

import { resolveRoutePageKey } from '#/components/business/ai-runtime/page-key-utils';
import { currentRouteAISecurityPolicy } from '#/composables/use-ai-page-policy';
import { $t } from '#/locales';

import { createUIRuntime } from './ui-runtime';

export interface EnsureGlobalUIRuntimeOptions {
  getRoute?: () => null | UIRouteLike;
}

export interface RuntimeSnapshotResult {
  pageContext: PageContext;
  sizeBytes: number;
  snapshot: UISnapshot;
}

export interface RuntimeFormActionResult {
  data?: Record<string, unknown>;
  error?: string;
  error_type?: string;
  message: string;
  success: boolean;
}

let globalRuntime: null | UIRuntime = null;
let globalRouteGetter: (() => null | UIRouteLike) | undefined;

export function byteSize(value: unknown): number {
  return new TextEncoder().encode(JSON.stringify(value)).length;
}

export function normalizeText(value: unknown, maxLength = 240): string {
  return String(value ?? '')
    .replaceAll(/\s+/g, ' ')
    .trim()
    .slice(0, maxLength);
}

export function escapeSelectorValue(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value);
  }
  return value.replaceAll('"', String.raw`\"`);
}

export function resolveCurrentRoute(): null | UIRouteLike {
  return globalRouteGetter?.() ?? null;
}

export function resolveRuntimePageKey(explicitPageKey?: string): string {
  if (explicitPageKey?.trim()) {
    return resolveRoutePageKey(undefined, explicitPageKey.trim());
  }
  const route = resolveCurrentRoute();
  return resolveRoutePageKey(
    route
      ? {
          meta: route.meta,
          path: route.fullPath,
        }
      : undefined,
    typeof window === 'undefined' ? '' : window.location.pathname,
  );
}

export function resolvePageTitle(pageKey: string): string {
  const routeTitle = resolveCurrentRoute()?.meta?.title;
  if (typeof routeTitle === 'string' && routeTitle.trim()) {
    const localizedTitle = String($t(routeTitle.trim()) || '').trim();
    return normalizeText(localizedTitle || routeTitle.trim(), 200) || pageKey;
  }
  return normalizeText(document.title || pageKey, 200) || pageKey;
}

export function getCurrentRouteSecurityPolicy(): AIRouteSecurityPolicy {
  return {
    ...currentRouteAISecurityPolicy.value,
    confirmActionKinds: [
      ...(currentRouteAISecurityPolicy.value.confirmActionKinds ?? []),
    ],
    disabledActionKinds: [
      ...(currentRouteAISecurityPolicy.value.disabledActionKinds ?? []),
    ],
  };
}

export function ensureRuntimeInstance(): UIRuntime {
  if (!globalRuntime) {
    globalRuntime = createUIRuntime({
      getRoute: resolveCurrentRoute,
    });
    globalRuntime.initialize();
  }
  return globalRuntime;
}

export function ensureGlobalUIRuntime(
  options: EnsureGlobalUIRuntimeOptions = {},
): UIRuntime {
  if (options.getRoute) {
    globalRouteGetter = options.getRoute;
  }
  return ensureRuntimeInstance();
}

export function ensureElementVisible(
  element: HTMLElement | null,
): element is HTMLElement {
  if (!element) {
    return false;
  }
  const style = window.getComputedStyle(element);
  if (
    element.hidden ||
    style.display === 'none' ||
    style.visibility === 'hidden'
  ) {
    return false;
  }
  return element.getClientRects().length > 0 || style.opacity !== '0';
}

export function queryElementsByText(text: string): HTMLElement[] {
  const normalized = normalizeText(text).toLocaleLowerCase();
  if (!normalized) {
    return [];
  }
  return [...document.querySelectorAll<HTMLElement>('body *')].filter(
    (element) => {
      if (!ensureElementVisible(element)) {
        return false;
      }
      return normalizeText(element.innerText || element.textContent || '')
        .toLocaleLowerCase()
        .includes(normalized);
    },
  );
}

export function queryElementByLocator(locator: string): HTMLElement | null {
  const normalized = normalizeText(locator);
  if (!normalized) {
    return null;
  }

  const prefixed = [
    ['ai-id:', `[data-ai-id="${escapeSelectorValue(normalized.slice(6))}"]`],
    ['testid:', `[data-testid="${escapeSelectorValue(normalized.slice(7))}"]`],
    ['id:', `#${escapeSelectorValue(normalized.slice(3))}`],
    ['name:', `[name="${escapeSelectorValue(normalized.slice(5))}"]`],
    ['href:', `a[href="${escapeSelectorValue(normalized.slice(5))}"]`],
  ] as const;
  for (const [prefix, selector] of prefixed) {
    if (normalized.startsWith(prefix)) {
      try {
        const match = document.querySelector<HTMLElement>(selector);
        return ensureElementVisible(match) ? match : null;
      } catch {
        return null;
      }
    }
  }

  if (normalized.startsWith('text:')) {
    return queryElementsByText(normalized.slice(5))[0] ?? null;
  }

  const cssSelector = normalized.startsWith('css:')
    ? normalized.slice(4)
    : normalized;
  try {
    const match = document.querySelector<HTMLElement>(cssSelector);
    return ensureElementVisible(match) ? match : null;
  } catch {
    return null;
  }
}

export function readFormLikeElementValue(
  element: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement,
): string {
  if (element instanceof HTMLSelectElement) {
    return element.value || '';
  }
  return element.value || element.placeholder || '';
}
