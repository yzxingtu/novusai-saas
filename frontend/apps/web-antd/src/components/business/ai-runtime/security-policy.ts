export type AIReadAccess = 'allow' | 'mask' | 'off';
export type AIToggleAccess = 'allow' | 'off';

export type AISensitiveFieldCategory =
  | 'captcha'
  | 'file_upload'
  | 'password'
  | 'token';

export interface AIRouteSecurityPolicy {
  act?: AIToggleAccess;
  confirmActionKinds?: string[];
  disabledActionKinds?: string[];
  enabled?: boolean;
  pageContextKey?: string;
  read?: AIReadAccess;
  sensitiveFieldRead?: Exclude<AIReadAccess, 'allow'>;
  submit?: AIToggleAccess;
}

export interface AIDataPolicyDirective {
  act?: AIToggleAccess;
  aiDisabled?: boolean;
  aiOff?: boolean;
  read?: AIReadAccess;
  submit?: AIToggleAccess;
}

export interface AIElementPolicySource {
  className?: string;
  getAttribute(name: string): null | string;
  id?: string;
  name?: string;
  parentElement?: AIElementPolicySource | null;
  tagName?: string;
  type?: string;
}

export interface ResolveAISecurityPolicyInput {
  actionKind?: string;
  directives?: AIDataPolicyDirective;
  element?: AIElementPolicySource | null;
  fieldName?: string;
  fieldType?: string;
  routePolicy?: AIRouteSecurityPolicy | null;
}

export interface AISecurityPolicyDecision {
  actAccess: AIToggleAccess;
  blockedReasons: string[];
  canAct: boolean;
  canRead: boolean;
  canSubmit: boolean;
  readAccess: AIReadAccess;
  requireConfirm: boolean;
  sensitiveFieldCategory?: AISensitiveFieldCategory;
  submitAccess: AIToggleAccess;
  visible: boolean;
}

export interface AIActionSecurityResult {
  actionKind: string;
  allowed: boolean;
  decision: AISecurityPolicyDecision;
  reason?: string;
  requireConfirm: boolean;
}

const OFF = 'off';
const MASK = 'mask';

export const DEFAULT_DANGEROUS_ACTION_KINDS = Object.freeze([
  'approve',
  'delete',
  'drop',
  'publish',
  'reject',
  'reset',
  'send',
  'submit',
  'truncate',
]);

const DEFAULT_SENSITIVE_FIELD_RULES: Record<
  AISensitiveFieldCategory,
  {
    act: AIToggleAccess;
    read: AIReadAccess;
    submit: AIToggleAccess;
  }
> = {
  password: { read: OFF, act: OFF, submit: OFF },
  token: { read: OFF, act: OFF, submit: OFF },
  captcha: { read: OFF, act: OFF, submit: OFF },
  file_upload: { read: OFF, act: OFF, submit: OFF },
};

function normalizeList(values?: string | string[]): string[] {
  if (!values) return [];
  if (Array.isArray(values)) {
    return [
      ...new Set(values.map((item) => String(item).trim().toLowerCase())),
    ].filter(Boolean);
  }
  return [
    ...new Set(
      String(values)
        .split(',')
        .map((item) => item.trim().toLowerCase())
        .filter(Boolean),
    ),
  ];
}

function normalizeReadAccess(value?: null | string): AIReadAccess | undefined {
  const normalized = String(value ?? '')
    .trim()
    .toLowerCase();
  if (normalized === MASK) return MASK;
  if (normalized === OFF) return OFF;
  if (normalized === 'allow') return 'allow';
  return undefined;
}

function normalizeToggleAccess(
  value?: null | string,
): AIToggleAccess | undefined {
  const normalized = String(value ?? '')
    .trim()
    .toLowerCase();
  if (normalized === OFF) return OFF;
  if (normalized === 'allow') return 'allow';
  return undefined;
}

function normalizeAttrValue(value: null | string): string {
  return String(value ?? '')
    .trim()
    .toLowerCase();
}

function isDisabledDirective(value: null | string): boolean {
  if (value === null) {
    return false;
  }
  const normalized = normalizeAttrValue(value);
  if (!normalized) {
    return true;
  }
  return !['0', 'false', 'no', 'off'].includes(normalized);
}

function scanAncestorAttr(
  element: AIElementPolicySource | null | undefined,
  attrName: string,
): null | string {
  let current = element;
  while (current) {
    const rawValue = current.getAttribute(attrName);
    if (rawValue !== null) {
      return normalizeAttrValue(rawValue);
    }
    current = current.parentElement ?? null;
  }
  return null;
}

function extractFieldNameHint(
  input: ResolveAISecurityPolicyInput,
): string | undefined {
  const fieldName = String(input.fieldName ?? '').trim();
  if (fieldName) return fieldName.toLowerCase();

  const element = input.element;
  if (!element) return undefined;
  const hints = [
    element.getAttribute('name'),
    element.getAttribute('id'),
    element.getAttribute('autocomplete'),
    typeof element.className === 'string' ? element.className : '',
  ]
    .map((item) =>
      String(item ?? '')
        .trim()
        .toLowerCase(),
    )
    .filter(Boolean);
  return hints.join(' ');
}

function detectSensitiveFieldCategory(
  input: ResolveAISecurityPolicyInput,
): AISensitiveFieldCategory | undefined {
  const rawType =
    input.fieldType ||
    input.element?.type ||
    input.element?.getAttribute('type') ||
    '';
  const fieldType = String(rawType).trim().toLowerCase();

  if (['file'].includes(fieldType)) {
    return 'file_upload';
  }
  if (['passcode', 'passwd', 'password'].includes(fieldType)) {
    return 'password';
  }

  const fieldNameHint = extractFieldNameHint(input) ?? '';
  if (
    /captcha|otp|one[-_\s]?time[-_\s]?password|verification[-_\s]?code|verify[-_\s]?code/.test(
      fieldNameHint,
    )
  ) {
    return 'captcha';
  }

  if (
    /token|api[-_\s]?key|secret|access[-_\s]?key|client[-_\s]?secret|private[-_\s]?key/.test(
      fieldNameHint,
    )
  ) {
    return 'token';
  }

  if (/upload(?:er)?/.test(fieldNameHint)) {
    return 'file_upload';
  }

  return undefined;
}

function toDirective(
  input: ResolveAISecurityPolicyInput,
): AIDataPolicyDirective {
  const explicit = input.directives ?? {};
  const element = input.element;

  const aiValue = scanAncestorAttr(element, 'data-ai');
  const aiDisabledValue = scanAncestorAttr(element, 'data-ai-disabled');
  const readValue = scanAncestorAttr(element, 'data-ai-read');
  const actValue = scanAncestorAttr(element, 'data-ai-act');
  const submitValue = scanAncestorAttr(element, 'data-ai-submit');

  return {
    aiDisabled: explicit.aiDisabled ?? isDisabledDirective(aiDisabledValue),
    aiOff: explicit.aiOff ?? aiValue === OFF,
    read: explicit.read ?? normalizeReadAccess(readValue),
    act: explicit.act ?? normalizeToggleAccess(actValue),
    submit: explicit.submit ?? normalizeToggleAccess(submitValue),
  };
}

function resolveConfirmRequirement(input: {
  actionKind?: string;
  decision: AISecurityPolicyDecision;
  routePolicy?: AIRouteSecurityPolicy | null;
}) {
  const actionKind = normalizeActionKind(input.actionKind);
  if (!actionKind) return false;
  if (!input.decision.visible) return false;

  const isSubmitAction = actionKind === 'submit';
  if (isSubmitAction && !input.decision.canSubmit) return false;
  if (!isSubmitAction && !input.decision.canAct) return false;

  const confirmKinds = new Set<string>([
    ...DEFAULT_DANGEROUS_ACTION_KINDS,
    ...normalizeList(input.routePolicy?.confirmActionKinds),
  ]);
  return confirmKinds.has(actionKind);
}

function actionIsBlockedByRoute(input: {
  actionKind?: string;
  routePolicy?: AIRouteSecurityPolicy | null;
}): boolean {
  const actionKind = normalizeActionKind(input.actionKind);
  if (!actionKind) return false;

  const disabledKinds = new Set<string>();
  for (const value of normalizeList(input.routePolicy?.disabledActionKinds)) {
    disabledKinds.add(value);
    const normalized = normalizeActionKind(value);
    if (normalized) {
      disabledKinds.add(normalized);
    }
  }
  return disabledKinds.has(actionKind);
}

export function normalizeActionKind(raw?: string): string {
  const value = String(raw ?? '')
    .trim()
    .toLowerCase();
  if (!value) return '';

  if (value.includes('submit')) return 'submit';
  if (
    value.includes('delete') ||
    value.includes('remove') ||
    value.includes('destroy')
  ) {
    return 'delete';
  }
  if (value.includes('publish')) return 'publish';
  if (value.includes('approve')) return 'approve';
  if (value.includes('reject')) return 'reject';
  if (value.includes('send')) return 'send';
  if (
    value.includes('fill') ||
    value.includes('replace') ||
    value.includes('edit') ||
    value.includes('create') ||
    value.includes('update')
  ) {
    return 'mutate';
  }
  if (
    value.includes('click') ||
    value.includes('open') ||
    value.includes('navigate')
  ) {
    return 'click';
  }
  return value;
}

export function readValueForAI<T>(
  value: T,
  decision: Pick<AISecurityPolicyDecision, 'canRead' | 'readAccess'>,
): T | undefined {
  if (!decision.canRead) {
    return undefined;
  }
  if (decision.readAccess !== MASK) {
    return value;
  }
  return maskAIValue(value) as T;
}

export function maskAIValue(value: unknown): unknown {
  if (value === null || value === undefined) {
    return value;
  }
  if (typeof value === 'string') {
    if (!value) return value;
    if (value.length <= 4) {
      return '*'.repeat(value.length);
    }
    return `${value.slice(0, 2)}***${value.slice(-2)}`;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return '***';
  }
  if (Array.isArray(value)) {
    return value.map((item) => maskAIValue(item));
  }
  if (typeof value === 'object') {
    return '[masked]';
  }
  return '***';
}

export function extractAIDataPolicyDirective(
  element: AIElementPolicySource | null | undefined,
): AIDataPolicyDirective {
  return toDirective({ element });
}

export function resolveAISecurityPolicy(
  input: ResolveAISecurityPolicyInput,
): AISecurityPolicyDecision {
  const routePolicy = input.routePolicy;
  const actionKind = normalizeActionKind(input.actionKind);
  const directive = toDirective(input);

  const blockedReasons: string[] = [];
  const visible =
    routePolicy?.enabled !== false && !directive.aiOff && !directive.aiDisabled;
  if (routePolicy?.enabled === false) {
    blockedReasons.push('route_ai_disabled');
  }
  if (directive.aiDisabled) {
    blockedReasons.push('data_ai_disabled');
  }
  if (directive.aiOff) {
    blockedReasons.push('data_ai_off');
  }

  let readAccess: AIReadAccess = routePolicy?.read ?? 'allow';
  let actAccess: AIToggleAccess = routePolicy?.act ?? 'allow';
  let submitAccess: AIToggleAccess = routePolicy?.submit ?? 'allow';

  if (visible) {
    if (routePolicy?.read === OFF) {
      blockedReasons.push('route_read_off');
    } else if (routePolicy?.read === MASK) {
      blockedReasons.push('route_read_mask');
    }
    if (routePolicy?.act === OFF) {
      blockedReasons.push('route_act_off');
    }
    if (routePolicy?.submit === OFF) {
      blockedReasons.push('route_submit_off');
    }
    if (directive.read) {
      readAccess = directive.read;
      blockedReasons.push(
        directive.read === OFF ? 'data_ai_read_off' : 'data_ai_read_mask',
      );
    }
    if (directive.act === OFF) {
      actAccess = OFF;
      blockedReasons.push('data_ai_act_off');
    }
    if (directive.submit === OFF) {
      submitAccess = OFF;
      blockedReasons.push('data_ai_submit_off');
    }
  } else {
    readAccess = OFF;
    actAccess = OFF;
    submitAccess = OFF;
  }

  if (visible && actionIsBlockedByRoute({ actionKind, routePolicy })) {
    if (actionKind === 'submit') {
      submitAccess = OFF;
    } else {
      actAccess = OFF;
    }
    blockedReasons.push('route_action_disabled');
  }

  const sensitiveFieldCategory = detectSensitiveFieldCategory(input);
  if (visible && sensitiveFieldCategory) {
    const sensitiveRule = DEFAULT_SENSITIVE_FIELD_RULES[sensitiveFieldCategory];
    const routeSensitiveRead = routePolicy?.sensitiveFieldRead;

    if (readAccess !== OFF) {
      readAccess = routeSensitiveRead ?? sensitiveRule.read;
    }
    if (actAccess !== OFF) {
      actAccess = sensitiveRule.act;
    }
    if (submitAccess !== OFF) {
      submitAccess = sensitiveRule.submit;
    }
    blockedReasons.push(`sensitive_${sensitiveFieldCategory}`);
  }

  const canRead = visible && readAccess !== OFF;
  const canAct = visible && actAccess !== OFF;
  const canSubmit = visible && submitAccess !== OFF;

  const decision: AISecurityPolicyDecision = {
    visible,
    readAccess,
    actAccess,
    submitAccess,
    canRead,
    canAct,
    canSubmit,
    requireConfirm: false,
    blockedReasons,
    ...(sensitiveFieldCategory ? { sensitiveFieldCategory } : {}),
  };

  decision.requireConfirm = resolveConfirmRequirement({
    actionKind,
    decision,
    routePolicy,
  });

  return decision;
}

export function evaluateAIActionSecurity(
  input: ResolveAISecurityPolicyInput,
): AIActionSecurityResult {
  const decision = resolveAISecurityPolicy(input);
  const actionKind = normalizeActionKind(input.actionKind);
  const isSubmit = actionKind === 'submit';
  const allowed = isSubmit ? decision.canSubmit : decision.canAct;

  return {
    actionKind,
    allowed,
    requireConfirm: allowed && decision.requireConfirm,
    reason: allowed ? undefined : decision.blockedReasons[0],
    decision,
  };
}
