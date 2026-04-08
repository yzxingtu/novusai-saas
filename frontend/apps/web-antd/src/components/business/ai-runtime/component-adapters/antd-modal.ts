import { isElementVisible } from '../dom-scanner';
import { tAiRuntime } from '../i18n';
import type { UIAdapterResult, UIComponentAdapter } from '../types';

export const ANTD_MODAL_ADAPTER_ID = 'antd-modal';

function resolveModalKey(element: HTMLElement, index: number): string {
  const candidate =
    element.getAttribute('data-ai-surface-id') ??
    element.getAttribute('data-testid') ??
    element.getAttribute('id');
  if (candidate) {
    return `modal:${candidate}`;
  }
  return `modal:antd:${index}`;
}

function resolveModalTitle(element: HTMLElement): string {
  const titleNode = element.querySelector('.ant-modal-title');
  const title = titleNode?.textContent?.replaceAll(/\s+/g, ' ').trim();
  return title || tAiRuntime('surfaceTitle.modal', { index: 1 });
}

export function createAntdModalAdapter(priority = 80): UIComponentAdapter {
  return {
    id: ANTD_MODAL_ADAPTER_ID,
    priority,
    collect(context): UIAdapterResult {
      const overlays: NonNullable<UIAdapterResult['overlays']> = [];
      let index = 0;
      context.document
        .querySelectorAll<HTMLElement>('.ant-modal-root .ant-modal-wrap, .ant-modal')
        .forEach((element) => {
          if (!isElementVisible(element)) {
            return;
          }
          index += 1;
          overlays.push({
            key: resolveModalKey(element, index),
            kind: 'modal',
            metadata: {
              adapter: ANTD_MODAL_ADAPTER_ID,
            },
            title: resolveModalTitle(element),
          });
        });
      return {
        overlays,
      };
    },
  };
}
