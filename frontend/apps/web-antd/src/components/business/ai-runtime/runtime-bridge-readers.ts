import type { UISnapshot } from './ui-snapshot-generator';

import { tAiRuntime } from './i18n';
import {
  normalizeText,
  queryElementByLocator,
  readFormLikeElementValue,
} from './runtime-bridge-core';
import { buildSnapshot } from './runtime-bridge-snapshot';
import { readValueForAI, resolveAISecurityPolicy } from './security-policy';

function findSurfaceIdForElement(
  element: HTMLElement,
  snapshot: UISnapshot,
): string | undefined {
  const selectors: Array<[string, UISnapshot['surface_stack'][number]['kind']]> = [
    ['.ant-popover', 'popover'],
    ['.ant-dropdown, .ant-select-dropdown', 'dropdown'],
    ['.ant-modal, .ant-modal-wrap, [role="dialog"]', 'modal'],
    ['.ant-drawer, .ant-drawer-content-wrapper, .ant-drawer-content', 'drawer'],
  ];
  for (const [selector, kind] of selectors) {
    if (!element.closest(selector)) {
      continue;
    }
    for (let index = snapshot.surface_stack.length - 1; index >= 0; index -= 1) {
      const surface = snapshot.surface_stack[index];
      if (surface?.kind === kind) {
        return surface.surface_id;
      }
    }
  }
  return snapshot.active_surface_id || snapshot.surface_stack[0]?.surface_id;
}

function readElementText(element: HTMLElement): string | undefined {
  const decision = resolveAISecurityPolicy({
    element,
    fieldName: element.getAttribute('name') || undefined,
    fieldType:
      element instanceof HTMLInputElement ||
      element instanceof HTMLTextAreaElement ||
      element instanceof HTMLSelectElement
        ? element.type || undefined
        : undefined,
  });
  if (
    element instanceof HTMLInputElement ||
    element instanceof HTMLTextAreaElement ||
    element instanceof HTMLSelectElement
  ) {
    const value = readValueForAI(readFormLikeElementValue(element), decision);
    return typeof value === 'string' ? normalizeText(value, 4000) : undefined;
  }
  const value = readValueForAI(
    element.innerText || element.textContent || '',
    decision,
  );
  return typeof value === 'string' ? normalizeText(value, 4000) : undefined;
}

function readRegionItems(
  element: HTMLElement,
): Array<{ label?: string; value?: string }> {
  const items: Array<{ label?: string; value?: string }> = [];
  const labels = element.querySelectorAll<HTMLElement>('label,[data-label],dt,th');
  labels.forEach((labelElement) => {
    if (items.length >= 50) {
      return;
    }
    const label = normalizeText(
      labelElement.getAttribute('data-label') ||
        labelElement.innerText ||
        labelElement.textContent ||
        '',
      200,
    );
    if (!label) {
      return;
    }
    const sibling =
      labelElement.nextElementSibling instanceof HTMLElement
        ? labelElement.nextElementSibling
        : null;
    const value = sibling ? readElementText(sibling) : undefined;
    items.push({
      ...(label ? { label } : {}),
      ...(value ? { value } : {}),
    });
  });
  return items;
}

function filterTableCells(cells: HTMLElement[]): string[] {
  return cells
    .map((cell) => normalizeText(cell.innerText || cell.textContent || '', 240))
    .filter(Boolean);
}

export function readRuntimeRegion(locator: string): Record<string, unknown> {
  const element = queryElementByLocator(locator);
  if (!element) {
    throw new Error(tAiRuntime('regionLocatorNotFound', { locator }));
  }
  const snapshot = buildSnapshot('compact').snapshot;
  const title =
    normalizeText(
      element.getAttribute('aria-label') ||
        element.getAttribute('title') ||
        element.querySelector('h1,h2,h3,h4,.ant-card-head-title')?.textContent ||
        '',
      200,
    ) || undefined;
  return {
    items: readRegionItems(element),
    region_locator: locator,
    surface_id: findSurfaceIdForElement(element, snapshot),
    text: readElementText(element),
    title,
    truncated: false,
  };
}

export function readRuntimeTable(args: {
  locator: string;
  page?: number;
  pageSize?: number;
}): Record<string, unknown> {
  const element = queryElementByLocator(args.locator);
  const table = element?.matches('table') ? element : element?.querySelector('table');
  if (!(table instanceof HTMLTableElement)) {
    throw new Error(tAiRuntime('tableLocatorNotFound', { locator: args.locator }));
  }
  const snapshot = buildSnapshot('compact').snapshot;
  const page = Math.max(args.page ?? 1, 1);
  const pageSize = Math.max(Math.min(args.pageSize ?? 20, 100), 1);
  const headerCells = filterTableCells(
    Array.from(table.querySelectorAll<HTMLElement>('thead th')),
  );
  const headers =
    headerCells.length > 0
      ? headerCells
      : filterTableCells(
          Array.from(table.querySelectorAll<HTMLElement>('tbody tr:first-child td')),
        );
  const allRows = Array.from(table.querySelectorAll<HTMLTableRowElement>('tbody tr'));
  const startIndex = (page - 1) * pageSize;
  const rows = allRows.slice(startIndex, startIndex + pageSize).map((row) => {
    const cells = Array.from(row.querySelectorAll<HTMLElement>('td'));
    const values = filterTableCells(cells);
    const normalizedRow: Record<string, unknown> = {};
    values.forEach((value, index) => {
      normalizedRow[headers[index] || `column_${index + 1}`] = value;
    });
    return normalizedRow;
  });
  return {
    columns: headers,
    has_more: startIndex + rows.length < allRows.length,
    page,
    page_size: pageSize,
    rows,
    surface_id: snapshot.active_surface_id,
    table_locator: args.locator,
    total_rows: allRows.length,
    truncated: false,
  };
}

export function listRuntimeInteractables(
  surfaceId?: string,
): Record<string, unknown> {
  const snapshot = buildSnapshot('compact').snapshot;
  const items = snapshot.nodes
    .filter(
      (node) =>
        node.interactable ||
        ['button', 'input', 'link', 'select', 'tab'].includes(node.kind),
    )
    .filter((node) => !surfaceId || node.surface_id === surfaceId)
    .map((node) => {
      const element = queryElementByLocator(node.locator || '');
      const decision = resolveAISecurityPolicy({
        actionKind: node.kind === 'button' ? 'click' : node.kind,
        element,
      });
      return {
        enabled: !node.kind || decision.canAct,
        kind: node.kind,
        label: node.summary,
        locator: node.locator,
        requires_confirmation: decision.requireConfirm,
        surface_id: node.surface_id,
      };
    })
    .slice(0, 200);
  return {
    count: items.length,
    items,
    surface_id: surfaceId,
    truncated: snapshot.nodes.length > items.length,
  };
}
