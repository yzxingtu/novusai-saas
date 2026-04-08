import { isElementVisible } from '../dom-scanner';
import { tAiRuntime } from '../i18n';
import type { UIAdapterResult, UIComponentAdapter } from '../types';

export const ANTD_DRAWER_ADAPTER_ID = 'antd-drawer';

function resolveDrawerKey(element: HTMLElement, index: number): string {
  const candidate =
    element.getAttribute('data-ai-surface-id') ??
    element.getAttribute('data-testid') ??
    element.getAttribute('id');
  if (candidate) {
    return `drawer:${candidate}`;
  }
  return `drawer:antd:${index}`;
}

function resolveDrawerTitle(element: HTMLElement): string {
  const titleNode = element.querySelector('.ant-drawer-title');
  const title = titleNode?.textContent?.replaceAll(/\s+/g, ' ').trim();
  return title || tAiRuntime('surfaceTitle.drawer', { index: 1 });
}

export function createAntdDrawerAdapter(priority = 75): UIComponentAdapter {
  return {
    id: ANTD_DRAWER_ADAPTER_ID,
    priority,
    collect(context): UIAdapterResult {
      const overlays: NonNullable<UIAdapterResult['overlays']> = [];
      let index = 0;
      context.document
        .querySelectorAll<HTMLElement>(
          '.ant-drawer-content-wrapper, .ant-drawer-content',
        )
        .forEach((element) => {
          if (!isElementVisible(element)) {
            return;
          }
          index += 1;
          overlays.push({
            key: resolveDrawerKey(element, index),
            kind: 'drawer',
            metadata: {
              adapter: ANTD_DRAWER_ADAPTER_ID,
            },
            title: resolveDrawerTitle(element),
          });
        });
      return {
        overlays,
      };
    },
  };
}
