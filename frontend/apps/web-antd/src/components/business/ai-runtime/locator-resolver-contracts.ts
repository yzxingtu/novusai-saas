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
