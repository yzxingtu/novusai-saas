import type {
  UIAdapterResult,
  UIComponentAdapter,
  UIGraphNode,
} from '../types';

import {
  buildElementLocator,
  isElementVisible,
  readElementLabel,
} from '../dom-scanner';

export const ANTD_PAGINATION_ADAPTER_ID = 'antd-pagination';

function resolvePaginationLabel(element: HTMLElement): string | undefined {
  const explicit = readElementLabel(element);
  if (explicit) {
    return explicit;
  }
  if (element.classList.contains('ant-pagination-prev')) {
    return 'Previous page';
  }
  if (element.classList.contains('ant-pagination-next')) {
    return 'Next page';
  }
  return undefined;
}

function toPaginationNode(
  element: HTMLElement,
  priority: number,
): null | UIGraphNode {
  if (!isElementVisible(element)) {
    return null;
  }
  const locator = buildElementLocator(element);
  return {
    adapterId: ANTD_PAGINATION_ADAPTER_ID,
    disabled:
      element.classList.contains('ant-pagination-disabled') ||
      element.getAttribute('aria-disabled') === 'true',
    id: `adapter:pagination:${locator}`,
    kind: 'button',
    label: resolvePaginationLabel(element),
    locator,
    metadata: {
      active:
        element.classList.contains('ant-pagination-item-active') ||
        element.getAttribute('aria-current') === 'page',
      page: readElementLabel(element),
    },
    priority,
    source: 'adapter',
    visible: true,
  };
}

export function createAntdPaginationAdapter(priority = 58): UIComponentAdapter {
  return {
    id: ANTD_PAGINATION_ADAPTER_ID,
    priority,
    collect(context): UIAdapterResult {
      const nodes: UIGraphNode[] = [];
      const seen = new Set<string>();
      context.root
        .querySelectorAll<HTMLElement>(
          '.ant-pagination .ant-pagination-item, .ant-pagination .ant-pagination-prev, .ant-pagination .ant-pagination-next',
        )
        .forEach((element) => {
          const node = toPaginationNode(element, priority);
          if (!node || seen.has(node.locator)) {
            return;
          }
          seen.add(node.locator);
          nodes.push(node);
        });
      return {
        nodes,
      };
    },
  };
}
