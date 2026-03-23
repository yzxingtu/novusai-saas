import type { PageOperation } from './page-operation-registry';

import { $t } from '#/locales';
import {
  capturePageScreenshot,
  DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS,
  resolveScreenshotUploadTarget,
} from '#/composables/use-page-screenshot';

import { scanDomSemantics } from './dom-semantic-scanner';
import { resolvePageContext } from './page-context-registry';
import { normalizePageKey } from './page-key-utils';

function buildPageDataPreview(
  pageData: Record<string, unknown> | undefined,
): Record<string, unknown> | undefined {
  if (!pageData) return undefined;

  const {
    available_operations: _availableOperations,
    form_fields: _formFields,
    visual_state: _visualState,
    ...rest
  } = pageData;

  const preview: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(rest)) {
    if (value === undefined || value === null || value === '') continue;
    if (typeof value === 'string') {
      preview[key] = value.length > 240 ? `${value.slice(0, 240)}...` : value;
      continue;
    }
    preview[key] = value;
  }

  return Object.keys(preview).length > 0 ? preview : undefined;
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
                forms: domSnapshot.forms,
                page_title: domSnapshot.page_title,
                tables: domSnapshot.tables,
                tabs: domSnapshot.tabs,
              }
            : { page_title: normalizedKey },
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
