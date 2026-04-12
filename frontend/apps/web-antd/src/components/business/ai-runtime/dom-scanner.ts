import type {
  DOMScanInput,
  DOMScanMode,
  DOMScanResult,
  DOMScannerOptions,
  UIGraphNode,
  UINodeKind,
  UIOverlaySurfaceInput,
} from './types';

import { tAiRuntime } from './i18n';

const DEFAULT_DOM_SCANNER_OPTIONS: DOMScannerOptions = {
  maxDepth: 6,
  maxNodes: 160,
  textMaxLength: 120,
  visibleOnly: true,
};

const INTERACTABLE_SELECTOR = [
  'button',
  'a[href]',
  'input',
  'select',
  'textarea',
  '[role="button"]',
  '[role="menuitem"]',
  '[role="tab"]',
].join(',');

const AI_PANEL_SELECTOR = '[data-ai-panel]';

function nowInMs(): number {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now();
  }
  return Date.now();
}

function readTrimmedText(text: null | string | undefined, maxLength: number): string {
  return (text ?? '').replaceAll(/\s+/g, ' ').trim().slice(0, maxLength);
}

function toAttrValue(value: string): string {
  return value.replaceAll('\\', '\\\\').replaceAll('"', '\\"');
}

export function isElementVisible(element: HTMLElement): boolean {
  if (element.hidden) {
    return false;
  }
  if (element.getAttribute('aria-hidden') === 'true') {
    return false;
  }
  const style = element.getAttribute('style') ?? '';
  if (style.includes('display:none') || style.includes('visibility:hidden')) {
    return false;
  }
  const className = element.className;
  if (typeof className === 'string') {
    if (
      className.includes('hidden') ||
      className.includes('ant-modal-hidden') ||
      className.includes('ant-dropdown-hidden') ||
      className.includes('ant-popover-hidden')
    ) {
      return false;
    }
  }
  return true;
}

function isAIExcluded(element: Element): boolean {
  let cursor: null | Element = element;
  while (cursor) {
    if (cursor.matches(AI_PANEL_SELECTOR)) {
      return true;
    }
    const dataAI = cursor.getAttribute('data-ai');
    if (typeof dataAI === 'string') {
      const hasOffDirective = dataAI
        .split(/\s+/)
        .some((token) => token.trim().toLocaleLowerCase() === 'off');
      if (hasOffDirective) {
        return true;
      }
    }
    cursor = cursor.parentElement;
  }
  return false;
}

export function buildElementLocator(element: Element): string {
  const aiId = element.getAttribute('data-ai-id');
  if (aiId) {
    return `[data-ai-id="${toAttrValue(aiId)}"]`;
  }
  const testId = element.getAttribute('data-testid');
  if (testId) {
    return `[data-testid="${toAttrValue(testId)}"]`;
  }
  const elementId = element.getAttribute('id');
  if (elementId) {
    return `#${toAttrValue(elementId)}`;
  }
  const name = element.getAttribute('name');
  if (name) {
    return `${element.tagName.toLowerCase()}[name="${toAttrValue(name)}"]`;
  }
  const ariaLabel = element.getAttribute('aria-label');
  if (ariaLabel) {
    return `${element.tagName.toLowerCase()}[aria-label="${toAttrValue(ariaLabel)}"]`;
  }
  return buildPathLocator(element);
}

export function inferNodeKindFromElement(element: Element): UINodeKind {
  const tag = element.tagName.toLowerCase();
  const role = element.getAttribute('role');
  const className = element.className;
  const classText = typeof className === 'string' ? className : '';

  if (classText.includes('ant-menu-item') || role === 'menuitem') {
    return 'menu-item';
  }
  if (classText.includes('ant-tabs-tab') || role === 'tab') {
    return 'tab';
  }
  if (tag === 'a') {
    return 'link';
  }
  if (tag === 'textarea') {
    return 'textarea';
  }
  if (tag === 'input') {
    const inputType = element.getAttribute('type') ?? 'text';
    if (inputType === 'checkbox') {
      return 'checkbox';
    }
    if (inputType === 'radio') {
      return 'radio';
    }
    return 'input';
  }
  if (tag === 'select') {
    return 'select';
  }
  if (tag === 'button' || role === 'button' || classText.includes('ant-btn')) {
    return 'button';
  }
  return 'button';
}

export function readElementLabel(
  element: Element,
  maxLength = DEFAULT_DOM_SCANNER_OPTIONS.textMaxLength,
): string | undefined {
  const attrCandidates = [
    element.getAttribute('aria-label'),
    element.getAttribute('title'),
    element.getAttribute('placeholder'),
  ];
  const attrText = attrCandidates
    .map((value) => readTrimmedText(value, maxLength))
    .find((value) => value.length > 0);
  if (attrText) {
    return attrText;
  }
  const contentText = readTrimmedText(element.textContent, maxLength);
  return contentText || undefined;
}

function buildPathLocator(element: Element): string {
  const parts: string[] = [];
  let cursor: null | Element = element;
  let depth = 0;
  while (cursor && depth < 4) {
    const tag = cursor.tagName.toLowerCase();
    const parentElement: Element | null = cursor.parentElement;
    if (!parentElement) {
      parts.unshift(tag);
      break;
    }
    const siblings = Array.from(parentElement.children).filter(
      (candidate: Element) => candidate.tagName === cursor?.tagName,
    );
    if (siblings.length <= 1) {
      parts.unshift(tag);
    } else {
      const index = siblings.indexOf(cursor) + 1;
      parts.unshift(`${tag}:nth-of-type(${index})`);
    }
    cursor = parentElement;
    depth += 1;
  }
  return parts.join(' > ');
}

function isDisabled(element: Element): boolean {
  if (!('hasAttribute' in element)) {
    return false;
  }
  if (element.hasAttribute('disabled') || element.getAttribute('aria-disabled') === 'true') {
    return true;
  }
  return false;
}

function resolveRoot(input: DOMScanInput): ParentNode {
  if (input.root instanceof Element) {
    return input.root;
  }
  return input.document.body ?? input.document;
}

function createNodeFromElement(
  element: Element,
  maxLength: number,
  activeSurfaceId: null | string,
): UIGraphNode {
  const locator = buildElementLocator(element);
  const kind = inferNodeKindFromElement(element);
  return {
    adapterId: undefined,
    disabled: isDisabled(element),
    id: `dom:${kind}:${locator}`,
    kind,
    label: readElementLabel(element, maxLength),
    locator,
    metadata: {
      tag: element.tagName.toLowerCase(),
    },
    source: 'dom-fallback',
    surfaceId: activeSurfaceId ?? undefined,
    visible: !(element instanceof HTMLElement) || isElementVisible(element),
  };
}

function uniqueNodeKey(node: UIGraphNode): string {
  return `${node.kind}|${node.locator}`;
}

function readSurfaceTitle(element: Element, fallback: string, maxLength: number): string {
  const selectors = [
    '.ant-modal-title',
    '.ant-drawer-title',
    '.ant-popover-title',
    '[aria-label]',
    '[title]',
  ];
  for (const selector of selectors) {
    const target = element.querySelector(selector);
    const labelText = target?.getAttribute('aria-label') ?? target?.getAttribute('title');
    const text = readTrimmedText(target?.textContent ?? labelText, maxLength);
    if (text) {
      return text;
    }
  }
  return fallback;
}

function buildOverlayKey(kind: UIOverlaySurfaceInput['kind'], element: Element, index: number): string {
  const candidate =
    element.getAttribute('data-ai-surface-id') ??
    element.getAttribute('data-testid') ??
    element.getAttribute('id');
  if (candidate) {
    return `${kind}:${candidate}`;
  }
  return `${kind}:dom:${index}`;
}

function collectOverlays(document: Document, maxLength: number): UIOverlaySurfaceInput[] {
  const overlays: UIOverlaySurfaceInput[] = [];
  const definitions: Array<{
    fallbackTitle: string;
    kind: UIOverlaySurfaceInput['kind'];
    selector: string;
  }> = [
    {
      fallbackTitle: tAiRuntime('surfaceTitle.modal', { index: 1 }),
      kind: 'modal',
      selector: '.ant-modal-root .ant-modal-wrap, .ant-modal',
    },
    {
      fallbackTitle: tAiRuntime('surfaceTitle.drawer', { index: 1 }),
      kind: 'drawer',
      selector: '.ant-drawer-content-wrapper, .ant-drawer-content',
    },
    {
      fallbackTitle: tAiRuntime('surfaceTitle.dropdown', { index: 1 }),
      kind: 'dropdown',
      selector: '.ant-dropdown, .ant-select-dropdown',
    },
    {
      fallbackTitle: tAiRuntime('surfaceTitle.popover', { index: 1 }),
      kind: 'popover',
      selector: '.ant-popover',
    },
  ];
  const seen = new Set<string>();

  definitions.forEach((definition) => {
    const elements = document.querySelectorAll(definition.selector);
    let index = 0;
    elements.forEach((element) => {
      if (!(element instanceof HTMLElement)) {
        return;
      }
      if (!isElementVisible(element)) {
        return;
      }
      if (isAIExcluded(element)) {
        return;
      }
      index += 1;
      const key = buildOverlayKey(definition.kind, element, index);
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      overlays.push({
        key,
        kind: definition.kind,
        title: readSurfaceTitle(element, definition.fallbackTitle, maxLength),
      });
    });
  });

  return overlays;
}

export class DOMScanner {
  private readonly options: DOMScannerOptions;

  constructor(options: Partial<DOMScannerOptions> = {}) {
    this.options = {
      ...DEFAULT_DOM_SCANNER_OPTIONS,
      ...options,
    };
  }

  scan(input: DOMScanInput, mode: DOMScanMode = 'full'): DOMScanResult {
    const start = nowInMs();
    const overlays = collectOverlays(input.document, this.options.textMaxLength);
    if (mode === 'surfaces-only') {
      return {
        durationMs: nowInMs() - start,
        mode,
        nodes: [],
        overlays,
        scannedElements: 0,
        truncated: false,
      };
    }

    const root = resolveRoot(input);
    const queue: Array<{ depth: number; element: Element }> = [];
    const nodes: UIGraphNode[] = [];
    const seen = new Set<string>();
    let scannedElements = 0;
    let truncated = false;

    if (root instanceof Element) {
      queue.push({
        depth: 0,
        element: root,
      });
    } else if ('body' in input.document && input.document.body) {
      queue.push({
        depth: 0,
        element: input.document.body,
      });
    }

    while (queue.length > 0) {
      const current = queue.shift();
      if (!current) {
        break;
      }

      const { depth, element } = current;
      if (isAIExcluded(element)) {
        continue;
      }
      scannedElements += 1;
      const isVisible = !(element instanceof HTMLElement) || isElementVisible(element);

      if (
        element.matches(INTERACTABLE_SELECTOR) &&
        (!this.options.visibleOnly || isVisible)
      ) {
        const node = createNodeFromElement(
          element,
          this.options.textMaxLength,
          input.activeSurfaceId ?? null,
        );
        const key = uniqueNodeKey(node);
        if (!seen.has(key)) {
          seen.add(key);
          nodes.push(node);
        }
      }

      if (nodes.length >= this.options.maxNodes) {
        truncated = true;
        break;
      }

      if (depth >= this.options.maxDepth) {
        continue;
      }

      const children = Array.from(element.children);
      children.forEach((child) => {
        if (!(child instanceof Element)) {
          return;
        }
        if (isAIExcluded(child)) {
          return;
        }
        if (
          this.options.visibleOnly &&
          child instanceof HTMLElement &&
          !isElementVisible(child)
        ) {
          return;
        }
        queue.push({
          depth: depth + 1,
          element: child,
        });
      });
    }

    return {
      durationMs: nowInMs() - start,
      mode,
      nodes,
      overlays,
      scannedElements,
      truncated,
    };
  }
}
