import type {
  PaginatedResult,
  TenantApprovalRecord,
  TenantArtifactDetail,
  TenantArtifactFeedback,
  TenantArtifactFeedbackPayload,
  TenantArtifactSummary,
  TenantBuilderCapability,
  TenantHomeAlertItem,
  TenantHomePayload,
  TenantHomeStatCard,
  TenantHomeSummary,
  TenantTemplateListQuery,
  TenantHomeTodoItem,
  TenantListQuery,
  TenantNodeRun,
  TenantPluginSharedApi,
  TenantRequestClientLike,
  TenantRunDetail,
  TenantRunEvent,
  TenantRunSummary,
  TenantWorkflowDetail,
  TenantWorkflowEdge,
  TenantWorkflowInputVariable,
  TenantWorkflowNode,
  TenantWorkflowOutputContract,
  TenantWorkflowCopyPayload,
  TenantWorkflowSummary,
  TenantWorkflowTemplateSummary,
  TenantWorkflowUpsertPayload,
  TenantWorkflowVersionSummary,
} from '../types/tenant';

function getShared(): TenantPluginSharedApi {
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as TenantPluginSharedApi | undefined;
  if (!shared?.requestClient) {
    throw new Error('NovusPluginShared.requestClient is not available');
  }
  return shared;
}

function getClient(): TenantRequestClientLike {
  return getShared().requestClient;
}

function resolveTenantApiBase(): string {
  return '/tenant/plugins/workflow-orchestration/api';
}

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function toNullableRecord(value: unknown): null | Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function toArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function asBoolean(...values: unknown[]): boolean | undefined {
  for (const value of values) {
    if (typeof value === 'boolean') {
      return value;
    }
  }
  return undefined;
}

function asNumber(...values: unknown[]): number | undefined {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string' && value.trim() !== '') {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return undefined;
}

function asString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === 'string' && value.trim() !== '') {
      return value;
    }
  }
  return undefined;
}

function asOptionalString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === 'string') {
      return value;
    }
  }
  return undefined;
}

function asStringArray(value: unknown): string[] {
  return toArray<unknown>(value)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
}

function asOptionalStringArray(value: unknown): string[] | undefined {
  return Array.isArray(value) ? asStringArray(value) : undefined;
}

function unwrapPayload<T>(value: unknown): T {
  const record = toRecord(value);
  if ('data' in record) {
    return unwrapPayload<T>(record.data);
  }
  return (value as T) ?? ({} as T);
}

function extractListContainer(value: unknown): Record<string, unknown> {
  const payload = toRecord(unwrapPayload<Record<string, unknown>>(value));
  if (Array.isArray(payload.items)) {
    return payload;
  }
  if (Array.isArray(payload.list)) {
    return { ...payload, items: payload.list };
  }
  if (Array.isArray(payload.rows)) {
    return { ...payload, items: payload.rows };
  }
  if (Array.isArray(payload.records)) {
    return { ...payload, items: payload.records };
  }
  if (Array.isArray(value)) {
    return { items: value };
  }
  return payload;
}

function buildListResult<T>(
  value: unknown,
  normalizer: (item: unknown) => T,
): PaginatedResult<T> {
  const container = extractListContainer(value);
  const items = toArray<unknown>(container.items).map(normalizer);
  return {
    items,
    page:
      asNumber(
        container.page,
        container.pageNumber,
        container.page_number,
        toRecord(container.page).number,
      ) ?? 1,
    size:
      asNumber(
        container.size,
        container.pageSize,
        container.page_size,
        toRecord(container.page).size,
      ) ?? items.length,
    total:
      asNumber(
        container.total,
        container.totalCount,
        container.total_count,
        container.count,
      ) ?? items.length,
  };
}

function normalizeBuilderCapability(item: unknown): TenantBuilderCapability {
  const record = toRecord(item);
  return {
    code:
      asString(record.code, record.key, record.name) ?? 'unknown_capability',
    enabled:
      asBoolean(record.enabled, record.is_enabled, record.isEnabled) ?? false,
    editable: asBoolean(record.editable, record.is_editable, record.can_edit),
    label: asString(record.label, record.display_name, record.name),
    description: asOptionalString(record.description, record.summary),
    reason: asOptionalString(record.reason, record.message),
    limit: asNumber(record.limit, record.max, record.max_steps),
  };
}

function normalizeHomeSummary(value: unknown): TenantHomeSummary | undefined {
  const record = toRecord(value);
  if (Object.keys(record).length === 0) {
    return undefined;
  }
  return {
    pendingApprovals: asNumber(
      record.pendingApprovals,
      record.pending_approvals,
    ),
    failedRuns: asNumber(record.failedRuns, record.failed_runs),
    pendingArtifacts: asNumber(
      record.pendingArtifacts,
      record.pending_artifacts,
    ),
    activeWorkflows: asNumber(
      record.activeWorkflows,
      record.active_workflows,
    ),
    runningNow: asNumber(record.runningNow, record.running_now),
    quotaWarnings: asNumber(record.quotaWarnings, record.quota_warnings),
  };
}

function normalizeHomeStatCard(item: unknown): TenantHomeStatCard {
  const record = toRecord(item);
  return {
    code: asString(record.code, record.key, record.name) ?? 'unknown',
    label: asString(record.label, record.title, record.name) ?? 'unknown',
    value: asString(record.value) ?? asNumber(record.value) ?? '0',
    hint: asOptionalString(record.hint, record.description),
    tone: asOptionalString(record.tone, record.level),
  };
}

function normalizeHomeTodo(item: unknown): TenantHomeTodoItem {
  const record = toRecord(item);
  return {
    id: asString(record.id) ?? asNumber(record.id) ?? 'todo',
    category:
      asString(record.category, record.type, record.todo_type) ?? 'general',
    title: asString(record.title, record.name) ?? '',
    summary: asOptionalString(record.summary, record.description),
    severity: asOptionalString(record.severity, record.level, record.urgency),
    actionLabel: asOptionalString(
      record.actionLabel,
      record.action_label,
      record.cta_label,
    ),
    targetPath: asOptionalString(
      record.targetPath,
      record.target_path,
      record.detail_path,
    ),
    dueAt: asOptionalString(record.dueAt, record.due_at),
  };
}

function normalizeHomeAlert(item: unknown): TenantHomeAlertItem {
  const record = toRecord(item);
  return {
    id: asString(record.id) ?? asNumber(record.id) ?? 'alert',
    level: asString(record.level, record.severity, record.type) ?? 'info',
    title: asString(record.title, record.name) ?? '',
    summary: asOptionalString(record.summary, record.description, record.message),
    targetPath: asOptionalString(
      record.targetPath,
      record.target_path,
      record.detail_path,
    ),
  };
}

function normalizeWorkflowInputVariable(
  item: unknown,
): TenantWorkflowInputVariable {
  const record = toRecord(item);
  return {
    name: asString(record.name, record.key) ?? 'variable',
    label: asOptionalString(record.label, record.title),
    type: asOptionalString(record.type),
    required: asBoolean(record.required, record.is_required),
    defaultValue: record.defaultValue ?? record.default_value,
    description: asOptionalString(record.description, record.help),
  };
}

function normalizeWorkflowOutputContract(
  item: unknown,
): TenantWorkflowOutputContract {
  const record = toRecord(item);
  return {
    key: asString(record.key, record.name) ?? 'output',
    label: asOptionalString(record.label, record.title),
    type: asOptionalString(record.type),
    description: asOptionalString(record.description),
  };
}

function normalizeWorkflowNode(item: unknown): TenantWorkflowNode {
  const record = toRecord(item);
  return {
    id: asString(record.id, record.node_id) ?? 'node',
    name: asString(record.name, record.title) ?? '',
    type: asString(record.type, record.node_type) ?? 'unknown',
    stage: asOptionalString(record.stage, record.group),
    status: asOptionalString(record.status),
    readonly: asBoolean(record.readonly, record.is_readonly),
  };
}

function normalizeWorkflowEdge(item: unknown): TenantWorkflowEdge {
  const record = toRecord(item);
  return {
    source: asString(record.source, record.from, record.source_id) ?? 'source',
    target: asString(record.target, record.to, record.target_id) ?? 'target',
    label: asOptionalString(record.label, record.name),
  };
}

function normalizeWorkflowVersion(
  item: unknown,
): TenantWorkflowVersionSummary {
  const record = toRecord(item);
  return {
    id: asNumber(record.id),
    version: asString(record.version, record.code) ?? '',
    changeLog: asOptionalString(record.changeLog, record.change_log),
    createdAt: asOptionalString(record.createdAt, record.created_at),
    createdBy: asOptionalString(record.createdBy, record.created_by),
    isCurrent: asBoolean(record.isCurrent, record.is_current),
    status: asOptionalString(record.status),
  };
}

function normalizeWorkflowSummary(item: unknown): TenantWorkflowSummary {
  const record = toRecord(item);
  return {
    id: asNumber(record.id, record.workflow_id) ?? 0,
    name: asString(record.name, record.title) ?? '',
    code: asOptionalString(record.code),
    description: asOptionalString(record.description, record.summary),
    status: asOptionalString(record.status),
    builderMode: asOptionalString(
      record.builderMode,
      record.builder_mode,
      record.source_kind,
    ),
    sourceTemplateName: asOptionalString(
      record.sourceTemplateName,
      record.source_template_name,
      record.template_name,
    ),
    currentVersion: asOptionalString(
      record.currentVersion,
      record.current_version,
      record.version,
    ),
    latestRunStatus: asOptionalString(
      record.latestRunStatus,
      record.latest_run_status,
    ),
    lastRunAt: asOptionalString(record.lastRunAt, record.last_run_at),
    updatedAt: asOptionalString(record.updatedAt, record.updated_at),
    riskLevel: asOptionalString(record.riskLevel, record.risk_level),
    pendingApprovals: asNumber(
      record.pendingApprovals,
      record.pending_approvals,
    ),
    runCount7d: asNumber(record.runCount7d, record.run_count_7d),
    successRate7d: asNumber(record.successRate7d, record.success_rate_7d),
    ownerName: asOptionalString(record.ownerName, record.owner_name),
    canEdit: asBoolean(record.canEdit, record.can_edit, record.editable),
    canPublish: asBoolean(record.canPublish, record.can_publish),
    canExecute: asBoolean(record.canExecute, record.can_execute),
  };
}

function normalizeWorkflowTemplateSummary(
  item: unknown,
): TenantWorkflowTemplateSummary {
  const record = toRecord(item);
  return {
    id: asNumber(record.id, record.template_id) ?? 0,
    code: asOptionalString(record.code),
    name: asString(record.name, record.title) ?? '',
    description: asOptionalString(record.description, record.summary),
    category: asOptionalString(record.category),
    status: asOptionalString(record.status),
    builderSurface: asOptionalString(
      record.builderSurface,
      record.builder_surface,
    ),
    releaseScope: asOptionalString(record.releaseScope, record.release_scope),
    tags: asOptionalStringArray(record.tags ?? record.tags_json),
    latestVersionNo: asNumber(record.latestVersionNo, record.latest_version_no),
    currentPublishedVersionId: asNumber(
      record.currentPublishedVersionId,
      record.current_published_version_id,
    ),
    publishedVersion: asOptionalString(
      record.publishedVersion,
      record.published_version,
      record.version,
    ),
    nodeCount: asNumber(record.nodeCount, record.node_count),
    edgeCount: asNumber(record.edgeCount, record.edge_count),
    publishedAt: asOptionalString(record.publishedAt, record.published_at),
    updatedAt: asOptionalString(record.updatedAt, record.updated_at),
    canCopy: asBoolean(record.canCopy, record.can_copy) ?? true,
  };
}

function normalizeRunSummary(item: unknown): TenantRunSummary {
  const record = toRecord(item);
  return {
    id: asNumber(record.id, record.run_id) ?? 0,
    name: asString(record.name, record.title) ?? '',
    workflowId: asNumber(record.workflowId, record.workflow_id),
    workflowName: asOptionalString(record.workflowName, record.workflow_name),
    solutionName: asOptionalString(record.solutionName, record.solution_name),
    status: asOptionalString(record.status),
    riskLevel: asOptionalString(record.riskLevel, record.risk_level),
    triggerSource: asOptionalString(
      record.triggerSource,
      record.trigger_source,
    ),
    currentNodeName: asOptionalString(
      record.currentNodeName,
      record.current_node_name,
    ),
    waitingApproval: asBoolean(
      record.waitingApproval,
      record.waiting_approval,
    ),
    waitingHumanInput: asBoolean(
      record.waitingHumanInput,
      record.waiting_human_input,
    ),
    costSummary: asOptionalString(record.costSummary, record.cost_summary),
    costAmount: asNumber(record.costAmount, record.cost_amount),
    startedAt: asOptionalString(record.startedAt, record.started_at),
    endedAt: asOptionalString(record.endedAt, record.ended_at),
    updatedAt: asOptionalString(record.updatedAt, record.updated_at),
    artifactCount: asNumber(record.artifactCount, record.artifact_count),
    statusBucket: asOptionalString(
      record.statusBucket,
      record.status_bucket,
    ),
    availableActions: asOptionalStringArray(
      record.availableActions ?? record.available_actions,
    ),
    canPause: asBoolean(record.canPause, record.can_pause),
    canResume: asBoolean(record.canResume, record.can_resume),
    canRetry: asBoolean(record.canRetry, record.can_retry),
    canTerminate: asBoolean(record.canTerminate, record.can_terminate),
  };
}

function normalizeNodeRun(item: unknown): TenantNodeRun {
  const record = toRecord(item);
  return {
    id: asNumber(record.id, record.node_run_id) ?? 0,
    nodeId: asOptionalString(record.nodeId, record.node_id),
    nodeName: asString(record.nodeName, record.node_name, record.name) ?? '',
    nodeType: asOptionalString(record.nodeType, record.node_type, record.type),
    status: asOptionalString(record.status),
    startedAt: asOptionalString(record.startedAt, record.started_at),
    endedAt: asOptionalString(record.endedAt, record.ended_at),
    durationMs: asNumber(record.durationMs, record.duration_ms),
    inputSummary: asOptionalString(record.inputSummary, record.input_summary),
    outputSummary: asOptionalString(record.outputSummary, record.output_summary),
    errorMessage: asOptionalString(record.errorMessage, record.error_message),
    checkpointId: asNumber(record.checkpointId, record.checkpoint_id),
  };
}

function normalizeRunEvent(item: unknown): TenantRunEvent {
  const record = toRecord(item);
  return {
    id: asString(record.id) ?? asNumber(record.id) ?? 'event',
    eventType: asString(record.eventType, record.event_type, record.type) ?? 'event',
    title: asOptionalString(record.title, record.name),
    summary: asOptionalString(record.summary, record.description, record.message),
    actorName: asOptionalString(record.actorName, record.actor_name),
    createdAt: asOptionalString(record.createdAt, record.created_at),
    checkpointId: asNumber(record.checkpointId, record.checkpoint_id),
  };
}

function normalizeApprovalRecord(item: unknown): TenantApprovalRecord {
  const record = toRecord(item);
  return {
    id: asString(record.id) ?? asNumber(record.id) ?? 'approval',
    title: asString(record.title, record.name) ?? '',
    status: asOptionalString(record.status),
    approverName: asOptionalString(record.approverName, record.approver_name),
    dueAt: asOptionalString(record.dueAt, record.due_at),
    detailPath: asOptionalString(record.detailPath, record.detail_path),
  };
}

function normalizeArtifactSummary(item: unknown): TenantArtifactSummary {
  const record = toRecord(item);
  return {
    id: asNumber(record.id, record.artifact_id) ?? 0,
    title: asString(record.title, record.name) ?? '',
    type: asOptionalString(record.type, record.artifact_type),
    status: asOptionalString(record.status),
    workflowId: asNumber(record.workflowId, record.workflow_id),
    workflowName: asOptionalString(record.workflowName, record.workflow_name),
    runId: asNumber(record.runId, record.run_id),
    runName: asOptionalString(record.runName, record.run_name),
    sourceVersion: asOptionalString(
      record.sourceVersion,
      record.source_version,
      record.version,
    ),
    sourceNodeName: asOptionalString(
      record.sourceNodeName,
      record.source_node_name,
    ),
    mimeType: asOptionalString(record.mimeType, record.mime_type),
    sizeBytes: asNumber(record.sizeBytes, record.size_bytes),
    previewText: asOptionalString(record.previewText, record.preview_text),
    feedbackCount: asNumber(record.feedbackCount, record.feedback_count),
    createdAt: asOptionalString(record.createdAt, record.created_at),
    updatedAt: asOptionalString(record.updatedAt, record.updated_at),
    downloadFilename: asOptionalString(
      record.downloadFilename,
      record.download_filename,
      record.filename,
    ),
    availableActions: asOptionalStringArray(
      record.availableActions ?? record.available_actions,
    ),
    canFeedback: asBoolean(record.canFeedback, record.can_feedback),
    canDownload: asBoolean(record.canDownload, record.can_download),
    downloadAvailable: asBoolean(
      record.downloadAvailable,
      record.download_available,
    ),
  };
}

function normalizeArtifactFeedback(item: unknown): TenantArtifactFeedback {
  const record = toRecord(item);
  return {
    id: asString(record.id) ?? asNumber(record.id) ?? 'feedback',
    kind: asOptionalString(record.kind, record.type, record.decision),
    rating: asNumber(record.rating),
    comment: asOptionalString(record.comment, record.comments, record.message),
    createdAt: asOptionalString(
      record.createdAt,
      record.created_at,
      record.submitted_at,
    ),
    createdBy: asOptionalString(record.createdBy, record.created_by),
  };
}

function normalizeHomePayload(value: unknown): TenantHomePayload {
  const payload = toRecord(unwrapPayload<Record<string, unknown>>(value));
  const summary =
    normalizeHomeSummary(payload.summary) ??
    normalizeHomeSummary(payload.metrics) ??
    normalizeHomeSummary(payload);
  const stats = toArray<unknown>(payload.stats).map(normalizeHomeStatCard);
  const builderCapabilities = toArray<unknown>(
    payload.builderCapabilities ?? payload.builder_capabilities,
  ).map(normalizeBuilderCapability);

  return {
    summary,
    stats,
    todos: toArray<unknown>(payload.todos).map(normalizeHomeTodo),
    alerts: toArray<unknown>(payload.alerts).map(normalizeHomeAlert),
    builderCapabilities,
    highlightedWorkflows: toArray<unknown>(
      payload.highlightedWorkflows ?? payload.highlighted_workflows,
    ).map(normalizeWorkflowSummary),
    latestRuns: toArray<unknown>(
      payload.latestRuns ?? payload.latest_runs,
    ).map(normalizeRunSummary),
    latestArtifacts: toArray<unknown>(
      payload.latestArtifacts ?? payload.latest_artifacts,
    ).map(normalizeArtifactSummary),
  };
}

function normalizeWorkflowDetail(value: unknown): TenantWorkflowDetail {
  const payload = toRecord(unwrapPayload<Record<string, unknown>>(value));
  const base = normalizeWorkflowSummary(payload);
  return {
    ...base,
    entrypoint: asOptionalString(payload.entrypoint),
    publishedVersion: asOptionalString(
      payload.publishedVersion,
      payload.published_version,
    ),
    latestVersion: asOptionalString(
      payload.latestVersion,
      payload.latest_version,
    ),
    activationSummary: asOptionalString(
      payload.activationSummary,
      payload.activation_summary,
    ),
    contextHealthSummary: asOptionalString(
      payload.contextHealthSummary,
      payload.context_health_summary,
    ),
    policySummary: asOptionalString(
      payload.policySummary,
      payload.policy_summary,
    ),
    approvalSummary: asOptionalString(
      payload.approvalSummary,
      payload.approval_summary,
    ),
    notes: asOptionalString(payload.notes),
    inputVariables: toArray<unknown>(
      payload.inputVariables ?? payload.input_variables,
    ).map(normalizeWorkflowInputVariable),
    outputContracts: toArray<unknown>(
      payload.outputContracts ?? payload.output_contracts,
    ).map(normalizeWorkflowOutputContract),
    nodes: toArray<unknown>(payload.nodes).map(normalizeWorkflowNode),
    edges: toArray<unknown>(payload.edges).map(normalizeWorkflowEdge),
    versions: toArray<unknown>(payload.versions).map(normalizeWorkflowVersion),
    relatedRuns: toArray<unknown>(
      payload.relatedRuns ?? payload.related_runs,
    ).map(normalizeRunSummary),
    relatedArtifacts: toArray<unknown>(
      payload.relatedArtifacts ?? payload.related_artifacts,
    ).map(normalizeArtifactSummary),
    builderCapabilities: toArray<unknown>(
      payload.builderCapabilities ?? payload.builder_capabilities,
    ).map(normalizeBuilderCapability),
  };
}

function normalizeRunDetail(value: unknown): TenantRunDetail {
  const payload = toRecord(unwrapPayload<Record<string, unknown>>(value));
  const base = normalizeRunSummary(payload);
  return {
    ...base,
    runKey: asOptionalString(payload.runKey, payload.run_key),
    snapshotVersion: asOptionalString(
      payload.snapshotVersion,
      payload.snapshot_version,
      payload.version,
    ),
    contractSummary: asOptionalString(
      payload.contractSummary,
      payload.contract_summary,
    ),
    inputPayload: payload.inputPayload ?? payload.input_payload,
    outputPayload: payload.outputPayload ?? payload.output_payload,
    nodeRuns: toArray<unknown>(
      payload.nodeRuns ?? payload.node_runs,
    ).map(normalizeNodeRun),
    artifacts: toArray<unknown>(payload.artifacts).map(normalizeArtifactSummary),
    approvals: toArray<unknown>(payload.approvals).map(normalizeApprovalRecord),
    recoveryEvents: toArray<unknown>(
      payload.recoveryEvents ?? payload.recovery_events ?? payload.events,
    ).map(normalizeRunEvent),
    evaluationSummary: asOptionalString(
      payload.evaluationSummary,
      payload.evaluation_summary,
    ),
    hostApprovalPath: asOptionalString(
      payload.hostApprovalPath,
      payload.host_approval_path,
    ),
  };
}

function normalizeArtifactDetail(value: unknown): TenantArtifactDetail {
  const payload = toRecord(unwrapPayload<Record<string, unknown>>(value));
  const base = normalizeArtifactSummary(payload);
  return {
    ...base,
    contentText: asOptionalString(payload.contentText, payload.content_text),
    contentMarkdown: asOptionalString(
      payload.contentMarkdown,
      payload.content_markdown,
    ),
    contentJson: toNullableRecord(payload.contentJson ?? payload.content_json),
    adoptionSummary: asOptionalString(
      payload.adoptionSummary,
      payload.adoption_summary,
    ),
    approvalStatus: asOptionalString(
      payload.approvalStatus,
      payload.approval_status,
    ),
    feedback: toArray<unknown>(payload.feedback).map(normalizeArtifactFeedback),
    downloadUrl: asOptionalString(payload.downloadUrl, payload.download_url),
  };
}

type TenantListResource = 'artifact' | 'run' | 'workflow';

function buildListSearchParams(
  resource: TenantListResource,
  query: TenantListQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  params.set('page[number]', String(query.page ?? 1));
  params.set('page[size]', String(query.size ?? 12));

  if (query.keyword) {
    if (resource === 'run') {
      params.set('filter[code][ilike]', query.keyword);
    } else {
      params.set('filter[name][ilike]', query.keyword);
    }
  }
  if (query.statuses?.length) {
    params.set('filter[status][in]', query.statuses.join(','));
    if (query.statuses.length === 1) {
      params.set('filter[status][eq]', query.statuses[0]);
    }
  }

  if (resource === 'workflow' && query.builderModes?.length) {
    params.set('filter[builder_mode][in]', query.builderModes.join(','));
  }

  if (resource === 'artifact' && query.types?.length) {
    params.set('filter[artifact_type][in]', query.types.join(','));
  }
  if (resource !== 'workflow' && query.workflowId != null) {
    params.set('filter[workflow_id][eq]', String(query.workflowId));
  }

  return params;
}

export async function getTenantHomeApi(): Promise<TenantHomePayload> {
  const response = await getClient().get<unknown>(`${resolveTenantApiBase()}/home`);
  return normalizeHomePayload(response);
}

export async function getTenantBuilderCapabilitiesApi(): Promise<
  TenantBuilderCapability[]
> {
  const response = await getClient().get<unknown>(
    `${resolveTenantApiBase()}/builder-capabilities`,
  );
  const payload = toRecord(unwrapPayload<Record<string, unknown>>(response));
  const items = toArray<unknown>(payload.items);
  if (items.length > 0) {
    return items.map(normalizeBuilderCapability);
  }

  return [
    {
      code: 'tenant_simple_builder',
      enabled:
        asBoolean(
          payload.simpleBuilderEnabled,
          payload.simple_builder_enabled,
        ) ?? false,
      limit: asNumber(payload.maxSimpleSteps, payload.max_simple_steps),
    },
    {
      code: 'tenant_template_editor',
      enabled:
        asBoolean(
          payload.templateEditorEnabled,
          payload.template_editor_enabled,
        ) ?? false,
    },
    {
      code: 'agentic_builder',
      enabled:
        asBoolean(
          payload.agenticBuilderEnabled,
          payload.agentic_builder_enabled,
        ) ?? false,
      limit: asNumber(payload.maxAgenticSteps, payload.max_agentic_steps),
    },
  ];
}

export async function listTenantWorkflowsApi(
  query: TenantListQuery = {},
): Promise<PaginatedResult<TenantWorkflowSummary>> {
  const params = buildListSearchParams('workflow', query);
  const response = await getClient().get<unknown>(
    `${resolveTenantApiBase()}/workflows?${params.toString()}`,
  );
  return buildListResult(response, normalizeWorkflowSummary);
}

export async function listTenantWorkflowTemplatesApi(
  query: TenantTemplateListQuery = {},
): Promise<PaginatedResult<TenantWorkflowTemplateSummary>> {
  const params = new URLSearchParams();
  params.set('page[number]', String(query.page ?? 1));
  params.set('page[size]', String(query.size ?? 6));
  if (query.keyword) {
    params.set('filter[name][ilike]', query.keyword);
  }
  const response = await getClient().get<unknown>(
    `${resolveTenantApiBase()}/templates?${params.toString()}`,
  );
  return buildListResult(response, normalizeWorkflowTemplateSummary);
}

export async function createTenantWorkflowApi(
  payload: TenantWorkflowUpsertPayload,
): Promise<TenantWorkflowDetail> {
  const response = await getClient().post<unknown>(
    `${resolveTenantApiBase()}/workflows`,
    payload,
  );
  return normalizeWorkflowDetail(response);
}

export async function copyTenantWorkflowFromTemplateApi(
  payload: TenantWorkflowCopyPayload,
): Promise<TenantWorkflowDetail> {
  const response = await getClient().post<unknown>(
    `${resolveTenantApiBase()}/workflows/copy-from-template`,
    {
      description: payload.description,
      name: payload.name,
      template_id: payload.templateId,
      template_version_id: payload.templateVersionId,
    },
  );
  return normalizeWorkflowDetail(response);
}

export async function getTenantWorkflowDetailApi(
  workflowId: number,
): Promise<TenantWorkflowDetail> {
  const response = await getClient().get<unknown>(
    `${resolveTenantApiBase()}/workflows/${workflowId}`,
  );
  return normalizeWorkflowDetail(response);
}

export async function listTenantWorkflowVersionsApi(
  workflowId: number,
): Promise<TenantWorkflowVersionSummary[]> {
  const response = await getClient().get<unknown>(
    `${resolveTenantApiBase()}/workflows/${workflowId}/versions`,
  );
  const payload = extractListContainer(response);
  const items = toArray<unknown>(payload.items);
  return items.map(normalizeWorkflowVersion);
}

export async function updateTenantWorkflowApi(
  workflowId: number,
  payload: TenantWorkflowUpsertPayload,
): Promise<TenantWorkflowDetail> {
  const response = await getClient().put<unknown>(
    `${resolveTenantApiBase()}/workflows/${workflowId}`,
    payload,
  );
  return normalizeWorkflowDetail(response);
}

export async function publishTenantWorkflowApi(
  workflowId: number,
): Promise<TenantWorkflowDetail> {
  const response = await getClient().post<unknown>(
    `${resolveTenantApiBase()}/workflows/${workflowId}/publish`,
  );
  return normalizeWorkflowDetail(response);
}

export async function executeTenantWorkflowApi(
  workflowId: number,
): Promise<TenantRunDetail> {
  const response = await getClient().post<unknown>(
    `${resolveTenantApiBase()}/workflows/${workflowId}/run`,
  );
  return normalizeRunDetail(response);
}

export async function listTenantRunsApi(
  query: TenantListQuery = {},
): Promise<PaginatedResult<TenantRunSummary>> {
  const params = buildListSearchParams('run', query);
  const response = await getClient().get<unknown>(
    `${resolveTenantApiBase()}/runs?${params.toString()}`,
  );
  return buildListResult(response, normalizeRunSummary);
}

export async function getTenantRunDetailApi(
  runId: number,
): Promise<TenantRunDetail> {
  const response = await getClient().get<unknown>(
    `${resolveTenantApiBase()}/runs/${runId}`,
  );
  return normalizeRunDetail(response);
}

export async function pauseTenantRunApi(runId: number): Promise<TenantRunDetail> {
  const response = await getClient().post<unknown>(
    `${resolveTenantApiBase()}/runs/${runId}/pause`,
  );
  return normalizeRunDetail(response);
}

export async function resumeTenantRunApi(
  runId: number,
): Promise<TenantRunDetail> {
  const response = await getClient().post<unknown>(
    `${resolveTenantApiBase()}/runs/${runId}/resume`,
  );
  return normalizeRunDetail(response);
}

export async function retryTenantRunApi(runId: number): Promise<TenantRunDetail> {
  const response = await getClient().post<unknown>(
    `${resolveTenantApiBase()}/runs/${runId}/retry`,
  );
  return normalizeRunDetail(response);
}

export async function terminateTenantRunApi(
  runId: number,
): Promise<TenantRunDetail> {
  const response = await getClient().post<unknown>(
    `${resolveTenantApiBase()}/runs/${runId}/terminate`,
  );
  return normalizeRunDetail(response);
}

export async function listTenantArtifactsApi(
  query: TenantListQuery = {},
): Promise<PaginatedResult<TenantArtifactSummary>> {
  const params = buildListSearchParams('artifact', query);
  const response = await getClient().get<unknown>(
    `${resolveTenantApiBase()}/artifacts?${params.toString()}`,
  );
  return buildListResult(response, normalizeArtifactSummary);
}

export async function getTenantArtifactDetailApi(
  artifactId: number,
): Promise<TenantArtifactDetail> {
  const response = await getClient().get<unknown>(
    `${resolveTenantApiBase()}/artifacts/${artifactId}`,
  );
  return normalizeArtifactDetail(response);
}

export async function submitTenantArtifactFeedbackApi(
  artifactId: number,
  payload: TenantArtifactFeedbackPayload,
): Promise<TenantArtifactDetail> {
  const response = await getClient().post<unknown>(
    `${resolveTenantApiBase()}/artifacts/${artifactId}/feedback`,
    payload,
  );
  return normalizeArtifactDetail(response);
}

export async function downloadTenantArtifactApi(
  artifactId: number,
  options: { signedDownloadUrl?: string } = {},
): Promise<Blob> {
  const client = getClient();
  const endpoint = `${resolveTenantApiBase()}/artifacts/${artifactId}/download`;

  if (client.download) {
    try {
      return await client.download(endpoint);
    } catch (error) {
      if (!options.signedDownloadUrl) {
        throw error instanceof Error
          ? error
          : new Error('Artifact download failed');
      }
    }
  }

  if (options.signedDownloadUrl) {
    const response = await fetch(options.signedDownloadUrl);
    if (!response.ok) {
      throw new Error('Artifact download failed');
    }
    return await response.blob();
  }

  throw new Error('Download is not supported by the current tenant client');
}
