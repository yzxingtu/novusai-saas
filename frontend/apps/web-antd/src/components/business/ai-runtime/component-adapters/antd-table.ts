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

export const ANTD_TABLE_ADAPTER_ID = 'antd-table';

function findTableContainer(element: HTMLTableElement): HTMLElement {
  let cursor: HTMLElement | null = element;
  let structuralFallback: HTMLElement | null = null;
  while (cursor) {
    if (
      Object.hasOwn(cursor.dataset, 'aiId') ||
      Object.hasOwn(cursor.dataset, 'testid') ||
      Object.hasOwn(cursor.dataset, 'aiTable')
    ) {
      return cursor;
    }
    if (
      !structuralFallback &&
      cursor.matches('.ant-table-wrapper, .ant-table, .vxe-table')
    ) {
      structuralFallback = cursor;
    }
    cursor = cursor.parentElement;
  }
  return structuralFallback ?? element;
}

function toTableNode(
  element: HTMLTableElement,
  priority: number,
): null | UIGraphNode {
  const container = findTableContainer(element);
  if (!isElementVisible(element) || !isElementVisible(container)) {
    return null;
  }
  const locator = buildElementLocator(container);
  const rowCount = element.querySelectorAll('tbody tr').length;
  const headColumnCount = element.querySelectorAll('thead th').length;
  const bodyColumnCount = element.querySelectorAll(
    'tbody tr:first-child td',
  ).length;
  const columnCount = headColumnCount || bodyColumnCount;
  return {
    adapterId: ANTD_TABLE_ADAPTER_ID,
    disabled: false,
    id: `adapter:table:${locator}`,
    kind: 'table',
    label:
      readElementLabel(container) ||
      readElementLabel(element) ||
      `Table (${Math.max(rowCount, 0)}x${Math.max(columnCount, 0)})`,
    locator,
    metadata: {
      columnCount,
      rowCount,
      tag: element.tagName.toLowerCase(),
    },
    priority,
    source: 'adapter',
    visible: true,
  };
}

export function createAntdTableAdapter(priority = 68): UIComponentAdapter {
  return {
    id: ANTD_TABLE_ADAPTER_ID,
    priority,
    collect(context): UIAdapterResult {
      const nodes: UIGraphNode[] = [];
      const seen = new Set<string>();
      context.root
        .querySelectorAll<HTMLTableElement>(
          '.ant-table-wrapper table, .ant-table table, .vxe-table table, table',
        )
        .forEach((element) => {
          const node = toTableNode(element, priority);
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
