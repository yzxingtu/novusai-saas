import type {
  ActiveFormSummary,
  PageContext,
  PageContextSuggestedTools,
  PageSurfaceKind,
  PageSurfaceSummary,
} from '#/api/shared/ai-chat';

export type UISnapshotMode = 'compact' | 'full';

export interface UISnapshotSurfaceInput {
  kind: PageSurfaceKind;
  surface_id: string;
  title?: string;
}

export interface UISnapshotNodeInput {
  children_count?: number;
  content?: string;
  disabled?: boolean;
  interactable?: boolean;
  kind: string;
  label?: string;
  locator?: string;
  metadata?: Record<string, unknown>;
  node_id?: string;
  role?: string;
  surface_id?: string;
  text?: string;
  title?: string;
}

export interface UISnapshotInput {
  active_form_session_id?: string;
  active_form_summary?: ActiveFormSummary;
  active_surface_id?: string;
  form_sessions?: ActiveFormSummary[];
  nodes: UISnapshotNodeInput[];
  suggested_tools?: PageContextSuggestedTools;
  surface_stack: UISnapshotSurfaceInput[];
  ui_epoch: number;
}

export interface UISnapshotNode {
  children_count?: number;
  content?: string;
  interactable?: boolean;
  kind: string;
  locator?: string;
  node_id: string;
  role?: string;
  summary?: string;
  surface_id?: string;
}

export interface UISnapshot {
  active_form_session_id?: string;
  active_form_summary?: ActiveFormSummary;
  active_surface_id?: string;
  form_sessions: ActiveFormSummary[];
  generated_at: string;
  interactables_count: number;
  mode: UISnapshotMode;
  nodes: UISnapshotNode[];
  size_bytes: number;
  suggested_tools?: PageContextSuggestedTools;
  surface_stack: PageSurfaceSummary[];
  truncated: boolean;
  ui_epoch: number;
}

export interface UISnapshotGeneratorOptions {
  compactMaxBytes?: number;
  compactNodeLimit?: number;
  fullMaxBytes?: number;
  textPreviewLength?: number;
}

const DEFAULT_OPTIONS: Required<UISnapshotGeneratorOptions> = {
  compactMaxBytes: 10 * 1024,
  compactNodeLimit: 160,
  fullMaxBytes: 50 * 1024,
  textPreviewLength: 180,
};

function normalizeText(value: unknown, maxLength: number): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return undefined;
  }
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength)}...`;
}

function byteSize(value: unknown): number {
  return new TextEncoder().encode(JSON.stringify(value)).length;
}

function normalizeSurfaceStack(
  surfaces: UISnapshotSurfaceInput[],
): PageSurfaceSummary[] {
  const normalized: PageSurfaceSummary[] = [];
  const seen = new Set<string>();

  for (const surface of surfaces) {
    const surfaceId = normalizeText(surface.surface_id, 128);
    if (!surfaceId || seen.has(surfaceId)) {
      continue;
    }
    seen.add(surfaceId);
    normalized.push({
      kind: surface.kind,
      surface_id: surfaceId,
      title: normalizeText(surface.title, 200),
    });
    if (normalized.length >= 12) {
      break;
    }
  }

  return normalized;
}

function normalizeFormSessions(
  formSessions?: ActiveFormSummary[],
): ActiveFormSummary[] {
  if (!Array.isArray(formSessions) || formSessions.length === 0) {
    return [];
  }

  const deduped: ActiveFormSummary[] = [];
  const seen = new Set<string>();
  for (const form of formSessions) {
    const formSessionId = normalizeText(form.form_session_id, 128);
    if (!formSessionId || seen.has(formSessionId)) {
      continue;
    }
    seen.add(formSessionId);
    deduped.push({
      ...form,
      form_session_id: formSessionId,
      entity_name: normalizeText(form.entity_name, 128),
      remaining_required_fields: Array.isArray(form.remaining_required_fields)
        ? form.remaining_required_fields
            .map((field) => normalizeText(field, 128))
            .filter((field): field is string => Boolean(field))
            .slice(0, 32)
        : [],
    });
    if (deduped.length >= 8) {
      break;
    }
  }
  return deduped;
}

function buildNodeSummary(
  node: UISnapshotNodeInput,
  textPreviewLength: number,
): string | undefined {
  const summarySource = node.label || node.title || node.text || node.content;
  return normalizeText(summarySource, textPreviewLength);
}

function normalizeNodes(
  nodes: UISnapshotNodeInput[],
  mode: UISnapshotMode,
  options: Required<UISnapshotGeneratorOptions>,
): UISnapshotNode[] {
  const normalizedNodes: UISnapshotNode[] = [];
  const nodeLimit =
    mode === 'compact'
      ? options.compactNodeLimit
      : options.compactNodeLimit * 2;

  for (let index = 0; index < nodes.length; index++) {
    const node = nodes[index];
    if (!node) {
      continue;
    }
    const nodeId = normalizeText(
      node.node_id || node.locator || `${node.kind}-${index}`,
      128,
    );
    if (!nodeId) {
      continue;
    }

    const output: UISnapshotNode = {
      children_count:
        typeof node.children_count === 'number'
          ? Math.max(Math.floor(node.children_count), 0)
          : undefined,
      interactable:
        typeof node.interactable === 'boolean' ? node.interactable : undefined,
      kind: normalizeText(node.kind, 64) || 'unknown',
      locator: normalizeText(node.locator, 240),
      node_id: nodeId,
      role: normalizeText(node.role, 64),
      summary: buildNodeSummary(node, options.textPreviewLength),
      surface_id: normalizeText(node.surface_id, 128),
    };

    if (mode === 'full') {
      output.content = normalizeText(node.content || node.text, 2000);
    }

    normalizedNodes.push(output);
    if (normalizedNodes.length >= nodeLimit) {
      break;
    }
  }

  return normalizedNodes;
}

function estimateInteractables(nodes: UISnapshotNode[]): number {
  return nodes.reduce((count, node) => {
    if (node.interactable) {
      return count + 1;
    }
    if (['button', 'input', 'link', 'select', 'switch'].includes(node.kind)) {
      return count + 1;
    }
    return count;
  }, 0);
}

function compactByBudget(
  snapshot: UISnapshot,
  mode: UISnapshotMode,
  options: Required<UISnapshotGeneratorOptions>,
): UISnapshot {
  const budget =
    mode === 'compact' ? options.compactMaxBytes : options.fullMaxBytes;
  let candidate = { ...snapshot };
  let size = byteSize(candidate);
  let truncated = false;

  while (size > budget && candidate.nodes.length > 1) {
    truncated = true;
    const nextLength = Math.max(1, Math.floor(candidate.nodes.length * 0.8));
    candidate = {
      ...candidate,
      nodes: candidate.nodes.slice(0, nextLength),
    };
    size = byteSize(candidate);
  }

  if (size > budget) {
    truncated = true;
    candidate = {
      ...candidate,
      nodes: candidate.nodes.map((node) => ({
        ...node,
        content: mode === 'full' ? normalizeText(node.content, 512) : undefined,
        summary: normalizeText(node.summary, 80),
      })),
    };
    size = byteSize(candidate);
  }

  return {
    ...candidate,
    interactables_count: estimateInteractables(candidate.nodes),
    size_bytes: size,
    truncated: snapshot.truncated || truncated,
  };
}

export class UISnapshotGenerator {
  private readonly options: Required<UISnapshotGeneratorOptions>;

  constructor(options: UISnapshotGeneratorOptions = {}) {
    this.options = {
      ...DEFAULT_OPTIONS,
      ...options,
    };
  }

  generateSnapshot(
    input: UISnapshotInput,
    mode: UISnapshotMode = 'compact',
  ): UISnapshot {
    const surfaceStack = normalizeSurfaceStack(input.surface_stack);
    const formSessions = normalizeFormSessions(input.form_sessions);
    const activeSurfaceId =
      normalizeText(input.active_surface_id, 128) ||
      surfaceStack[surfaceStack.length - 1]?.surface_id;
    const activeFormSessionId =
      normalizeText(input.active_form_session_id, 128) ||
      normalizeText(input.active_form_summary?.form_session_id, 128);

    const snapshot: UISnapshot = {
      active_form_session_id: activeFormSessionId,
      active_form_summary: input.active_form_summary
        ? {
            ...input.active_form_summary,
            form_session_id:
              normalizeText(input.active_form_summary.form_session_id, 128) ||
              '',
            entity_name: normalizeText(
              input.active_form_summary.entity_name,
              128,
            ),
            remaining_required_fields: Array.isArray(
              input.active_form_summary.remaining_required_fields,
            )
              ? input.active_form_summary.remaining_required_fields
                  .map((field) => normalizeText(field, 128))
                  .filter((field): field is string => Boolean(field))
                  .slice(0, 32)
              : [],
          }
        : undefined,
      active_surface_id: activeSurfaceId,
      form_sessions: formSessions,
      generated_at: new Date().toISOString(),
      interactables_count: 0,
      mode,
      nodes: normalizeNodes(input.nodes, mode, this.options),
      size_bytes: 0,
      suggested_tools: input.suggested_tools,
      surface_stack: surfaceStack,
      truncated: false,
      ui_epoch:
        typeof input.ui_epoch === 'number' && Number.isFinite(input.ui_epoch)
          ? Math.max(Math.floor(input.ui_epoch), 0)
          : 0,
    };

    const budgeted = compactByBudget(snapshot, mode, this.options);
    return {
      ...budgeted,
      size_bytes: byteSize(budgeted),
    };
  }

  buildThinPageContext(args: {
    pageKey: string;
    pageSessionId?: string;
    pageTitle?: string;
    snapshot: UISnapshot;
  }): PageContext {
    return {
      active_form_session_id: args.snapshot.active_form_session_id,
      active_form_summary: args.snapshot.active_form_summary,
      active_surface_id: args.snapshot.active_surface_id,
      page_key: args.pageKey,
      page_session_id: args.pageSessionId,
      page_title: args.pageTitle,
      suggested_tools: args.snapshot.suggested_tools,
      surface_stack: args.snapshot.surface_stack,
      ui_epoch: args.snapshot.ui_epoch,
    };
  }
}
