<script lang="ts" setup>
import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import {
  downloadTenantArtifactApi,
  getTenantArtifactDetailApi,
  submitTenantArtifactFeedbackApi,
} from '../../../api/tenant';
import type { TenantArtifactDetail } from '../../../types/tenant';
import {
  TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  buildPrompt,
  openWorkflowAIPanel,
  useWorkflowPageAI,
} from '../../../shared/ai';
import {
  TENANT_ARTIFACT_DETAIL_PAGE_ACCESS_CODES,
  WORKFLOW_ACCESS_CODES,
} from '../../../shared/access';
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantArtifactDetail',
});

const TENANT_ARTIFACT_DETAIL_PAGE_KEY =
  'tenant.workflow_orchestration.artifacts.detail';

const route = useRoute();
const {
  formatBytes,
  formatDateTime,
  formatRelativeTime,
  hasAccess,
  hasAnyAccess,
  labelForArtifactStatus,
  labelForArtifactType,
  navigateTo,
  saveBlob,
  shared,
  t,
  toneForArtifactStatus,
} = useTenantOrchestration();
const permissionDeniedMessage = t(
  'plugin.workflow-orchestration.tenant.common.messages.permissionDenied',
);
const canAccessArtifactDetailPage = hasAnyAccess(
  TENANT_ARTIFACT_DETAIL_PAGE_ACCESS_CODES,
);
const canViewWorkflowDetail = hasAccess(
  WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_VIEW,
);
const canViewRunDetail = hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_VIEW);
const canDownloadArtifact = hasAccess(
  WORKFLOW_ACCESS_CODES.ARTIFACT_CENTER_EXPORT,
);
const canSubmitArtifactFeedback = hasAccess(
  WORKFLOW_ACCESS_CODES.ARTIFACT_CENTER_FEEDBACK,
);

const artifact = ref<TenantArtifactDetail | null>(null);
const loading = ref(true);
const downloading = ref(false);
const submittingFeedback = ref(false);
const errorMessage = ref('');
const feedbackComment = ref('');
const feedbackRating = ref<null | number>(null);

const ratingOptions = [5, 4, 3, 2, 1];

const artifactId = computed(() => {
  const raw = Array.isArray(route.params.artifactId)
    ? route.params.artifactId[0]
    : route.params.artifactId;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
});

const previewText = computed(() => {
  return (
    artifact.value?.contentMarkdown ||
    artifact.value?.contentText ||
    artifact.value?.previewText ||
    ''
  );
});

const prettyJson = computed(() => {
  return artifact.value?.contentJson
    ? JSON.stringify(artifact.value.contentJson, null, 2)
    : '';
});

function buildArtifactPlannerSeed(): string | undefined {
  const parts = [
    artifact.value?.title?.trim(),
    artifact.value?.workflowName?.trim(),
    artifact.value?.type?.trim(),
    artifact.value?.status?.trim(),
    artifact.value?.previewText?.trim(),
  ].filter((part): part is string => Boolean(part && part.trim()));

  return parts.length > 0 ? parts.join('\n') : undefined;
}

function openAIPlanner(seed?: string): void {
  openWorkflowAIPanel({
    conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
    message: buildPrompt([
      t('plugin.workflow-orchestration.tenant.artifact.ai.systemLead'),
      seed?.trim()
        ? t('plugin.workflow-orchestration.tenant.artifact.ai.userIdea', {
            idea: seed.trim(),
          })
        : t('plugin.workflow-orchestration.tenant.artifact.ai.emptyIdea'),
      t('plugin.workflow-orchestration.tenant.artifact.ai.outputContract'),
    ]),
    pageKey: TENANT_ARTIFACT_DETAIL_PAGE_KEY,
  });
}

const downloadState = computed(() => {
  if (!canDownloadArtifact) {
    return {
      enabled: false,
      reason: permissionDeniedMessage,
    };
  }

  if (!artifact.value) {
    return {
      enabled: false,
      reason: t('plugin.workflow-orchestration.tenant.common.messages.downloadUnavailable'),
    };
  }

  const backendAllowsDownload = Array.isArray(artifact.value.availableActions)
    ? artifact.value.availableActions.includes('download')
    : artifact.value.canDownload !== false;
  const downloadAvailable = backendAllowsDownload && artifact.value.downloadAvailable !== false;

  if (!downloadAvailable) {
    return {
      enabled: false,
      reason: t('plugin.workflow-orchestration.tenant.common.messages.downloadUnavailable'),
    };
  }

  if (shared.value?.requestClient?.download) {
    return {
      enabled: true,
      reason: '',
    };
  }

  if (artifact.value.downloadUrl) {
    return {
      enabled: true,
      reason: '',
    };
  }

  return {
    enabled: false,
    reason: t('plugin.workflow-orchestration.tenant.artifact.empty.downloadDisabled'),
  };
});

async function loadArtifact(): Promise<void> {
  if (!canAccessArtifactDetailPage) {
    artifact.value = null;
    errorMessage.value = permissionDeniedMessage;
    loading.value = false;
    return;
  }

  if (!artifactId.value) {
    errorMessage.value = t('plugin.workflow-orchestration.tenant.common.messages.invalidRoute');
    loading.value = false;
    return;
  }

  loading.value = true;
  errorMessage.value = '';

  try {
    artifact.value = await getTenantArtifactDetailApi(artifactId.value);
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.loadFailed');
  } finally {
    loading.value = false;
  }
}

async function downloadArtifact(): Promise<void> {
  if (!artifact.value?.id) {
    return;
  }

  downloading.value = true;
  errorMessage.value = '';

  try {
    if (!downloadState.value.enabled) {
      throw new Error(downloadState.value.reason);
    }
    const blob = await downloadTenantArtifactApi(artifact.value.id, {
      signedDownloadUrl: artifact.value.downloadUrl,
    });
    saveBlob(blob, {
      filename:
        artifact.value.downloadFilename || `artifact-${artifact.value.id}.bin`,
      mimeType: artifact.value.mimeType,
    });
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
  } finally {
    downloading.value = false;
  }
}

async function submitFeedback(): Promise<void> {
  if (!canSubmitArtifactFeedback) {
    errorMessage.value = permissionDeniedMessage;
    return;
  }

  if (!artifact.value?.id || artifact.value.canFeedback === false) {
    return;
  }
  if (!feedbackComment.value.trim()) {
    errorMessage.value = t('plugin.workflow-orchestration.tenant.artifact.validation.commentRequired');
    return;
  }

  submittingFeedback.value = true;
  errorMessage.value = '';

  try {
    artifact.value = await submitTenantArtifactFeedbackApi(artifact.value.id, {
      comment: feedbackComment.value.trim(),
      rating: feedbackRating.value ?? undefined,
    });
    feedbackComment.value = '';
    feedbackRating.value = null;
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
  } finally {
    submittingFeedback.value = false;
  }
}

useWorkflowPageAI({
  conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  pageKey: TENANT_ARTIFACT_DETAIL_PAGE_KEY,
  buildContext: () => ({
    entityDescription: t(
      'plugin.workflow-orchestration.tenant.artifact.detailDescription',
    ),
    entityTitle:
      artifact.value?.title
      || t('plugin.workflow-orchestration.tenant.artifact.untitled'),
    entityType: 'workflow_orchestration_tenant_artifact_detail',
    pageData: {
      approval_status: artifact.value?.approvalStatus ?? null,
      artifact_id: artifactId.value,
      can_download: downloadState.value.enabled,
      can_feedback: artifact.value?.canFeedback ?? null,
      run_id: artifact.value?.runId ?? null,
      status: artifact.value?.status ?? null,
      type: artifact.value?.type ?? null,
      workflow_id: artifact.value?.workflowId ?? null,
      workflow_name: artifact.value?.workflowName ?? null,
    },
    pageTitle:
      artifact.value?.title
      || t('plugin.workflow-orchestration.tenant.artifact.untitled'),
  }),
  operations: [
    {
      name: 'open_workflow_from_artifact_detail',
      label: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.openWorkflows.label',
      ),
      description: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.openWorkflows.description',
      ),
      readonly: true,
      handler: async () => {
        if (artifact.value?.workflowId && canViewWorkflowDetail) {
          navigateTo(`workflows/${artifact.value.workflowId}`);
        } else if (hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_LIST)) {
          navigateTo('workflows');
        } else {
          return {
            success: false,
            message: permissionDeniedMessage,
          };
        }
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.artifact.ai.operations.openWorkflows.success',
          ),
        };
      },
    },
    {
      name: 'open_run_from_artifact_detail',
      label: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.openRuns.label',
      ),
      description: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.openRuns.description',
      ),
      readonly: true,
      handler: async () => {
        if (artifact.value?.runId && canViewRunDetail) {
          navigateTo(`runs/${artifact.value.runId}`);
        } else if (hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_LIST)) {
          navigateTo('runs');
        } else {
          return {
            success: false,
            message: permissionDeniedMessage,
          };
        }
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.artifact.ai.operations.openRuns.success',
          ),
        };
      },
    },
    {
      name: 'open_artifact_ai_assistant_from_detail',
      label: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.openAI.label',
      ),
      description: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.openAI.description',
      ),
      readonly: true,
      params: {
        idea: {
          description: t(
            'plugin.workflow-orchestration.tenant.artifact.ai.operations.openAI.ideaDescription',
          ),
          required: false,
          type: 'string',
        },
      },
      handler: async (params: Record<string, unknown>) => {
        openAIPlanner(
          typeof params.idea === 'string'
            ? params.idea
            : buildArtifactPlannerSeed(),
        );
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.artifact.ai.operations.openAI.success',
          ),
        };
      },
    },
    {
      name: 'refresh_artifact_detail',
      label: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.refresh.label',
      ),
      description: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.refresh.description',
      ),
      readonly: true,
      handler: async () => {
        await loadArtifact();
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.artifact.ai.operations.refresh.success',
          ),
        };
      },
    },
  ],
});

watch(
  () => route.params.artifactId,
  () => {
    void loadArtifact();
  },
  {
    immediate: true,
  },
);
</script>

<template>
  <ConsoleShell
    :description="artifact?.previewText || t('plugin.workflow-orchestration.tenant.artifact.detailDescription')"
    :eyebrow="t('plugin.workflow-orchestration.tenant.artifact.eyebrow')"
    :title="artifact?.title || t('plugin.workflow-orchestration.tenant.artifact.untitled')"
  >
    <template #actions>
      <button
        v-if="canAccessArtifactDetailPage"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        @click="openAIPlanner(buildArtifactPlannerSeed())"
      >
        {{ t('plugin.workflow-orchestration.tenant.artifact.actions.askAI') }}
      </button>
      <button
        v-if="artifact?.workflowId && canViewWorkflowDetail"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        @click="navigateTo(`workflows/${artifact.workflowId}`)"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.viewWorkflow') }}
      </button>
      <button
        v-if="artifact?.runId && canViewRunDetail"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        @click="navigateTo(`runs/${artifact.runId}`)"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.viewRun') }}
      </button>
      <button
        v-if="canAccessArtifactDetailPage && canDownloadArtifact"
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="downloading || !downloadState.enabled"
        @click="downloadArtifact"
      >
        {{
          downloading
            ? t('plugin.workflow-orchestration.tenant.common.messages.processing')
            : t('plugin.workflow-orchestration.tenant.common.actions.download')
        }}
      </button>
    </template>

    <EmptyState
      v-if="!canAccessArtifactDetailPage"
      :title="permissionDeniedMessage"
    />
    <template v-else>
    <section
      v-if="errorMessage"
      class="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700"
    >
      {{ errorMessage }}
    </section>

    <section v-if="loading" class="grid gap-4 xl:grid-cols-[1fr_1fr]">
      <div class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="h-5 w-44 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 h-56 animate-pulse rounded-3xl bg-slate-100" />
      </div>
      <div class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="h-5 w-32 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 h-56 animate-pulse rounded-3xl bg-slate-100" />
      </div>
    </section>

    <template v-else-if="artifact">
      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex flex-wrap items-center gap-2">
            <StatusPill
              :label="labelForArtifactType(artifact.type)"
              tone="info"
            />
            <StatusPill
              :label="labelForArtifactStatus(artifact.status)"
              :tone="toneForArtifactStatus(artifact.status)"
            />
            <StatusPill
              v-if="artifact.approvalStatus"
              :label="artifact.approvalStatus"
              tone="warning"
            />
          </div>

          <dl class="mt-5 grid gap-3 text-sm text-slate-600 sm:grid-cols-2 xl:grid-cols-3">
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.artifact.fields.workflowName') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.workflowName || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.artifact.fields.runId') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.runId ?? t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.artifact.fields.sourceVersion') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.sourceVersion || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.artifact.fields.sourceNodeName') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.sourceNodeName || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.artifact.fields.sizeBytes') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatBytes(artifact.sizeBytes) }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.artifact.fields.updatedAt') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatRelativeTime(artifact.updatedAt) }}
              </dd>
            </div>
          </dl>

          <p
            v-if="!downloadState.enabled"
            class="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
          >
            {{ downloadState.reason }}
          </p>

          <div class="mt-5 rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
            <h2 class="text-sm font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.adoption') }}
            </h2>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {{ artifact.adoptionSummary || t('plugin.workflow-orchestration.tenant.artifact.empty.adoptionDescription') }}
            </p>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.preview') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.previewHint') }}
            </p>
          </div>

          <pre
            v-if="previewText"
            class="mt-5 max-h-[26rem] overflow-auto whitespace-pre-wrap rounded-3xl bg-slate-900 p-5 text-xs leading-6 text-slate-100"
          >{{ previewText }}</pre>
          <EmptyState
            v-else
            :description="t('plugin.workflow-orchestration.tenant.artifact.empty.previewDescription')"
            :title="t('plugin.workflow-orchestration.tenant.artifact.empty.previewTitle')"
          />
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.structuredData') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.structuredDataHint') }}
            </p>
          </div>

          <pre
            v-if="prettyJson"
            class="mt-5 max-h-[26rem] overflow-auto rounded-3xl bg-slate-900 p-5 text-xs leading-6 text-slate-100"
          >{{ prettyJson }}</pre>
          <EmptyState
            v-else
            :description="t('plugin.workflow-orchestration.tenant.artifact.empty.jsonDescription')"
            :title="t('plugin.workflow-orchestration.tenant.artifact.empty.jsonTitle')"
          />
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.traceability') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.traceabilityHint') }}
            </p>
          </div>

          <dl class="mt-5 grid gap-3 text-sm text-slate-600">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.artifact.fields.createdAt') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatDateTime(artifact.createdAt) }}
              </dd>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.artifact.fields.mimeType') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.mimeType || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.artifact.fields.downloadFilename') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.downloadFilename || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.artifact.fields.feedbackCount') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.feedback?.length ?? artifact.feedbackCount ?? 0 }}
              </dd>
            </div>
          </dl>
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.feedback') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.feedbackHint') }}
            </p>
          </div>

          <div class="mt-5 grid gap-4">
            <label class="space-y-2 text-sm text-slate-600">
              <span>{{ t('plugin.workflow-orchestration.tenant.artifact.fields.rating') }}</span>
              <select
                v-model="feedbackRating"
                class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
                :disabled="submittingFeedback || !canSubmitArtifactFeedback || artifact.canFeedback === false"
              >
                <option :value="null">
                  {{ t('plugin.workflow-orchestration.tenant.artifact.placeholders.rating') }}
                </option>
                <option
                  v-for="rating in ratingOptions"
                  :key="rating"
                  :value="rating"
                >
                  {{ t('plugin.workflow-orchestration.tenant.artifact.ratingOption', { rating }) }}
                </option>
              </select>
            </label>

            <label class="space-y-2 text-sm text-slate-600">
              <span>{{ t('plugin.workflow-orchestration.tenant.artifact.fields.feedbackComment') }}</span>
              <textarea
                v-model="feedbackComment"
                class="min-h-36 w-full rounded-3xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
                :disabled="submittingFeedback || !canSubmitArtifactFeedback || artifact.canFeedback === false"
                :placeholder="t('plugin.workflow-orchestration.tenant.artifact.placeholders.feedbackComment')"
              />
            </label>
          </div>

          <p
            v-if="!canSubmitArtifactFeedback || artifact.canFeedback === false"
            class="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
          >
            {{
              !canSubmitArtifactFeedback
                ? permissionDeniedMessage
                : t('plugin.workflow-orchestration.tenant.artifact.empty.feedbackDisabled')
            }}
          </p>

          <div class="mt-5">
            <button
              v-if="canSubmitArtifactFeedback"
              class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="submittingFeedback || artifact.canFeedback === false"
              @click="submitFeedback"
            >
              {{
                submittingFeedback
                  ? t('plugin.workflow-orchestration.tenant.common.messages.processing')
                  : t('plugin.workflow-orchestration.tenant.common.actions.submitFeedback')
              }}
            </button>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.feedbackHistory') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.artifact.sections.feedbackHistoryHint') }}
            </p>
          </div>

          <div
            v-if="artifact.feedback && artifact.feedback.length > 0"
            class="mt-5 space-y-3"
          >
            <div
              v-for="item in artifact.feedback"
              :key="item.id"
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4"
            >
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div class="space-y-1">
                  <p class="text-sm font-semibold text-slate-900">
                    {{ item.createdBy || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
                  </p>
                  <p class="text-xs text-slate-500">
                    {{ formatDateTime(item.createdAt) }}
                  </p>
                </div>
                <StatusPill
                  :label="
                    item.rating != null
                      ? t('plugin.workflow-orchestration.tenant.artifact.ratingBadge', { rating: item.rating })
                      : t('plugin.workflow-orchestration.tenant.artifact.noRating')
                  "
                  :tone="item.rating != null && item.rating >= 4 ? 'success' : item.rating != null && item.rating <= 2 ? 'warning' : 'neutral'"
                />
              </div>
              <p class="mt-3 text-sm leading-6 text-slate-600">
                {{ item.comment || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </p>
            </div>
          </div>
          <EmptyState
            v-else
            :description="t('plugin.workflow-orchestration.tenant.artifact.empty.feedbackDescription')"
            :title="t('plugin.workflow-orchestration.tenant.artifact.empty.feedbackTitle')"
          />
        </article>
      </section>
    </template>

    <EmptyState
      v-else
      :description="t('plugin.workflow-orchestration.tenant.artifact.empty.detailDescription')"
      :title="t('plugin.workflow-orchestration.tenant.artifact.empty.detailTitle')"
    />
    </template>
  </ConsoleShell>
</template>
