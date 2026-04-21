import type {
  ActiveFormSummary,
  PageContext,
  PageContextSuggestedTool,
} from '#/api/shared/ai-chat';
import type { PageOperation } from '#/components/business/ai-runtime/page-operation-types';

import { $t } from '#/locales';

const UI_TOOL_META: Record<
  string,
  Omit<PageOperation, 'description' | 'handler' | 'label' | 'name'>
> = {
  ui_click: { readonly: false },
  ui_fill_form: { readonly: false },
  ui_get_form_state: { readonly: true },
  ui_get_snapshot: { readonly: true },
  ui_list_interactables: { readonly: true },
  ui_open_surface: { readonly: false },
  ui_read_region: { readonly: true },
  ui_read_table: { readonly: true },
  ui_set_field: { readonly: false },
  ui_submit_form: { readonly: false },
};

const PAGE_CONTEXT_TOOL_SET = new Set<PageContextSuggestedTool>([
  'ui_click',
  'ui_fill_form',
  'ui_get_form_state',
  'ui_get_snapshot',
  'ui_list_interactables',
  'ui_open_surface',
  'ui_read_region',
  'ui_read_table',
  'ui_set_field',
  'ui_submit_form',
]);

const FORM_SUBMIT_READY_STAGES = new Set([
  'ready_to_submit',
  'submitted',
  'submitting',
]);

function addToolName(
  target: PageContextSuggestedTool[],
  name: PageContextSuggestedTool,
) {
  if (!target.includes(name)) {
    target.push(name);
  }
}

function hasSurfaceState(pageContext: null | PageContext): boolean {
  if (!pageContext) {
    return false;
  }
  const activeSurfaceId = String(pageContext.active_surface_id || '').trim();
  if (activeSurfaceId) {
    return true;
  }
  return (
    Array.isArray(pageContext.surface_stack) &&
    pageContext.surface_stack.length > 0
  );
}

function hasFormState(
  pageContext: null | PageContext,
): pageContext is PageContext & {
  active_form_summary?: ActiveFormSummary;
} {
  if (!pageContext) {
    return false;
  }
  const activeFormSessionId = String(
    pageContext.active_form_session_id ||
      pageContext.active_form_summary?.form_session_id ||
      '',
  ).trim();
  return Boolean(activeFormSessionId || pageContext.active_form_summary);
}

export function hasRuntimePageState(pageContext: null | PageContext): boolean {
  if (!pageContext) {
    return false;
  }
  if (typeof pageContext.ui_epoch === 'number') {
    return true;
  }
  if (hasSurfaceState(pageContext)) {
    return true;
  }
  return hasFormState(pageContext);
}

export function isPageContextSuggestedTool(
  value: string,
): value is PageContextSuggestedTool {
  return PAGE_CONTEXT_TOOL_SET.has(value as PageContextSuggestedTool);
}

export function buildRuntimePageOperationNames(
  pageContext: null | PageContext,
): PageContextSuggestedTool[] {
  if (!hasRuntimePageState(pageContext)) {
    return [];
  }

  const operationNames: PageContextSuggestedTool[] = [];
  addToolName(operationNames, 'ui_get_snapshot');
  addToolName(operationNames, 'ui_read_region');
  addToolName(operationNames, 'ui_list_interactables');
  addToolName(operationNames, 'ui_click');
  addToolName(operationNames, 'ui_open_surface');

  if (hasFormState(pageContext)) {
    addToolName(operationNames, 'ui_get_form_state');
    addToolName(operationNames, 'ui_fill_form');
    addToolName(operationNames, 'ui_set_field');
    const stage = String(pageContext.active_form_summary?.stage || '').trim();
    if (
      pageContext.active_form_summary?.can_submit ||
      FORM_SUBMIT_READY_STAGES.has(stage)
    ) {
      addToolName(operationNames, 'ui_submit_form');
    }
  }

  return operationNames;
}

function toToolLabel(name: string): string {
  if (!name) {
    return '';
  }
  const fallback = name
    .replace(/^ui_/, '')
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
  const key = `common.aiPanel.toolLabel.${name}`;
  const translated = $t(key);
  return translated === key ? fallback : translated;
}

function toToolDescription(name: string): string {
  const key = `common.aiPanel.toolDesc.${name}`;
  const translated = $t(key);
  return translated === key ? toToolLabel(name) : translated;
}

export function buildPageOperation(name: string): null | PageOperation {
  const normalizedName = String(name || '').trim();
  if (!isPageContextSuggestedTool(normalizedName)) {
    return null;
  }
  return {
    name: normalizedName,
    label: toToolLabel(normalizedName),
    description: toToolDescription(normalizedName),
    readonly: UI_TOOL_META[normalizedName]?.readonly ?? true,
  };
}
