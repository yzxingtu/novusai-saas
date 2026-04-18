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

export const ANTD_TABS_ADAPTER_ID = 'antd-tabs';

function toTabNode(element: HTMLElement, priority: number): null | UIGraphNode {
  if (!isElementVisible(element)) {
    return null;
  }
  const locator = buildElementLocator(element);
  return {
    adapterId: ANTD_TABS_ADAPTER_ID,
    disabled: element.getAttribute('aria-disabled') === 'true',
    id: `adapter:tab:${locator}`,
    kind: 'tab',
    label: readElementLabel(element),
    locator,
    metadata: {
      active: element.classList.contains('ant-tabs-tab-active'),
    },
    priority,
    source: 'adapter',
    visible: true,
  };
}

export function createAntdTabsAdapter(priority = 60): UIComponentAdapter {
  return {
    id: ANTD_TABS_ADAPTER_ID,
    priority,
    collect(context): UIAdapterResult {
      const nodes: UIGraphNode[] = [];
      const seen = new Set<string>();
      context.root
        .querySelectorAll<HTMLElement>('.ant-tabs-tab')
        .forEach((element) => {
          const node = toTabNode(element, priority);
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
