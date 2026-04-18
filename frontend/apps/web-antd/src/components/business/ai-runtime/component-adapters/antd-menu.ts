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

export const ANTD_MENU_ADAPTER_ID = 'antd-menu';

function toMenuNode(
  element: HTMLElement,
  priority: number,
): null | UIGraphNode {
  if (!isElementVisible(element)) {
    return null;
  }
  const locator = buildElementLocator(element);
  return {
    adapterId: ANTD_MENU_ADAPTER_ID,
    disabled:
      element.classList.contains('ant-menu-item-disabled') ||
      element.getAttribute('aria-disabled') === 'true',
    id: `adapter:menu-item:${locator}`,
    kind: 'menu-item',
    label: readElementLabel(element),
    locator,
    metadata: {
      selected: element.classList.contains('ant-menu-item-selected'),
    },
    priority,
    source: 'adapter',
    visible: true,
  };
}

export function createAntdMenuAdapter(priority = 65): UIComponentAdapter {
  return {
    id: ANTD_MENU_ADAPTER_ID,
    priority,
    collect(context): UIAdapterResult {
      const nodes: UIGraphNode[] = [];
      const seen = new Set<string>();
      context.root
        .querySelectorAll<HTMLElement>(
          '.ant-menu .ant-menu-item, .ant-menu [role="menuitem"]',
        )
        .forEach((element) => {
          const node = toMenuNode(element, priority);
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
