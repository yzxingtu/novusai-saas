export interface TenantRequestConfig {
  [key: string]: unknown;
}

export interface TenantDownloadOptions {
  filename: string;
  mimeType?: string;
}

export interface TenantRequestClientLike {
  get: <T = unknown>(
    url: string,
    config?: TenantRequestConfig,
  ) => Promise<T>;
  post: <T = unknown>(
    url: string,
    data?: unknown,
    config?: TenantRequestConfig,
  ) => Promise<T>;
  put: <T = unknown>(
    url: string,
    data?: unknown,
    config?: TenantRequestConfig,
  ) => Promise<T>;
  delete: <T = unknown>(
    url: string,
    config?: TenantRequestConfig,
  ) => Promise<T>;
  download?: (
    url: string,
    config?: TenantRequestConfig,
  ) => Promise<Blob>;
}

export interface TenantRouterLike {
  push: (to: string) => Promise<unknown> | void;
}

export interface TenantCurrentUser {
  id: null | number;
  name: string;
  username: string;
}

export interface TenantPluginSharedApi {
  requestClient: TenantRequestClientLike;
  downloadBlob?: (blob: Blob, options: TenantDownloadOptions) => void;
  $t?: (key: string, params?: Record<string, unknown>) => string;
  router?: TenantRouterLike;
  getCurrentUser?: () => TenantCurrentUser;
}

export interface TenantListQuery {
  keyword?: string;
  page?: number;
  size?: number;
  builderModes?: string[];
  statuses?: string[];
  types?: string[];
  workflowId?: null | number;
}

export interface PaginatedResult<T> {
  items: T[];
  page: number;
  size: number;
  total: number;
}

export interface TenantBuilderCapability {
  code: string;
  enabled: boolean;
  editable?: boolean;
  label?: string;
  description?: string;
  reason?: null | string;
  limit?: null | number;
}

export interface TenantHomeSummary {
  pendingApprovals?: number;
  failedRuns?: number;
  pendingArtifacts?: number;
  activeWorkflows?: number;
  runningNow?: number;
  quotaWarnings?: number;
}

export interface TenantHomeStatCard {
  code: string;
  label: string;
  value: null | number | string;
  hint?: string;
  tone?: string;
}

export interface TenantHomeTodoItem {
  id: number | string;
  category: string;
  title: string;
  summary?: string;
  severity?: string;
  actionLabel?: string;
  targetPath?: string;
  dueAt?: string;
}

export interface TenantHomeAlertItem {
  id: number | string;
  level: string;
  title: string;
  summary?: string;
  targetPath?: string;
}

export interface TenantHomePayload {
  summary?: TenantHomeSummary;
  stats?: TenantHomeStatCard[];
  todos?: TenantHomeTodoItem[];
  alerts?: TenantHomeAlertItem[];
  builderCapabilities?: TenantBuilderCapability[];
  highlightedWorkflows?: TenantWorkflowSummary[];
  latestRuns?: TenantRunSummary[];
  latestArtifacts?: TenantArtifactSummary[];
}

export type TenantWorkflowStatus =
  | 'archived'
  | 'disabled'
  | 'draft'
  | 'error'
  | 'paused'
  | 'published'
  | string;

export type TenantWorkflowBuilderMode =
  | 'tenant_simple_builder'
  | 'tenant_template_editor'
  | 'copied_from_template'
  | string;

export interface TenantWorkflowInputVariable {
  name: string;
  label?: string;
  type?: string;
  required?: boolean;
  defaultValue?: unknown;
  description?: string;
}

export interface TenantWorkflowOutputContract {
  key: string;
  label?: string;
  type?: string;
  description?: string;
}

export interface TenantWorkflowNode {
  id: string;
  name: string;
  type: string;
  stage?: string;
  status?: string;
  readonly?: boolean;
}

export interface TenantWorkflowEdge {
  source: string;
  target: string;
  label?: string;
}

export interface TenantWorkflowVersionSummary {
  id?: number;
  version: string;
  changeLog?: string;
  createdAt?: string;
  createdBy?: string;
  isCurrent?: boolean;
  status?: string;
}

export interface TenantWorkflowSummary {
  id: number;
  name: string;
  code?: string;
  description?: string;
  status?: TenantWorkflowStatus;
  builderMode?: TenantWorkflowBuilderMode;
  sourceTemplateName?: string;
  currentVersion?: string;
  latestRunStatus?: string;
  lastRunAt?: string;
  updatedAt?: string;
  riskLevel?: string;
  pendingApprovals?: number;
  runCount7d?: number;
  successRate7d?: number;
  ownerName?: string;
  canEdit?: boolean;
  canPublish?: boolean;
  canExecute?: boolean;
}

export interface TenantWorkflowDetail extends TenantWorkflowSummary {
  entrypoint?: string;
  publishedVersion?: string;
  latestVersion?: string;
  activationSummary?: string;
  contextHealthSummary?: string;
  policySummary?: string;
  approvalSummary?: string;
  notes?: string;
  inputVariables?: TenantWorkflowInputVariable[];
  outputContracts?: TenantWorkflowOutputContract[];
  nodes?: TenantWorkflowNode[];
  edges?: TenantWorkflowEdge[];
  versions?: TenantWorkflowVersionSummary[];
  relatedRuns?: TenantRunSummary[];
  relatedArtifacts?: TenantArtifactSummary[];
  builderCapabilities?: TenantBuilderCapability[];
}

export type TenantRunStatus =
  | 'cancelled'
  | 'completed'
  | 'failed'
  | 'compensating'
  | 'partially_completed'
  | 'pending'
  | 'paused'
  | 'planning'
  | 'queued'
  | 'recovering'
  | 'running'
  | 'succeeded'
  | 'terminated'
  | 'validating'
  | 'waiting_human'
  | 'waiting_approval'
  | 'waiting_input'
  | string;

export type TenantRunStatusBucket =
  | 'cancelled'
  | 'failed'
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'waiting_human'
  | string;

export type TenantRunAction =
  | 'pause'
  | 'recover'
  | 'replay'
  | 'resume'
  | 'retry'
  | 'terminate'
  | string;

export interface TenantRunSummary {
  id: number;
  name: string;
  workflowId?: number;
  workflowName?: string;
  solutionName?: string;
  status?: TenantRunStatus;
  riskLevel?: string;
  triggerSource?: string;
  currentNodeName?: string;
  waitingApproval?: boolean;
  waitingHumanInput?: boolean;
  costSummary?: string;
  costAmount?: number;
  startedAt?: string;
  endedAt?: string;
  updatedAt?: string;
  artifactCount?: number;
  statusBucket?: TenantRunStatusBucket;
  availableActions?: TenantRunAction[];
  canPause?: boolean;
  canResume?: boolean;
  canRetry?: boolean;
  canTerminate?: boolean;
}

export interface TenantNodeRun {
  id: number;
  nodeId?: string;
  nodeName: string;
  nodeType?: string;
  status?: TenantRunStatus;
  startedAt?: string;
  endedAt?: string;
  durationMs?: number;
  inputSummary?: string;
  outputSummary?: string;
  errorMessage?: string;
  checkpointId?: number;
}

export interface TenantRunEvent {
  id: number | string;
  eventType: string;
  title?: string;
  summary?: string;
  actorName?: string;
  createdAt?: string;
  checkpointId?: number;
}

export interface TenantApprovalRecord {
  id: number | string;
  title: string;
  status?: string;
  approverName?: string;
  dueAt?: string;
  detailPath?: string;
}

export interface TenantRunDetail extends TenantRunSummary {
  runKey?: string;
  snapshotVersion?: string;
  contractSummary?: string;
  inputPayload?: unknown;
  outputPayload?: unknown;
  nodeRuns?: TenantNodeRun[];
  artifacts?: TenantArtifactSummary[];
  approvals?: TenantApprovalRecord[];
  recoveryEvents?: TenantRunEvent[];
  evaluationSummary?: string;
  hostApprovalPath?: string;
}

export type TenantArtifactType =
  | 'approval_packet'
  | 'draft'
  | 'evidence_bundle'
  | 'recommendation'
  | 'report'
  | string;

export type TenantArtifactStatus =
  | 'draft'
  | 'adopted'
  | 'archived'
  | 'expired'
  | 'failed'
  | 'pending_review'
  | 'rejected'
  | 'ready'
  | 'returned'
  | string;

export type TenantArtifactAction =
  | 'download'
  | 'feedback'
  | string;

export interface TenantArtifactSummary {
  id: number;
  title: string;
  type?: TenantArtifactType;
  status?: TenantArtifactStatus;
  workflowId?: number;
  workflowName?: string;
  runId?: number;
  runName?: string;
  sourceVersion?: string;
  sourceNodeName?: string;
  mimeType?: string;
  sizeBytes?: number;
  previewText?: string;
  feedbackCount?: number;
  createdAt?: string;
  updatedAt?: string;
  downloadFilename?: string;
  availableActions?: TenantArtifactAction[];
  canFeedback?: boolean;
  canDownload?: boolean;
  downloadAvailable?: boolean;
}

export interface TenantArtifactFeedback {
  id: number | string;
  kind?: string;
  rating?: number;
  comment?: string;
  createdAt?: string;
  createdBy?: string;
}

export interface TenantArtifactDetail extends TenantArtifactSummary {
  contentText?: string;
  contentMarkdown?: string;
  contentJson?: null | Record<string, unknown>;
  adoptionSummary?: string;
  approvalStatus?: string;
  feedback?: TenantArtifactFeedback[];
  downloadUrl?: string;
}

export interface TenantWorkflowUpsertPayload {
  name: string;
  description?: string;
}

export interface TenantArtifactFeedbackPayload {
  comment: string;
  kind?: string;
  rating?: number;
}
