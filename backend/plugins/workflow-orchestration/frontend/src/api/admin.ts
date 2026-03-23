import type {
  AdminOverviewResponse,
  AdminReleaseListQuery,
  AdminRunDetail,
  AdminRunListQuery,
  AdminTemplateListQuery,
  CreateAdminTemplatePayload,
  GlobalRunSummary,
  PaginatedResult,
  PublishTemplatePayload,
  WorkflowArtifactSummary,
  WorkflowExecutionCheckpoint,
  WorkflowGraphEdge,
  WorkflowGraphNode,
  WorkflowGraphSnapshot,
  WorkflowNodeRunSummary,
  WorkflowReleaseSummary,
  WorkflowRunTimelineEvent,
  WorkflowTemplateDetail,
  WorkflowTemplateEdge,
  WorkflowTemplateNode,
  WorkflowTemplateSummary,
  WorkflowTemplateVersion,
} from '../types/admin';

import { requestClient } from '@novus/plugin-shared';

const PLUGIN_API_BASE = '/admin/plugins/workflow-orchestration/api';

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isApiEnvelope(value: unknown): value is { code: number; data: unknown } {
  return isRecord(value) && 'data' in value && 'code' in value;
}

function unwrapApiData<T>(payload: unknown): T {
  let current: unknown = payload;
  let depth = 0;

  while (isApiEnvelope(current) && depth < 8) {
    current = current.data;
    depth += 1;
  }

  return current as T;
}

function toRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function toRecordArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map((item) => toRecord(item)) : [];
}

function toNumber(value: unknown, fallback = 0): number {
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : fallback;
}

function toNullableNumber(value: unknown): null | number {
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : null;
}

function toNullableString(value: unknown): null | string {
  if (value === undefined || value === null || value === '') {
    return null;
  }
  return String(value);
}

function toStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

function normalizePaginatedResult<T>(payload: unknown): PaginatedResult<T> {
  const data = unwrapApiData<unknown>(payload);

  if (Array.isArray(data)) {
    return {
      items: data as T[],
      page: 1,
      pageSize: data.length,
      total: data.length,
    };
  }

  if (!isRecord(data)) {
    return {
      items: [],
      page: 1,
      pageSize: 0,
      total: 0,
    };
  }

  const items = Array.isArray(data.items)
    ? (data.items as T[])
    : Array.isArray(data.records)
      ? (data.records as T[])
      : [];

  return {
    items,
    page: toNumber(data.page ?? data.page_number, 1),
    pageSize: toNumber(data.page_size ?? data.pageSize ?? data.size, items.length),
    total: toNumber(data.total ?? data.count, items.length),
  };
}

function appendParam(
  target: Record<string, number | string>,
  key: string,
  value: null | number | string | undefined,
): void {
  if (value === undefined || value === null || value === '') {
    return;
  }
  target[key] = value;
}

function buildBaseQueryParams(query: {
  page?: number;
  pageSize?: number;
  sort?: string;
}): Record<string, number | string> {
  const params: Record<string, number | string> = {};
  appendParam(params, 'page[number]', query.page ?? 1);
  appendParam(params, 'page[size]', query.pageSize ?? 10);
  appendParam(params, 'sort', query.sort);
  return params;
}

function buildTemplateListParams(
  query: AdminTemplateListQuery,
): Record<string, number | string> {
  const params = buildBaseQueryParams(query);
  appendParam(params, 'filter[name][ilike]', query.keyword);
  appendParam(params, 'filter[code][eq]', query.code);
  appendParam(params, 'filter[status][eq]', query.status);
  appendParam(params, 'filter[category][eq]', query.category);
  appendParam(params, 'filter[builder_surface][eq]', query.builderSurface);
  appendParam(params, 'filter[release_scope][eq]', query.releaseScope);
  appendParam(params, 'filter[created_by][eq]', query.createdBy);
  return params;
}

function buildReleaseListParams(
  query: AdminReleaseListQuery,
): Record<string, number | string> {
  const params = buildBaseQueryParams(query);
  appendParam(params, 'filter[workflow_kind][eq]', query.workflowKind);
  appendParam(params, 'filter[workflow_id][eq]', query.workflowId);
  appendParam(params, 'filter[status][eq]', query.status);
  appendParam(params, 'filter[release_scope][eq]', query.releaseScope);
  appendParam(params, 'filter[channel][eq]', query.channel);
  appendParam(params, 'filter[environment_code][eq]', query.environmentCode);
  return params;
}

function buildRunListParams(
  query: AdminRunListQuery,
): Record<string, number | string> {
  const params = buildBaseQueryParams(query);
  appendParam(params, 'filter[code][ilike]', query.keyword);
  appendParam(params, 'filter[status][eq]', query.status);
  appendParam(params, 'filter[tenant_id][eq]', query.tenantId);
  appendParam(params, 'filter[workflow_id][eq]', query.workflowId);
  appendParam(params, 'filter[workflow_template_id][eq]', query.workflowTemplateId);
  appendParam(params, 'filter[workflow_version_id][eq]', query.workflowVersionId);
  appendParam(params, 'filter[release_id][eq]', query.releaseId);
  return params;
}

function normalizeGraphNode(raw: Record<string, unknown>): WorkflowGraphNode {
  return {
    id: String(raw.id ?? raw.node_key ?? raw.key ?? ''),
    label: toNullableString(raw.label ?? raw.title ?? raw.node_name),
    type: toNullableString(raw.type ?? raw.node_type),
    category: toNullableString(raw.category),
    risk_level: toNullableString(raw.risk_level),
    status: toNullableString(raw.status),
    capability_key: toNullableString(raw.capability_key),
    readonly: Boolean(raw.readonly),
  };
}

function normalizeGraphEdge(raw: Record<string, unknown>): WorkflowGraphEdge {
  return {
    id: toNullableString(raw.id ?? raw.edge_key),
    label: toNullableString(raw.label),
    source: String(raw.source ?? raw.from_node_key ?? ''),
    target: String(raw.target ?? raw.to_node_key ?? ''),
  };
}

function normalizeGraphSnapshot(raw: unknown): WorkflowGraphSnapshot {
  const root = toRecord(raw);
  const graph = toRecord(root.graph);
  const nodeSource = Array.isArray(root.nodes)
    ? root.nodes
    : Array.isArray(graph.nodes)
      ? graph.nodes
      : [];
  const edgeSource = Array.isArray(root.edges)
    ? root.edges
    : Array.isArray(graph.edges)
      ? graph.edges
      : [];

  return {
    nodes: nodeSource.map((item) => normalizeGraphNode(toRecord(item))),
    edges: edgeSource.map((item) => normalizeGraphEdge(toRecord(item))),
    root_node_keys: Array.isArray(root.root_node_keys)
      ? root.root_node_keys.map((item) => String(item))
      : [],
    metadata: isRecord(root.metadata) ? root.metadata : null,
  };
}

function normalizeTemplateNode(raw: Record<string, unknown>): WorkflowTemplateNode {
  return {
    id: toNumber(raw.id),
    template_id: toNullableNumber(raw.template_id),
    node_key: String(raw.node_key ?? ''),
    node_type: String(raw.node_type ?? ''),
    title: String(raw.title ?? raw.node_key ?? ''),
    description: toNullableString(raw.description),
    sort_order: toNumber(raw.sort_order, 0),
    timeout_minutes: toNullableNumber(raw.timeout_minutes),
    retry_limit: toNullableNumber(raw.retry_limit),
    config_json: toRecord(raw.config_json),
    position_json: toRecord(raw.position_json),
    input_contract_json: toRecord(raw.input_contract_json),
    output_contract_json: toRecord(raw.output_contract_json),
    policy_json: toRecord(raw.policy_json),
    metadata_json: toRecord(raw.metadata_json),
  };
}

function normalizeTemplateEdge(raw: Record<string, unknown>): WorkflowTemplateEdge {
  return {
    id: toNumber(raw.id),
    template_id: toNullableNumber(raw.template_id),
    edge_key: String(raw.edge_key ?? raw.id ?? ''),
    from_node_key: String(raw.from_node_key ?? ''),
    from_port: toNullableString(raw.from_port),
    to_node_key: String(raw.to_node_key ?? ''),
    to_port: toNullableString(raw.to_port),
    sort_order: toNumber(raw.sort_order, 0),
    condition_json: toRecord(raw.condition_json),
    metadata_json: toRecord(raw.metadata_json),
  };
}

function normalizeTemplateVersion(raw: Record<string, unknown>): WorkflowTemplateVersion {
  const snapshot = normalizeGraphSnapshot(raw.snapshot_json);
  const versionNo = toNullableNumber(raw.version_no);

  return {
    id: toNumber(raw.id),
    template_id: toNullableNumber(raw.template_id),
    version_no: versionNo,
    version_label: versionNo === null ? null : `v${versionNo}`,
    status: toNullableString(raw.status),
    snapshot_version: toNullableString(raw.snapshot_version),
    workflow_schema_version: toNullableString(raw.workflow_schema_version),
    snapshot_hash: toNullableString(raw.snapshot_hash),
    snapshot_json: toRecord(raw.snapshot_json),
    change_summary: toNullableString(raw.change_summary),
    release_notes: toNullableString(raw.release_notes),
    compiled_at: toNullableString(raw.compiled_at),
    compiled_by: toNullableNumber(raw.compiled_by),
    published_at: toNullableString(raw.published_at),
    published_by: toNullableNumber(raw.published_by),
    is_latest: Boolean(raw.is_latest),
    is_published: Boolean(raw.is_published),
    created_by: toNullableNumber(raw.created_by),
    updated_by: toNullableNumber(raw.updated_by),
    created_at: toNullableString(raw.created_at),
    updated_at: toNullableString(raw.updated_at),
    node_count: snapshot.nodes?.length ?? 0,
    edge_count: snapshot.edges?.length ?? 0,
  };
}

function normalizeTemplateSummary(raw: Record<string, unknown>): WorkflowTemplateSummary {
  const latestVersionNo = toNullableNumber(raw.latest_version_no);

  return {
    id: toNumber(raw.id),
    name: String(raw.name ?? ''),
    code: toNullableString(raw.code),
    description: toNullableString(raw.description),
    category: toNullableString(raw.category),
    status: toNullableString(raw.status),
    builder_surface: toNullableString(raw.builder_surface),
    release_scope: toNullableString(raw.release_scope),
    tags_json: toStringArray(raw.tags_json),
    metadata_json: toRecord(raw.metadata_json),
    risk_policy_json: toRecord(raw.risk_policy_json),
    contract_summary_json: toRecord(raw.contract_summary_json),
    default_trigger_json: toRecord(raw.default_trigger_json),
    latest_version_no: latestVersionNo,
    latest_version_id: toNullableNumber(raw.latest_version_id),
    latest_version_label:
      latestVersionNo === null ? null : `v${latestVersionNo}`,
    current_published_version_id: toNullableNumber(raw.current_published_version_id),
    latest_release_id: toNullableNumber(raw.latest_release_id),
    created_by: toNullableNumber(raw.created_by),
    updated_by: toNullableNumber(raw.updated_by),
    published_by: toNullableNumber(raw.published_by),
    published_at: toNullableString(raw.published_at),
    created_at: toNullableString(raw.created_at),
    updated_at: toNullableString(raw.updated_at),
  };
}

function normalizeReleaseSummary(raw: Record<string, unknown>): WorkflowReleaseSummary {
  return {
    id: toNumber(raw.id),
    code: toNullableString(raw.code),
    workflow_kind: toNullableString(raw.workflow_kind),
    workflow_id: toNullableNumber(raw.workflow_id),
    workflow_code: toNullableString(raw.workflow_code),
    workflow_name: toNullableString(raw.workflow_name),
    workflow_version_id: toNullableNumber(raw.workflow_version_id),
    environment_id: toNullableNumber(raw.environment_id),
    environment_code: toNullableString(raw.environment_code),
    release_scope: toNullableString(raw.release_scope),
    channel: toNullableString(raw.channel),
    status: toNullableString(raw.status),
    rollout_json: toRecord(raw.rollout_json),
    notes: toNullableString(raw.notes),
    rollback_of_release_id: toNullableNumber(raw.rollback_of_release_id),
    rollback_target_release_id: toNullableNumber(raw.rollback_target_release_id),
    published_by: toNullableNumber(raw.published_by),
    reviewed_by: toNullableNumber(raw.reviewed_by),
    published_at: toNullableString(raw.published_at),
    reviewed_at: toNullableString(raw.reviewed_at),
    created_by: toNullableNumber(raw.created_by),
    updated_by: toNullableNumber(raw.updated_by),
    created_at: toNullableString(raw.created_at),
    updated_at: toNullableString(raw.updated_at),
  };
}

function normalizeTemplateDetail(raw: Record<string, unknown>): WorkflowTemplateDetail {
  return {
    ...normalizeTemplateSummary(raw),
    nodes: toRecordArray(raw.nodes).map((item) => normalizeTemplateNode(item)),
    edges: toRecordArray(raw.edges).map((item) => normalizeTemplateEdge(item)),
    latest_version: isRecord(raw.latest_version)
      ? normalizeTemplateVersion(toRecord(raw.latest_version))
      : null,
    published_version: isRecord(raw.published_version)
      ? normalizeTemplateVersion(toRecord(raw.published_version))
      : null,
    latest_release: isRecord(raw.latest_release)
      ? normalizeReleaseSummary(toRecord(raw.latest_release))
      : null,
    version_count: toNumber(raw.version_count, 0),
    builder_capabilities: toRecordArray(raw.builder_capabilities).map((item) => ({
      code: String(item.code ?? ''),
      category: toNullableString(item.category),
      label: toNullableString(item.label),
      description: toNullableString(item.description),
      reason: toNullableString(item.reason),
      available: item.available === false ? false : true,
    })),
    editable_segments: toRecordArray(raw.editable_segments).map((item) => ({
      code: toNullableString(item.code),
      description: toNullableString(item.description),
      kind: toNullableString(item.kind),
      label: toNullableString(item.label),
    })),
    locked_segments: toRecordArray(raw.locked_segments).map((item) => ({
      code: toNullableString(item.code),
      description: toNullableString(item.description),
      kind: toNullableString(item.kind),
      label: toNullableString(item.label),
    })),
    parameterized_segments: toRecordArray(raw.parameterized_segments).map((item) => ({
      code: toNullableString(item.code),
      description: toNullableString(item.description),
      kind: toNullableString(item.kind),
      label: toNullableString(item.label),
    })),
  };
}

function normalizeOverview(
  overviewPayload: unknown,
  metricsPayload: unknown,
): AdminOverviewResponse {
  const overview = toRecord(unwrapApiData(overviewPayload));
  const metrics = toRecord(unwrapApiData(metricsPayload));

  const templateStatusCounts = toRecord(toRecord(overview.template_summary).status_counts);
  const releaseStatusCounts = toRecord(toRecord(overview.release_summary).status_counts);
  const runStatusCounts = toRecord(toRecord(overview.runtime_summary).run_status_counts);
  const artifactStatusCounts = toRecord(toRecord(overview.runtime_summary).artifact_status_counts);

  return {
    template_summary: {
      total_templates: toNumber(toRecord(overview.template_summary).total_templates, 0),
      total_versions: toNumber(toRecord(overview.template_summary).total_versions, 0),
      total_runs: toNumber(toRecord(overview.template_summary).total_runs, 0),
      total_artifacts: toNumber(toRecord(overview.template_summary).total_artifacts, 0),
      status_counts: Object.fromEntries(
        Object.entries(templateStatusCounts).map(([key, count]) => [key, toNumber(count, 0)]),
      ),
    },
    release_summary: {
      total_releases: toNumber(toRecord(overview.release_summary).total_releases, 0),
      latest_published_at: toNullableString(
        toRecord(overview.release_summary).latest_published_at,
      ),
      status_counts: Object.fromEntries(
        Object.entries(releaseStatusCounts).map(([key, count]) => [key, toNumber(count, 0)]),
      ),
    },
    runtime_summary: {
      run_status_counts: Object.fromEntries(
        Object.entries(runStatusCounts).map(([key, count]) => [key, toNumber(count, 0)]),
      ),
      artifact_status_counts: Object.fromEntries(
        Object.entries(artifactStatusCounts).map(([key, count]) => [key, toNumber(count, 0)]),
      ),
    },
    settings_summary: {
      config_rows: toRecordArray(toRecord(overview.settings_summary).config_rows),
      environment_count: toNumber(toRecord(overview.settings_summary).environment_count, 0),
      zero_host_boundary: toRecord(toRecord(overview.settings_summary).zero_host_boundary),
    },
    metrics,
  };
}

function normalizeRunNodeCounts(value: unknown): GlobalRunSummary['node_counts'] {
  const raw = toRecord(value);
  return {
    total: toNumber(raw.total, 0),
    running: toNumber(raw.running, 0),
    waiting_human: toNumber(raw.waiting_human, 0),
    failed: toNumber(raw.failed, 0),
    succeeded: toNumber(raw.succeeded, 0),
  };
}

function normalizeRunSummary(raw: Record<string, unknown>): GlobalRunSummary {
  return {
    id: toNumber(raw.id),
    name: toNullableString(raw.name),
    tenant_id: toNullableNumber(raw.tenant_id),
    workflow_template_id: toNullableNumber(raw.workflow_template_id),
    tenant_workflow_id: toNullableNumber(raw.tenant_workflow_id),
    workflow_id: toNullableNumber(raw.workflow_id),
    workflow_version_id: toNullableNumber(raw.workflow_version_id),
    release_id: toNullableNumber(raw.release_id),
    trigger_id: toNullableNumber(raw.trigger_id),
    environment_id: toNullableNumber(raw.environment_id),
    parent_run_id: toNullableNumber(raw.parent_run_id),
    code: toNullableString(raw.code),
    entrypoint: toNullableString(raw.entrypoint),
    trigger_source: toNullableString(raw.trigger_source),
    initiated_from: toNullableString(raw.initiated_from),
    mode: toNullableString(raw.mode),
    status: toNullableString(raw.status),
    status_bucket: toNullableString(raw.status_bucket),
    available_actions: toStringArray(raw.available_actions),
    initiated_by: toNullableNumber(raw.initiated_by),
    started_by_type: toNullableString(raw.started_by_type),
    started_by_id: toNullableNumber(raw.started_by_id),
    current_node_key: toNullableString(raw.current_node_key),
    current_node_name: toNullableString(raw.current_node_name),
    trace_id: toNullableString(raw.trace_id),
    idempotency_key: toNullableString(raw.idempotency_key),
    retry_count: toNumber(raw.retry_count, 0),
    input_payload: raw.input_payload,
    output_payload: raw.output_payload,
    final_output: raw.final_output,
    budget_snapshot_json: toRecord(raw.budget_snapshot_json),
    risk_snapshot_json: toRecord(raw.risk_snapshot_json),
    cost_summary: toRecord(raw.cost_summary),
    cost_summary_text: toNullableString(raw.cost_summary_text),
    cost_amount: toNullableNumber(raw.cost_amount),
    error_summary: toNullableString(raw.error_summary),
    waiting_approval: Boolean(raw.waiting_approval),
    waiting_human_input: Boolean(raw.waiting_human_input),
    can_pause: Boolean(raw.can_pause),
    can_resume: Boolean(raw.can_resume),
    can_retry: Boolean(raw.can_retry),
    can_terminate: Boolean(raw.can_terminate),
    started_at: toNullableString(raw.started_at),
    ended_at: toNullableString(raw.ended_at),
    last_heartbeat_at: toNullableString(raw.last_heartbeat_at),
    created_at: toNullableString(raw.created_at),
    updated_at: toNullableString(raw.updated_at),
    node_counts: normalizeRunNodeCounts(raw.node_counts),
    workflow_name: toNullableString(raw.workflow_name),
    template_name: toNullableString(raw.template_name),
    artifact_count: toNullableNumber(raw.artifact_count),
    risk_level: toNullableString(raw.risk_level),
  };
}

function normalizeNodeRunSummary(raw: Record<string, unknown>): WorkflowNodeRunSummary {
  return {
    id: toNumber(raw.id),
    workflow_run_id: toNullableNumber(raw.workflow_run_id),
    node_key: toNullableString(raw.node_key),
    node_label: toNullableString(raw.node_label ?? raw.node_name),
    node_type: toNullableString(raw.node_type),
    status: toNullableString(raw.status),
    status_bucket: toNullableString(raw.status_bucket),
    attempt_no: toNullableNumber(raw.attempt_no),
    executor_type: toNullableString(raw.executor_type),
    executor_ref: toNullableString(raw.executor_ref),
    input_payload: raw.input_payload,
    output_payload: raw.output_payload,
    error_detail: toNullableString(raw.error_detail ?? raw.error_summary),
    duration_ms: toNullableNumber(raw.duration_ms),
    started_at: toNullableString(raw.started_at),
    ended_at: toNullableString(raw.ended_at),
    created_at: toNullableString(raw.created_at),
  };
}

function normalizeCheckpoint(raw: Record<string, unknown>): WorkflowExecutionCheckpoint {
  return {
    id: toNullableNumber(raw.id) ?? String(raw.id ?? ''),
    workflow_run_id: toNullableNumber(raw.workflow_run_id),
    workflow_node_run_id: toNullableNumber(raw.workflow_node_run_id),
    checkpoint_type: toNullableString(raw.checkpoint_type),
    snapshot_payload: raw.snapshot_payload ?? raw.snapshot_json,
    artifact_refs: Array.isArray(raw.artifact_refs)
      ? raw.artifact_refs.map((item) =>
          typeof item === 'number' || typeof item === 'string' ? item : String(item),
        )
      : [],
    created_at: toNullableString(raw.created_at),
  };
}

function normalizeTimelineEvent(raw: Record<string, unknown>): WorkflowRunTimelineEvent {
  return {
    id: toNullableNumber(raw.id) ?? String(raw.id ?? ''),
    event_type: toNullableString(raw.event_type),
    status_from: toNullableString(raw.status_from),
    status_to: toNullableString(raw.status_to),
    message: toNullableString(raw.message),
    detail: raw.detail ?? raw.payload_json,
    occurred_at: toNullableString(raw.occurred_at),
    created_at: toNullableString(raw.created_at),
  };
}

function normalizeArtifactSummary(raw: Record<string, unknown>): WorkflowArtifactSummary {
  return {
    id: toNumber(raw.id),
    workflow_run_id: toNullableNumber(raw.workflow_run_id),
    title: toNullableString(raw.title),
    name: toNullableString(raw.name),
    summary: toNullableString(raw.summary),
    preview_text: toNullableString(raw.preview_text),
    artifact_type: toNullableString(raw.artifact_type),
    status: toNullableString(raw.status),
    available_actions: toStringArray(raw.available_actions),
    content_json: isRecord(raw.content_json) ? raw.content_json : null,
    content_text: toNullableString(raw.content_text),
    mime_type: toNullableString(raw.mime_type),
    visibility: toNullableString(raw.visibility),
    storage_uri: toNullableString(raw.storage_uri),
    storage_path: toNullableString(raw.storage_path),
    size_bytes: toNullableNumber(raw.size_bytes),
    hash: toNullableString(raw.hash),
    feedback_summary: isRecord(raw.feedback_summary) ? raw.feedback_summary : null,
    download_filename: toNullableString(raw.download_filename),
    created_at: toNullableString(raw.created_at),
    expires_at: toNullableString(raw.expires_at),
  };
}

function normalizeRunDetail(raw: Record<string, unknown>): AdminRunDetail {
  return {
    run: isRecord(raw.run) ? normalizeRunSummary(toRecord(raw.run)) : undefined,
    node_runs: toRecordArray(raw.node_runs).map((item) => normalizeNodeRunSummary(item)),
    checkpoints: toRecordArray(raw.checkpoints).map((item) => normalizeCheckpoint(item)),
    events: toRecordArray(raw.events).map((item) => normalizeTimelineEvent(item)),
    artifacts: toRecordArray(raw.artifacts).map((item) => normalizeArtifactSummary(item)),
    execution_graph: normalizeGraphSnapshot(raw.execution_graph),
  };
}

export async function getAdminOverviewApi(): Promise<AdminOverviewResponse> {
  const [overviewResponse, metricsResponse] = await Promise.all([
    requestClient.get<unknown>(`${PLUGIN_API_BASE}/overview`),
    requestClient.get<unknown>(`${PLUGIN_API_BASE}/metrics`),
  ]);
  return normalizeOverview(overviewResponse, metricsResponse);
}

export async function getAdminMetricsApi(): Promise<Record<string, unknown>> {
  const response = await requestClient.get<unknown>(`${PLUGIN_API_BASE}/metrics`);
  return unwrapApiData<Record<string, unknown>>(response);
}

export async function listAdminTemplatesApi(
  query: AdminTemplateListQuery = {},
): Promise<PaginatedResult<WorkflowTemplateSummary>> {
  const response = await requestClient.get<unknown>(`${PLUGIN_API_BASE}/templates`, {
    params: buildTemplateListParams(query),
  });
  const normalized = normalizePaginatedResult<Record<string, unknown>>(response);
  return {
    ...normalized,
    items: normalized.items.map((item) => normalizeTemplateSummary(toRecord(item))),
  };
}

export async function getAdminTemplateDetailApi(
  templateId: number | string,
): Promise<WorkflowTemplateDetail> {
  const response = await requestClient.get<unknown>(
    `${PLUGIN_API_BASE}/templates/${templateId}`,
  );
  return normalizeTemplateDetail(toRecord(unwrapApiData(response)));
}

export async function createAdminTemplateApi(
  payload: CreateAdminTemplatePayload,
): Promise<WorkflowTemplateDetail> {
  const body: Record<string, unknown> = {
    code: payload.code,
    name: payload.name,
    description: payload.description ?? null,
    category: payload.category ?? null,
    status: payload.status ?? 'draft',
    builder_surface: payload.builderSurface ?? 'platform_workflow_studio',
    release_scope: payload.releaseScope ?? 'selected_tenants',
    tags_json: payload.tagsJson ?? [],
    metadata_json: payload.metadataJson ?? {},
    risk_policy_json: payload.riskPolicyJson ?? {},
    contract_summary_json: payload.contractSummaryJson ?? {},
    default_trigger_json: payload.defaultTriggerJson ?? {},
    snapshot: {
      snapshot_version: payload.snapshot.snapshotVersion ?? '1.0.0',
      workflow_schema_version:
        payload.snapshot.workflowSchemaVersion ?? '1.0.0',
      contract_refs: payload.snapshot.contractRefs ?? [],
      control_envelope_schema: payload.snapshot.controlEnvelopeSchema ?? {},
      graph: {
        nodes: payload.snapshot.graph?.nodes ?? [],
        edges: payload.snapshot.graph?.edges ?? [],
      },
      entrypoints: payload.snapshot.entrypoints ?? [],
      defaults: payload.snapshot.defaults ?? {},
      risk_policy_snapshot: payload.snapshot.riskPolicySnapshot ?? {},
      trigger_snapshot: payload.snapshot.triggerSnapshot ?? {},
      artifact_contracts: payload.snapshot.artifactContracts ?? [],
      output_contracts: payload.snapshot.outputContracts ?? [],
      builder_surface:
        payload.snapshot.builderSurface ?? payload.builderSurface ?? 'platform_workflow_studio',
      compiled_at: payload.snapshot.compiledAt ?? null,
      compiled_by: payload.snapshot.compiledBy ?? null,
    },
    change_summary: payload.changeSummary ?? null,
    release_notes: payload.releaseNotes ?? null,
  };

  const response = await requestClient.post<unknown>(
    `${PLUGIN_API_BASE}/templates`,
    body,
  );
  return normalizeTemplateDetail(toRecord(unwrapApiData(response)));
}

export async function listAdminTemplateVersionsApi(
  templateId: number | string,
  query: Pick<AdminTemplateListQuery, 'page' | 'pageSize' | 'sort'> = {},
): Promise<PaginatedResult<WorkflowTemplateVersion>> {
  const response = await requestClient.get<unknown>(
    `${PLUGIN_API_BASE}/templates/${templateId}/versions`,
    { params: buildBaseQueryParams(query) },
  );
  const normalized = normalizePaginatedResult<Record<string, unknown>>(response);
  return {
    ...normalized,
    items: normalized.items.map((item) => normalizeTemplateVersion(toRecord(item))),
  };
}

export async function publishAdminTemplateApi(
  templateId: number | string,
  payload: PublishTemplatePayload,
): Promise<Record<string, unknown>> {
  const body: Record<string, unknown> = {
    version_id: payload.versionId ?? null,
    release_scope: payload.releaseScope ?? 'selected_tenants',
    channel: payload.channel ?? 'stable',
    environment_code: payload.environmentCode ?? 'prod_env',
    rollout_json: payload.rolloutJson ?? {},
    notes: payload.notes ?? null,
    change_types_json:
      payload.changeTypes && payload.changeTypes.length > 0
        ? payload.changeTypes
        : ['workflow_definition_change'],
    validation_result_json: payload.validationResult ?? {},
    risk_level: payload.riskLevel ?? null,
  };

  const response = await requestClient.post<unknown>(
    `${PLUGIN_API_BASE}/templates/${templateId}/publish`,
    body,
  );
  return unwrapApiData<Record<string, unknown>>(response);
}

export async function listAdminReleasesApi(
  query: AdminReleaseListQuery = {},
): Promise<PaginatedResult<WorkflowReleaseSummary>> {
  const response = await requestClient.get<unknown>(`${PLUGIN_API_BASE}/releases`, {
    params: buildReleaseListParams(query),
  });
  const normalized = normalizePaginatedResult<Record<string, unknown>>(response);
  return {
    ...normalized,
    items: normalized.items.map((item) => normalizeReleaseSummary(toRecord(item))),
  };
}

export async function rollbackAdminReleaseApi(
  releaseId: number | string,
): Promise<Record<string, unknown>> {
  const response = await requestClient.post<unknown>(
    `${PLUGIN_API_BASE}/releases/${releaseId}/rollback`,
    {},
  );
  return unwrapApiData<Record<string, unknown>>(response);
}

export async function listAdminRunsApi(
  query: AdminRunListQuery = {},
): Promise<PaginatedResult<GlobalRunSummary>> {
  const response = await requestClient.get<unknown>(`${PLUGIN_API_BASE}/runs`, {
    params: buildRunListParams(query),
  });
  const normalized = normalizePaginatedResult<Record<string, unknown>>(response);
  return {
    ...normalized,
    items: normalized.items.map((item) => normalizeRunSummary(toRecord(item))),
  };
}

export async function getAdminRunDetailApi(
  runId: number | string,
): Promise<AdminRunDetail> {
  const response = await requestClient.get<unknown>(`${PLUGIN_API_BASE}/runs/${runId}`);
  return normalizeRunDetail(toRecord(unwrapApiData(response)));
}

export async function replayAdminRunApi(
  runId: number | string,
): Promise<Record<string, unknown>> {
  const response = await requestClient.post<unknown>(
    `${PLUGIN_API_BASE}/runs/${runId}/replay`,
    {},
  );
  return unwrapApiData<Record<string, unknown>>(response);
}

export async function recoverAdminRunApi(
  runId: number | string,
): Promise<Record<string, unknown>> {
  const response = await requestClient.post<unknown>(
    `${PLUGIN_API_BASE}/runs/${runId}/recover`,
    {},
  );
  return unwrapApiData<Record<string, unknown>>(response);
}

export async function terminateAdminRunApi(
  runId: number | string,
): Promise<Record<string, unknown>> {
  const response = await requestClient.post<unknown>(
    `${PLUGIN_API_BASE}/runs/${runId}/terminate`,
    {},
  );
  return unwrapApiData<Record<string, unknown>>(response);
}
