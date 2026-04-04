import type { PageOperation } from './page-operation-types';

import { useAccessStore } from '@vben/stores';

import {
  capturePageScreenshot,
  DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS,
  resolveScreenshotUploadTarget,
} from '#/composables/use-page-screenshot';
import { $t } from '#/locales';
import { router } from '#/router';
import { getEndpointFromPath } from '#/utils/endpoint';
import {
  buildMenuNavigationEntries,
  resolveMenuNavigationTarget,
  searchMenuNavigationEntries,
  serializeMenuNavigationEntry,
} from '#/utils/menu-navigation';
import {
  buildPageDataPreview,
  navigateToMenuEntry,
} from '#/utils/page-navigation';

import { scanDomSemantics } from './dom-semantic-scanner';
import { resolvePageContext } from './page-context-registry';
import { normalizePageKey } from './page-key-utils';

function getAccessibleMenusSafe(): ReturnType<typeof useAccessStore>['accessMenus'] {
  try {
    return useAccessStore().accessMenus;
  } catch {
    return [];
  }
}

export function getDefaultPageOperations(pageKey: string): PageOperation[] {
  const normalizedKey = normalizePageKey(pageKey);

  return [
    {
      name: 'read_current_view',
      label: $t('shared.pageOperation.readCurrentView'),
      description:
        'Read a compact snapshot of the current page view, including page context and DOM structure / 读取当前页面的紧凑视图快照，包括页面上下文与 DOM 结构',
      readonly: true,
      handler: async () => {
        const pageContext = resolvePageContext(normalizedKey);
        const domSnapshot = scanDomSemantics();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.currentViewRead'),
          data: {
            page_key: pageContext?.page_key ?? normalizedKey,
            page_title:
              pageContext?.page_title ??
              domSnapshot?.page_title ??
              normalizedKey,
            dom_snapshot: domSnapshot ?? undefined,
            page_data_preview: buildPageDataPreview(pageContext?.page_data),
          },
        };
      },
    },
    {
      name: 'read_current_sections',
      label: $t('shared.pageOperation.readCurrentSections'),
      description:
        'Read the current page sections, tabs, tables, forms, and action buttons / 读取当前页面的分区、页签、表格、表单和操作按钮',
      readonly: true,
      handler: async () => {
        const domSnapshot = scanDomSemantics();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.currentSectionsRead'),
          data: domSnapshot
            ? {
                action_buttons: domSnapshot.action_buttons,
                breadcrumb: domSnapshot.breadcrumb,
                detail_fields: domSnapshot.detail_fields,
                forms: domSnapshot.forms,
                overlays: domSnapshot.overlays,
                page_title: domSnapshot.page_title,
                stat_cards: domSnapshot.stat_cards,
                tables: domSnapshot.tables,
                tabs: domSnapshot.tabs,
                text_blocks: domSnapshot.text_blocks,
              }
            : { page_title: normalizedKey },
        };
      },
    },
    {
      name: 'list_available_menus',
      label: $t('shared.pageOperation.listAvailableMenus'),
      description:
        'List accessible menus for the current endpoint so you can decide where to navigate next / 列出当前端点下可访问的菜单，供后续导航决策使用',
      readonly: true,
      handler: async () => {
        const currentRoute = router.currentRoute.value;
        const entries = buildMenuNavigationEntries({
          currentEndpoint: getEndpointFromPath(currentRoute.path),
          menus: getAccessibleMenusSafe(),
          translate: $t,
        });

        return {
          success: true,
          message: $t('shared.pageOperation.msg.availableMenusListed', {
            count: entries.length,
          }),
          data: {
            items: entries.map((entry) => serializeMenuNavigationEntry(entry)),
          },
        };
      },
    },
    {
      name: 'navigate_menu',
      label: $t('shared.pageOperation.navigateMenu'),
      description:
        'Navigate to an accessible menu within the current endpoint by natural-language target / 按自然语言目标在当前端点内跳转到可访问菜单',
      readonly: true,
      params: {
        target: {
          type: 'string',
          description: 'Target menu title, path, breadcrumb, or page key / 目标菜单标题、路径、面包屑或页面 key',
          required: true,
        },
      },
      handler: async (params) => {
        const target = String(params.target ?? '').trim();
        if (!target) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.paramRequired', {
              param: 'target',
            }),
            error_type: 'invalid_input',
          };
        }

        const currentRoute = router.currentRoute.value;
        const entries = buildMenuNavigationEntries({
          currentEndpoint: getEndpointFromPath(currentRoute.path),
          menus: getAccessibleMenusSafe(),
          translate: $t,
        });
        const resolution = resolveMenuNavigationTarget({
          currentPageKey: normalizedKey,
          currentPath: currentRoute.path,
          entries,
          target,
        });

        if (resolution.kind === 'not_found') {
          const candidates = searchMenuNavigationEntries(entries, target).slice(0, 5);
          return {
            success: false,
            message: $t('shared.pageOperation.msg.menuTargetNotFound', {
              target,
            }),
            error_type: 'not_found',
            data: candidates.length
              ? {
                  candidates: candidates.map((entry) =>
                    serializeMenuNavigationEntry(entry),
                  ),
                }
              : undefined,
          };
        }

        if (resolution.kind === 'ambiguous_match') {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.menuTargetAmbiguous', {
              target,
            }),
            error_type: 'ambiguous_match',
            data: {
              candidates: resolution.candidates.map((entry) =>
                serializeMenuNavigationEntry(entry),
              ),
            },
          };
        }

        const result = await navigateToMenuEntry(resolution.entry);
        if (!result.success) {
          return {
            success: false,
            message:
              result.error_type === 'permission_denied'
                ? $t('shared.pageOperation.msg.menuPermissionDenied', {
                    path: resolution.entry.path,
                  })
                : $t('shared.pageOperation.msg.menuNavigationBlocked', {
                    path: resolution.entry.path,
                  }),
            error_type: result.error_type,
          };
        }

        if (resolution.kind === 'already_on_page') {
          return {
            success: true,
            message: $t('shared.pageOperation.msg.alreadyOnPage', {
              path: resolution.entry.path,
            }),
            data: result.data,
          };
        }

        return {
          success: true,
          message:
            result.data?.destination_ready === false
              ? $t('shared.pageOperation.msg.navigatedToPending', {
                  path: resolution.entry.path,
                })
              : $t('shared.pageOperation.msg.navigatedTo', {
                  path: resolution.entry.path,
                }),
          data: result.data,
        };
      },
    },
    {
      name: 'capture_screenshot',
      label: $t('shared.pageOperation.captureScreenshot'),
      description:
        'Capture the current visible page as an image for visual inspection. Use this only when page context, DOM structure, or table/form data is insufficient, and avoid repeated screenshots unless the page changed visually / 截取当前可见页面作为图片供视觉分析。仅在页面上下文、DOM 结构或表单表格数据不足时使用；除非页面视觉状态明显变化，否则避免重复截图',
      readonly: true,
      handler: async () => {
        const result = await capturePageScreenshot({
          ...resolveScreenshotUploadTarget(),
          excludeSelectors: [...DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS],
        });

        if (!result) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.screenshotFailed'),
            error_type: 'capture_failed',
          };
        }

        return {
          success: true,
          message: $t('shared.pageOperation.msg.screenshotCaptured'),
          data: {
            attachment: {
              attachment_id: result.attachment.attachment_id,
              type: result.attachment.type,
              url: result.attachment.url,
              name: result.attachment.name,
              mime_type: result.attachment.mime_type,
            },
            capture_scope: 'viewport',
            page_key: normalizedKey,
            viewport: {
              height: window.innerHeight,
              width: window.innerWidth,
            },
          },
        };
      },
    },
  ];
}
