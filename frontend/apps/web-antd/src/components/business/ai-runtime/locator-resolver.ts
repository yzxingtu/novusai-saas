import { tAiRuntime } from './i18n';

export type UIInteractableKind =
  | 'button'
  | 'generic'
  | 'link'
  | 'menu_item'
  | 'pagination'
  | 'tab';

export type LocatorResolutionErrorCode =
  | 'ambiguous'
  | 'invalid_locator'
  | 'not_found';

export interface LocatorCandidate {
  disabled: boolean;
  kind: UIInteractableKind;
  label: string;
  locator: string;
  score: number;
}

export interface LocatorResolution {
  candidate: LocatorCandidate;
  element: HTMLElement;
}

export interface ResolveLocatorOptions {
  allowFuzzy?: boolean;
  candidateLimit?: number;
}

export interface LocatorResolverOptions {
  candidateLimit?: number;
  fuzzyThreshold?: number;
  includeHidden?: boolean;
  root?: ParentNode;
}

interface CandidateRecord {
  candidate: LocatorCandidate;
  element: HTMLElement;
  searchable: Set<string>;
}

const INTERACTABLE_SELECTOR = [
  'button',
  'a[href]',
  '[role="button"]',
  '[role="link"]',
  '[role="menuitem"]',
  '[role="tab"]',
  '.ant-menu-item',
  '.ant-dropdown-menu-item',
  '.ant-tabs-tab',
  '.ant-pagination-item',
  '.ant-pagination-prev',
  '.ant-pagination-next',
].join(', ');

const SEMANTIC_HINTS: Record<UIInteractableKind, string[]> = {
  button: ['button', 'btn', '按钮', '提交', '确认', '保存', '创建'],
  generic: [],
  link: ['link', 'href', '链接', '跳转'],
  menu_item: ['menu', '菜单', '导航', '入口'],
  pagination: ['page', 'pagination', 'next', 'prev', '分页', '下一页', '上一页'],
  tab: ['tab', '标签', '选项卡'],
};

function normalizeText(value: string): string {
  return value.replaceAll(/\s+/g, ' ').trim();
}

function normalizeQuery(value: string): string {
  return normalizeText(value).toLocaleLowerCase();
}

function compactText(value: string): string {
  return value.replaceAll(/\s+/g, '');
}

function looksLikeCssSelector(locator: string): boolean {
  return /^[#.[]/.test(locator) || locator.includes('>');
}

function escapeSelectorValue(value: string): string {
  const escaper =
    typeof CSS !== 'undefined' && typeof CSS.escape === 'function'
      ? CSS.escape
      : (raw: string) => raw.replaceAll('"', '\\"');
  return escaper(value);
}

function isElementVisible(element: HTMLElement): boolean {
  if (element.hidden) {
    return false;
  }
  const style = window.getComputedStyle(element);
  if (style.display === 'none' || style.visibility === 'hidden') {
    return false;
  }
  return element.getClientRects().length > 0 || style.opacity !== '0';
}

function isElementDisabled(element: HTMLElement): boolean {
  if ('disabled' in element && element.disabled) {
    return true;
  }
  const ariaDisabled = element.getAttribute('aria-disabled');
  if (ariaDisabled === 'true') {
    return true;
  }
  return element.classList.contains('ant-btn-disabled');
}

function resolveElementLabel(element: HTMLElement): string {
  const preferred =
    element.getAttribute('data-ai-label') ||
    element.getAttribute('aria-label') ||
    element.getAttribute('title') ||
    element.getAttribute('name');
  if (preferred) {
    return normalizeText(preferred).slice(0, 120);
  }

  if (
    element instanceof HTMLInputElement ||
    element instanceof HTMLTextAreaElement
  ) {
    return normalizeText(
      element.placeholder || element.name || element.id || element.value || '',
    ).slice(0, 120);
  }

  return normalizeText(element.textContent || '').slice(0, 120);
}

function detectKind(element: HTMLElement): UIInteractableKind {
  const role = (element.getAttribute('role') || '').toLocaleLowerCase();
  const className = element.className || '';
  const tagName = element.tagName.toLocaleLowerCase();

  if (
    role === 'menuitem' ||
    className.includes('ant-menu-item') ||
    className.includes('ant-dropdown-menu-item')
  ) {
    return 'menu_item';
  }
  if (role === 'tab' || className.includes('ant-tabs-tab')) {
    return 'tab';
  }
  if (
    className.includes('ant-pagination') ||
    element.closest('.ant-pagination')
  ) {
    return 'pagination';
  }
  if (role === 'link' || tagName === 'a') {
    return 'link';
  }
  if (role === 'button' || tagName === 'button') {
    return 'button';
  }
  return 'generic';
}

function fallbackLocatorByDomPath(element: HTMLElement): string {
  if (element.id) {
    return `id:${element.id}`;
  }
  const tag = element.tagName.toLocaleLowerCase();
  const index = Array.from(
    element.parentElement?.querySelectorAll(tag) || [],
  ).indexOf(element);
  return `css:${tag}:nth-of-type(${Math.max(index + 1, 1)})`;
}

function buildLocator(element: HTMLElement): string {
  const aiId = element.getAttribute('data-ai-id');
  if (aiId) {
    return `ai-id:${aiId}`;
  }
  const testId = element.getAttribute('data-testid');
  if (testId) {
    return `testid:${testId}`;
  }
  if (element.id) {
    return `id:${element.id}`;
  }
  const name = element.getAttribute('name');
  if (name) {
    return `name:${name}`;
  }
  if (element instanceof HTMLAnchorElement && element.getAttribute('href')) {
    return `href:${element.getAttribute('href')}`;
  }
  const label = resolveElementLabel(element);
  if (label) {
    return `text:${label}`;
  }
  return fallbackLocatorByDomPath(element);
}

function isInteractableNode(node: HTMLElement): boolean {
  return node.matches(INTERACTABLE_SELECTOR);
}

function toCandidateRecord(element: HTMLElement): CandidateRecord {
  const kind = detectKind(element);
  const label = resolveElementLabel(element);
  const locator = buildLocator(element);
  const disabled = isElementDisabled(element);
  const searchable = new Set<string>();

  searchable.add(normalizeQuery(locator));
  searchable.add(normalizeQuery(label));
  searchable.add(normalizeQuery(element.id || ''));
  searchable.add(normalizeQuery(element.getAttribute('data-ai-id') || ''));
  searchable.add(normalizeQuery(element.getAttribute('data-testid') || ''));
  searchable.add(normalizeQuery(element.getAttribute('name') || ''));
  searchable.add(normalizeQuery(element.getAttribute('href') || ''));

  return {
    candidate: {
      disabled,
      kind,
      label,
      locator,
      score: 0,
    },
    element,
    searchable,
  };
}

function scoreRecord(query: string, record: CandidateRecord): number {
  if (!query) {
    return 0;
  }

  const queryCompact = compactText(query);
  let score = 0;
  for (const value of record.searchable) {
    if (!value) {
      continue;
    }
    const valueCompact = compactText(value);
    if (value === query) {
      score = Math.max(score, 1);
    } else if (
      queryCompact &&
      valueCompact &&
      (valueCompact === queryCompact ||
        valueCompact.includes(queryCompact) ||
        queryCompact.includes(valueCompact))
    ) {
      score = Math.max(score, 0.85);
    } else if (value.startsWith(query)) {
      score = Math.max(score, 0.9);
    } else if (value.includes(query) || query.includes(value)) {
      score = Math.max(score, 0.76);
    } else if (
      queryCompact.length >= 2 &&
      valueCompact.length >= 2 &&
      queryCompact.slice(0, 2) === valueCompact.slice(0, 2)
    ) {
      score = Math.max(score, 0.58);
    }
  }

  const hintWords = SEMANTIC_HINTS[record.candidate.kind];
  if (hintWords.some((token) => query.includes(token))) {
    score += 0.1;
  }
  if (!record.candidate.disabled) {
    score += 0.04;
  }
  return Math.min(score, 1);
}

function compareByScore(a: CandidateRecord, b: CandidateRecord): number {
  if (b.candidate.score !== a.candidate.score) {
    return b.candidate.score - a.candidate.score;
  }
  return a.candidate.label.localeCompare(b.candidate.label);
}

export class LocatorResolutionError extends Error {
  readonly candidates: LocatorCandidate[];
  readonly code: LocatorResolutionErrorCode;
  readonly query: string;

  constructor(
    code: LocatorResolutionErrorCode,
    query: string,
    candidates: LocatorCandidate[],
    message: string,
  ) {
    super(message);
    this.code = code;
    this.query = query;
    this.candidates = candidates;
    this.name = 'LocatorResolutionError';
  }
}

export class LocatorResolver {
  private readonly candidateLimit: number;
  private readonly fuzzyThreshold: number;
  private readonly includeHidden: boolean;
  private readonly root: ParentNode;

  constructor(options: LocatorResolverOptions = {}) {
    this.root = options.root ?? document;
    this.includeHidden = options.includeHidden ?? false;
    this.candidateLimit = options.candidateLimit ?? 5;
    this.fuzzyThreshold = options.fuzzyThreshold ?? 0.7;
  }

  findCandidates(locator: string, limit = this.candidateLimit): LocatorCandidate[] {
    const normalized = normalizeQuery(locator);
    const ranked = this.collectCandidates()
      .map((record) => {
        record.candidate.score = scoreRecord(normalized, record);
        return record;
      })
      .filter((record) => record.candidate.score > 0.25)
      .sort(compareByScore)
      .slice(0, limit)
      .map((record) => record.candidate);
    return ranked;
  }

  resolve(locator: string, options: ResolveLocatorOptions = {}): LocatorResolution {
    const query = normalizeText(locator);
    if (!query) {
      throw new LocatorResolutionError(
        'invalid_locator',
        locator,
        [],
        tAiRuntime('locatorEmpty'),
      );
    }

    const exactMatch = this.resolveExact(query);
    if (exactMatch) {
      return exactMatch;
    }

    if (options.allowFuzzy === false) {
      const candidates = this.findCandidates(query, options.candidateLimit);
      throw new LocatorResolutionError(
        'not_found',
        query,
        candidates,
        tAiRuntime('locatorNoExactMatch', { locator: query }),
      );
    }

    const fuzzyMatches = this.resolveFuzzy(query);
    if (fuzzyMatches.length === 1) {
      return fuzzyMatches[0]!;
    }
    if (fuzzyMatches.length > 1) {
      throw new LocatorResolutionError(
        'ambiguous',
        query,
        fuzzyMatches.map((item) => item.candidate),
        tAiRuntime('locatorAmbiguous', { locator: query }),
      );
    }

    const candidates = this.findCandidates(query, options.candidateLimit);
    throw new LocatorResolutionError(
      'not_found',
      query,
      candidates,
      tAiRuntime('locatorNotFound', { locator: query }),
    );
  }

  resolveOrNull(
    locator: string,
    options: ResolveLocatorOptions = {},
  ): null | LocatorResolution {
    try {
      return this.resolve(locator, options);
    } catch {
      return null;
    }
  }

  private collectCandidates(): CandidateRecord[] {
    const records: CandidateRecord[] = [];
    const seen = new Set<HTMLElement>();

    const elements = this.root.querySelectorAll<HTMLElement>(INTERACTABLE_SELECTOR);
    elements.forEach((element) => {
      if (seen.has(element)) {
        return;
      }
      seen.add(element);
      if (!this.includeHidden && !isElementVisible(element)) {
        return;
      }
      records.push(toCandidateRecord(element));
    });

    if (
      this.root instanceof HTMLElement &&
      isInteractableNode(this.root) &&
      !seen.has(this.root)
    ) {
      records.push(toCandidateRecord(this.root));
    }

    return records;
  }

  private resolveBySelector(selector: string): null | LocatorResolution {
    let element: HTMLElement | null = null;
    try {
      element = this.root.querySelector<HTMLElement>(selector);
    } catch {
      return null;
    }
    if (!element) {
      return null;
    }
    if (!this.includeHidden && !isElementVisible(element)) {
      return null;
    }
    return {
      candidate: toCandidateRecord(element).candidate,
      element,
    };
  }

  private resolveExact(locator: string): null | LocatorResolution {
    if (locator.startsWith('css:')) {
      return this.resolveBySelector(locator.slice(4));
    }
    if (looksLikeCssSelector(locator)) {
      return this.resolveBySelector(locator);
    }
    if (locator.startsWith('id:')) {
      return this.resolveBySelector(`#${escapeSelectorValue(locator.slice(3))}`);
    }
    if (locator.startsWith('testid:')) {
      return this.resolveBySelector(
        `[data-testid="${escapeSelectorValue(locator.slice(7))}"]`,
      );
    }
    if (locator.startsWith('ai-id:')) {
      return this.resolveBySelector(
        `[data-ai-id="${escapeSelectorValue(locator.slice(6))}"]`,
      );
    }
    if (locator.startsWith('name:')) {
      return this.resolveBySelector(
        `[name="${escapeSelectorValue(locator.slice(5))}"]`,
      );
    }
    if (locator.startsWith('href:')) {
      return this.resolveBySelector(
        `a[href="${escapeSelectorValue(locator.slice(5))}"]`,
      );
    }

    const exactText = locator.startsWith('text:')
      ? normalizeQuery(locator.slice(5))
      : normalizeQuery(locator);
    if (!exactText) {
      return null;
    }
    const matches = this.collectCandidates().filter((record) =>
      record.searchable.has(exactText),
    );
    if (matches.length === 1) {
      return matches[0]!;
    }
    return null;
  }

  private resolveFuzzy(locator: string): LocatorResolution[] {
    const normalized = normalizeQuery(locator);
    const ranked = this.collectCandidates()
      .map((record) => {
        record.candidate.score = scoreRecord(normalized, record);
        return record;
      })
      .filter((record) => record.candidate.score >= this.fuzzyThreshold)
      .sort(compareByScore);

    if (ranked.length === 0) {
      return [];
    }
    if (ranked.length === 1) {
      const top = ranked[0]!;
      return [{ candidate: top.candidate, element: top.element }];
    }

    const top = ranked[0]!;
    const second = ranked[1]!;
    if (top.candidate.score - second.candidate.score <= 0.06) {
      return ranked.slice(0, this.candidateLimit).map((record) => ({
        candidate: record.candidate,
        element: record.element,
      }));
    }
    return [{ candidate: top.candidate, element: top.element }];
  }
}
