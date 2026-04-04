import type { RouteMeta, Router } from 'vue-router';

import { watch } from 'vue';

import { resolveRouteMetaTitle } from '@vben/utils';

type HasLocaleKeyFn = (key: string) => boolean;
type RouterLike = Pick<Router, 'currentRoute'>;
type TranslateFn = (key: string) => string;

export interface BuildDocumentTitleOptions {
  appName: string;
  hasLocaleKey: HasLocaleKeyFn;
  locale: string;
  meta?: Partial<RouteMeta>;
  translate: TranslateFn;
}

export interface SetupDocumentTitleSyncOptions {
  appName: () => string;
  dynamicTitle: () => boolean;
  hasLocaleKey: HasLocaleKeyFn;
  locale: () => string;
  refreshSignal?: () => number | string;
  router: RouterLike;
  translate: TranslateFn;
}

export function buildDocumentTitle(
  options: BuildDocumentTitleOptions,
): string {
  const routeTitle = resolveRouteMetaTitle(options.meta, {
    hasLocaleKey: options.hasLocaleKey,
    locale: options.locale,
    translate: options.translate,
  });

  return (routeTitle ? `${routeTitle} - ` : '') + options.appName;
}

export function setupDocumentTitleSync(
  options: SetupDocumentTitleSyncOptions,
) {
  return watch(
    () => {
      const currentRoute = options.router.currentRoute.value;
      const routeMeta = currentRoute.meta ?? {};

      return [
        options.dynamicTitle(),
        options.locale(),
        options.appName(),
        String(options.refreshSignal?.() ?? ''),
        String(currentRoute.name ?? ''),
        currentRoute.path,
        typeof routeMeta.title === 'string' ? routeMeta.title : '',
        JSON.stringify(routeMeta.titleLocaleMap ?? {}),
      ];
    },
    () => {
      if (!options.dynamicTitle() || typeof document === 'undefined') {
        return;
      }

      document.title = buildDocumentTitle({
        appName: options.appName(),
        hasLocaleKey: options.hasLocaleKey,
        locale: options.locale(),
        meta: options.router.currentRoute.value.meta,
        translate: options.translate,
      });
    },
    { immediate: true },
  );
}
