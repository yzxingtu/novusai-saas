import type {
  LocatorCandidate,
  LocatorResolution,
  LocatorResolutionErrorCode,
  LocatorResolverOptions,
  ResolveLocatorOptions,
} from './locator-resolver-contracts';

import { tAiRuntime } from './i18n';
import {
  collectCandidates,
  compareByScore,
  escapeSelectorValue,
  isElementVisible,
  looksLikeCssSelector,
  normalizeQuery,
  normalizeText,
  scoreRecord,
  toCandidateRecord,
} from './locator-resolver-support';

export type {
  LocatorCandidate,
  LocatorResolution,
  LocatorResolutionErrorCode,
  LocatorResolverOptions,
  ResolveLocatorOptions,
  UIInteractableKind,
} from './locator-resolver-contracts';

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
    return this.collectCandidates()
      .map((record) => {
        record.candidate.score = scoreRecord(normalized, record);
        return record;
      })
      .filter((record) => record.candidate.score > 0.25)
      .sort(compareByScore)
      .slice(0, limit)
      .map((record) => record.candidate);
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

  private collectCandidates() {
    return collectCandidates({
      includeHidden: this.includeHidden,
      root: this.root,
    });
  }

  private resolveBySelector(
    selector: string,
    options: {
      failOnMultiple?: boolean;
      locatorForError?: string;
    } = {},
  ): null | LocatorResolution {
    let elements: NodeListOf<HTMLElement>;
    try {
      elements = this.root.querySelectorAll<HTMLElement>(selector);
    } catch {
      return null;
    }
    const visibleMatches = Array.from(elements).filter(
      (element) => this.includeHidden || isElementVisible(element),
    );
    if (visibleMatches.length === 0) {
      return null;
    }
    if (options.failOnMultiple && visibleMatches.length > 1) {
      const locator = options.locatorForError || selector;
      const candidates = visibleMatches
        .slice(0, this.candidateLimit)
        .map((element) => toCandidateRecord(element).candidate);
      throw new LocatorResolutionError(
        'ambiguous',
        locator,
        candidates,
        tAiRuntime('locatorAmbiguous', { locator }),
      );
    }
    const element = visibleMatches[0]!;
    return {
      candidate: toCandidateRecord(element).candidate,
      element,
    };
  }

  private resolveExact(locator: string): null | LocatorResolution {
    if (locator.startsWith('css:')) {
      return this.resolveBySelector(locator.slice(4), {
        failOnMultiple: true,
        locatorForError: locator,
      });
    }
    if (looksLikeCssSelector(locator)) {
      return this.resolveBySelector(locator, {
        failOnMultiple: true,
        locatorForError: locator,
      });
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
