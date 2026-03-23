export interface AdminCollectionQuery {
  keyword?: string;
  page?: number;
  pageSize?: number;
  sort?: string;
}

export interface PublishTemplatePayload {
  versionId?: number;
  releaseScope?: string;
  channel?: string;
  environmentCode?: string;
  rolloutJson?: Record<string, unknown>;
  notes?: null | string;
  changeTypes?: string[];
  validationResult?: Record<string, unknown>;
  riskLevel?: null | string;
}

export interface AdminTemplateListQuery extends AdminCollectionQuery {
  builderSurface?: string;
  category?: string;
  code?: string;
  createdBy?: number;
  releaseScope?: string;
  status?: string;
}

export interface AdminReleaseListQuery extends AdminCollectionQuery {
  channel?: string;
  environmentCode?: string;
  releaseScope?: string;
  status?: string;
  workflowId?: number;
  workflowKind?: string;
}

export interface AdminRunListQuery extends AdminCollectionQuery {
  releaseId?: number;
  status?: string;
  tenantId?: number;
  workflowId?: number;
  workflowTemplateId?: number;
  workflowVersionId?: number;
}

export interface ApiEnvelope<T = unknown> {
  code: number;
  data: T;
  message: string;
}

export interface PaginatedResult<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

export interface WorkflowBuilderCapability {
  available?: boolean;
  category?: null | string;
  code: string;
  description?: null | string;
  label?: null | string;
  reason?: null | string;
}

export interface WorkflowTemplateSegment {
  code?: null | string;
  description?: null | string;
  kind?: null | string;
  label?: null | string;
}

export interface WorkflowGraphNode {
  capability_key?: null | string;
  category?: null | string;
  id: string;
  label?: null | string;
  readonly?: boolean;
  risk_level?: null | string;
  status?: null | string;
  type?: null | string;
}

export interface WorkflowGraphEdge {
  id?: null | string;
  label?: null | string;
  source: string;
  target: string;
}

export interface WorkflowGraphSnapshot {
  edges?: WorkflowGraphEdge[];
  metadata?: null | Record<string, unknown>;
  nodes?: WorkflowGraphNode[];
  root_node_keys?: string[];
}

export interface WorkflowTemplateNode {
  config_json?: Record<string, unknown>;
  description?: null | string;
  id: number;
  input_contract_json?: Record<string, unknown>;
  metadata_json?: Record<string, unknown>;
  node_key: string;
  node_type: string;
  output_contract_json?: Record<string, unknown>;
  policy_json?: Record<string, unknown>;
  position_json?: Record<string, unknown>;
  retry_limit?: null | number;
  sort_order?: number;
  template_id?: null | number;
  timeout_minutes?: null | number;
  title: string;
}

export interface WorkflowTemplateEdge {
  condition_json?: Record<string, unknown>;
  edge_key: string;
  from_node_key: string;
  from_port?: null | string;
  id: number;
  metadata_json?: Record<string, unknown>;
  sort_order?: number;
  template_id?: null | number;
  to_node_key: string;
  to_port?: null | string;
}

export interface WorkflowTemplateVersion {
  change_summary?: null | string;
  compiled_at?: null | string;
  compiled_by?: null | number;
  created_at?: null | string;
  created_by?: null | number;
  edge_count?: null | number;
  id: number;
  is_latest?: boolean;
  is_published?: boolean;
  node_count?: null | number;
  published_at?: null | string;
  published_by?: null | number;
  release_notes?: null | string;
  snapshot_hash?: null | string;
  snapshot_json?: Record<string, unknown>;
  snapshot_version?: null | string;
  status?: null | string;
  template_id?: null | number;
  updated_at?: null | string;
  updated_by?: null | number;
  version_label?: null | string;
  version_no?: null | number;
  workflow_schema_version?: null | string;
}

export interface WorkflowTemplateSummary {
  builder_surface?: null | string;
  category?: null | string;
  code?: null | string;
  contract_summary_json?: Record<string, unknown>;
  created_at?: null | string;
  created_by?: null | number;
  current_published_version_id?: null | number;
  default_trigger_json?: Record<string, unknown>;
  description?: null | string;
  id: number;
  latest_release_id?: null | number;
  latest_version_id?: null | number;
  latest_version_label?: null | string;
  latest_version_no?: null | number;
  metadata_json?: Record<string, unknown>;
  name: string;
  published_at?: null | string;
  published_by?: null | number;
  release_scope?: null | string;
  risk_policy_json?: Record<string, unknown>;
  status?: null | string;
  tags_json?: string[];
  updated_at?: null | string;
  updated_by?: null | number;
}

export interface WorkflowReleaseSummary {
  channel?: null | string;
  code?: null | string;
  created_at?: null | string;
  created_by?: null | number;
  environment_code?: null | string;
  environment_id?: null | number;
  id: number;
  notes?: null | string;
  published_at?: null | string;
  published_by?: null | number;
  release_scope?: null | string;
  reviewed_at?: null | string;
  reviewed_by?: null | number;
  rollback_of_release_id?: null | number;
  rollback_target_release_id?: null | number;
  rollout_json?: Record<string, unknown>;
  status?: null | string;
  updated_at?: null | string;
  updated_by?: null | number;
  workflow_code?: null | string;
  workflow_id?: null | number;
  workflow_kind?: null | string;
  workflow_name?: null | string;
  workflow_version_id?: null | number;
}

export interface WorkflowTemplateDetail extends WorkflowTemplateSummary {
  builder_capabilities?: WorkflowBuilderCapability[];
  editable_segments?: WorkflowTemplateSegment[];
  edges?: WorkflowTemplateEdge[];
  latest_release?: null | WorkflowReleaseSummary;
  latest_version?: null | WorkflowTemplateVersion;
  locked_segments?: WorkflowTemplateSegment[];
  nodes?: WorkflowTemplateNode[];
  parameterized_segments?: WorkflowTemplateSegment[];
  published_version?: null | WorkflowTemplateVersion;
  version_count?: number;
}

export interface TemplateOverviewSummary {
  status_counts?: Record<string, number>;
  total_artifacts?: number;
  total_runs?: number;
  total_templates?: number;
  total_versions?: number;
}

export interface ReleaseOverviewSummary {
  latest_published_at?: null | string;
  status_counts?: Record<string, number>;
  total_releases?: number;
}

export interface RuntimeOverviewSummary {
  artifact_status_counts?: Record<string, number>;
  run_status_counts?: Record<string, number>;
}

export interface SettingsOverviewSummary {
  config_rows?: Record<string, unknown>[];
  environment_count?: number;
  zero_host_boundary?: Record<string, unknown>;
}

export interface AdminOverviewResponse {
  metrics?: Record<string, unknown>;
  release_summary?: ReleaseOverviewSummary;
  settings_summary?: SettingsOverviewSummary;
  template_summary?: TemplateOverviewSummary;
  runtime_summary?: RuntimeOverviewSummary;
}

export interface WorkflowArtifactSummary {
  artifact_type?: null | string;
  available_actions?: string[];
  content_json?: null | Record<string, unknown>;
  content_text?: null | string;
  created_at?: null | string;
  download_filename?: null | string;
  expires_at?: null | string;
  feedback_summary?: null | Record<string, unknown>;
  hash?: null | string;
  id: number;
  mime_type?: null | string;
  name?: null | string;
  preview_text?: null | string;
  size_bytes?: null | number;
  status?: null | string;
  storage_path?: null | string;
  storage_uri?: null | string;
  summary?: null | string;
  title?: null | string;
  visibility?: null | string;
  workflow_run_id?: null | number;
}

export interface WorkflowNodeRunSummary {
  attempt_no?: null | number;
  created_at?: null | string;
  duration_ms?: null | number;
  ended_at?: null | string;
  error_detail?: null | string;
  executor_ref?: null | string;
  executor_type?: null | string;
  id: number;
  input_payload?: unknown;
  node_key?: null | string;
  node_label?: null | string;
  node_type?: null | string;
  output_payload?: unknown;
  started_at?: null | string;
  status?: null | string;
  status_bucket?: null | string;
  workflow_run_id?: null | number;
}

export interface WorkflowRunTimelineEvent {
  created_at?: null | string;
  detail?: unknown;
  event_type?: null | string;
  id: number | string;
  message?: null | string;
  occurred_at?: null | string;
  status_from?: null | string;
  status_to?: null | string;
}

export interface WorkflowExecutionCheckpoint {
  artifact_refs?: Array<number | string>;
  checkpoint_type?: null | string;
  created_at?: null | string;
  id: number | string;
  snapshot_payload?: unknown;
  workflow_node_run_id?: null | number;
  workflow_run_id?: null | number;
}

export interface AdminRunNodeCounts {
  failed?: number;
  running?: number;
  succeeded?: number;
  total?: number;
  waiting_human?: number;
}

export interface GlobalRunSummary {
  artifact_count?: null | number;
  available_actions?: string[];
  budget_snapshot_json?: Record<string, unknown>;
  can_pause?: boolean;
  can_resume?: boolean;
  can_retry?: boolean;
  can_terminate?: boolean;
  code?: null | string;
  cost_amount?: null | number;
  cost_summary?: null | Record<string, unknown>;
  cost_summary_text?: null | string;
  created_at?: null | string;
  current_node_key?: null | string;
  current_node_name?: null | string;
  ended_at?: null | string;
  entrypoint?: null | string;
  environment_id?: null | number;
  error_summary?: null | string;
  final_output?: unknown;
  id: number;
  idempotency_key?: null | string;
  initiated_by?: null | number;
  initiated_from?: null | string;
  input_payload?: unknown;
  last_heartbeat_at?: null | string;
  mode?: null | string;
  name?: null | string;
  node_counts?: null | AdminRunNodeCounts;
  output_payload?: unknown;
  parent_run_id?: null | number;
  release_id?: null | number;
  retry_count?: number;
  risk_level?: null | string;
  risk_snapshot_json?: Record<string, unknown>;
  started_at?: null | string;
  started_by_id?: null | number;
  started_by_type?: null | string;
  status?: null | string;
  status_bucket?: null | string;
  template_name?: null | string;
  tenant_id?: null | number;
  tenant_workflow_id?: null | number;
  trace_id?: null | string;
  trigger_id?: null | number;
  trigger_source?: null | string;
  updated_at?: null | string;
  waiting_approval?: boolean;
  waiting_human_input?: boolean;
  workflow_id?: null | number;
  workflow_name?: null | string;
  workflow_template_id?: null | number;
  workflow_version_id?: null | number;
}

export interface AdminRunDetail {
  artifacts?: WorkflowArtifactSummary[];
  checkpoints?: WorkflowExecutionCheckpoint[];
  events?: WorkflowRunTimelineEvent[];
  execution_graph?: WorkflowGraphSnapshot;
  node_runs?: WorkflowNodeRunSummary[];
  run?: GlobalRunSummary;
}

export type GlobalRunDetail = AdminRunDetail;
