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

export const ANTD_BUTTON_ADAPTER_ID = 'antd-button';

function createButtonNode(
  element: HTMLElement,
  priority: number,
): null | UIGraphNode {
  if (!isElementVisible(element)) {
    return null;
  }
  const locator = buildElementLocator(element);
  return {
    adapterId: ANTD_BUTTON_ADAPTER_ID,
    disabled:
      element.hasAttribute('disabled') ||
      element.getAttribute('aria-disabled') === 'true',
    id: `adapter:button:${locator}`,
    kind: 'button',
    label: readElementLabel(element),
    locator,
    metadata: {
      className: element.className,
      tag: element.tagName.toLowerCase(),
    },
    priority,
    source: 'adapter',
    visible: true,
  };
}

export function createAntdButtonAdapter(priority = 50): UIComponentAdapter {
  return {
    id: ANTD_BUTTON_ADAPTER_ID,
    priority,
    collect(context): UIAdapterResult {
      const nodes: UIGraphNode[] = [];
      const seen = new Set<string>();
      context.root
        .querySelectorAll<HTMLElement>(
          'button.ant-btn, .ant-btn[role="button"]',
        )
        .forEach((element) => {
          const node = createButtonNode(element, priority);
          if (!node) {
            return;
          }
          if (seen.has(node.locator)) {
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
