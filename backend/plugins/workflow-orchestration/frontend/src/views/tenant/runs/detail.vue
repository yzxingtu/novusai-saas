<script lang="ts" setup>
import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import {
  getTenantRunDetailApi,
  pauseTenantRunApi,
  resumeTenantRunApi,
  retryTenantRunApi,
  terminateTenantRunApi,
} from '../../../api/tenant';
import type { TenantRunDetail } from '../../../types/tenant';
import {
  TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  buildPrompt,
  openWorkflowAIPanel,
  useWorkflowPageAI,
} from '../../../shared/ai';
import {
  TENANT_RUN_ACTION_ACCESS_CODES,
  TENANT_RUN_DETAIL_PAGE_ACCESS_CODES,
  WORKFLOW_ACCESS_CODES,
} from '../../../shared/access';
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantRunDetail',
});

const TENANT_RUN_DETAIL_PAGE_KEY = 'tenant.workflow_orchestration.runs.detail';

const route = useRoute();
const {
  canRunAction,
  formatDateTime,
  formatRelativeTime,
  hasAccess,
  hasAnyAccess,
  labelForArtifactStatus,
  labelForArtifactType,
  labelForRisk,
  labelForRunStatus,
  navigateTo,
  openExternal,
  t,
  toneForArtifactStatus,
  toneForRisk,
  toneForRunStatus,
} = useTenantOrchestration();
const permissionDeniedMessage = t(
  'plugin.workflow-orchestration.tenant.common.messages.permissionDenied',
);
const canAccessRunDetailPage = hasAnyAccess(TENANT_RUN_DETAIL_PAGE_ACCESS_CODES);
const canOpenWorkflowCenter = hasAccess(
  WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_LIST,
);
const canOpenWorkflowDetail = hasAccess(
  WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_VIEW,
);
const canOpenArtifacts = hasAccess(
  WORKFLOW_ACCESS_CODES.ARTIFACT_CENTER_LIST,
);
const canOpenArtifactDetail = hasAccess(
  WORKFLOW_ACCESS_CODES.ARTIFACT_CENTER_VIEW,
);

function hasRunActionAccess(
  action: keyof typeof TENANT_RUN_ACTION_ACCESS_CODES,
): boolean {
  return hasAccess(TENANT_RUN_ACTION_ACCESS_CODES[action]);
}

const loading = ref(true);
const actionBusy = ref(false);
const errorMessage = ref('');
const run = ref<TenantRunDetail | null>(null);

const runId = computed(() => {
  const raw = Array.isArray(route.params.runId)
    ? route.params.runId[0]
    : route.params.runId;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
});

const prettyInput = computed(() => {
  return run.value?.inputPayload != null
    ? JSON.stringify(run.value.inputPayload, null, 2)
    : '';
});

const prettyOutput = computed(() => {
  return run.value?.outputPayload != null
    ? JSON.stringify(run.value.outputPayload, null, 2)
    : '';
});

function buildRunPlannerSeed(): string | undefined {
  const parts = [
    run.value?.name?.trim(),
    run.value?.workflowName?.trim(),
    run.value?.status?.trim(),
    run.value?.currentNodeName?.trim(),
    run.value?.contractSummary?.trim(),
  ].filter((part): part is string => Boolean(part && part.trim()));

  return parts.length > 0 ? parts.join('\n') : undefined;
}

function openAIPlanner(seed?: string): void {
  openWorkflowAIPanel({
    conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
    message: buildPrompt([
      t('plugin.workflow-orchestration.tenant.run.ai.systemLead'),
      seed?.trim()
        ? t('plugin.workflow-orchestration.tenant.run.ai.userIdea', {
            idea: seed.trim(),
          })
        : t('plugin.workflow-orchestration.tenant.run.ai.emptyIdea'),
      t('plugin.workflow-orchestration.tenant.run.ai.outputContract'),
    ]),
    pageKey: TENANT_RUN_DETAIL_PAGE_KEY,
  });
}

async function loadRun(): Promise<void> {
  if (!canAccessRunDetailPage) {
    run.value = null;
    errorMessage.value = permissionDeniedMessage;
    loading.value = false;
    return;
  }

  if (!runId.value) {
    errorMessage.value = t('plugin.workflow-orchestration.tenant.common.messages.invalidRoute');
    loading.value = false;
    return;
  }

  loading.value = true;
  errorMessage.value = '';

  try {
    run.value = await getTenantRunDetailApi(runId.value);
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.loadFailed');
  } finally {
    loading.value = false;
  }
}

async function handleAction(
  action: 'pause' | 'resume' | 'retry' | 'terminate',
): Promise<void> {
  if (!hasRunActionAccess(action)) {
    errorMessage.value = permissionDeniedMessage;
    return;
  }

  if (!run.value?.id) {
    return;
  }

  if (
    action === 'terminate' &&
    !window.confirm(
      t('plugin.workflow-orchestration.tenant.run.confirm.terminate'),
    )
  ) {
    return;
  }

  actionBusy.value = true;
  try {
    if (action === 'pause') {
      run.value = await pauseTenantRunApi(run.value.id);
    }
    if (action === 'resume') {
      run.value = await resumeTenantRunApi(run.value.id);
    }
    if (action === 'retry') {
      run.value = await retryTenantRunApi(run.value.id);
    }
    if (action === 'terminate') {
      run.value = await terminateTenantRunApi(run.value.id);
    }
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
  } finally {
    actionBusy.value = false;
  }
}

useWorkflowPageAI({
  conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  pageKey: TENANT_RUN_DETAIL_PAGE_KEY,
  buildContext: () => ({
    entityDescription: t('plugin.workflow-orchestration.tenant.run.detailDescription'),
    entityTitle: run.value?.name || t('plugin.workflow-orchestration.tenant.run.untitled'),
    entityType: 'workflow_orchestration_tenant_run_detail',
    pageData: {
      artifact_count: run.value?.artifacts?.length ?? 0,
      current_node_name: run.value?.currentNodeName ?? null,
      run_id: runId.value,
      status: run.value?.status ?? null,
      workflow_id: run.value?.workflowId ?? null,
      workflow_name: run.value?.workflowName ?? null,
    },
    pageTitle: run.value?.name || t('plugin.workflow-orchestration.tenant.run.untitled'),
  }),
  operations: [
    {
      name: 'open_workflow_from_run_detail',
      label: t('plugin.workflow-orchestration.tenant.run.ai.operations.openWorkflows.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.run.ai.operations.openWorkflows.description',
      ),
      readonly: true,
      handler: async () => {
        if (run.value?.workflowId && canOpenWorkflowDetail) {
          navigateTo(`workflows/${run.value.workflowId}`);
        } else if (canOpenWorkflowCenter) {
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
            'plugin.workflow-orchestration.tenant.run.ai.operations.openWorkflows.success',
          ),
        };
      },
    },
    {
      name: 'open_artifacts_from_run_detail',
      label: t('plugin.workflow-orchestration.tenant.run.ai.operations.openArtifacts.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.run.ai.operations.openArtifacts.description',
      ),
      readonly: true,
      handler: async () => {
        if (run.value?.artifacts?.[0]?.id && canOpenArtifactDetail) {
          navigateTo(`artifacts/${run.value.artifacts[0].id}`);
        } else if (canOpenArtifacts) {
          navigateTo('artifacts');
        } else {
          return {
            success: false,
            message: permissionDeniedMessage,
          };
        }
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.run.ai.operations.openArtifacts.success',
          ),
        };
      },
    },
    {
      name: 'open_run_ai_assistant_from_detail',
      label: t('plugin.workflow-orchestration.tenant.run.ai.operations.openAI.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.run.ai.operations.openAI.description',
      ),
      readonly: true,
      params: {
        idea: {
          description: t(
            'plugin.workflow-orchestration.tenant.run.ai.operations.openAI.ideaDescription',
          ),
          required: false,
          type: 'string',
        },
      },
      handler: async (params: Record<string, unknown>) => {
        openAIPlanner(
          typeof params.idea === 'string' ? params.idea : buildRunPlannerSeed(),
        );
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.run.ai.operations.openAI.success',
          ),
        };
      },
    },
    {
      name: 'refresh_run_detail',
      label: t('plugin.workflow-orchestration.tenant.run.ai.operations.refresh.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.run.ai.operations.refresh.description',
      ),
      readonly: true,
      handler: async () => {
        await loadRun();
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.run.ai.operations.refresh.success',
          ),
        };
      },
    },
  ],
});

watch(
  () => route.params.runId,
  () => {
    void loadRun();
  },
  {
    immediate: true,
  },
);
</script>

<template>
  <ConsoleShell
    :description="t('plugin.workflow-orchestration.tenant.run.detailDescription')"
    :eyebrow="t('plugin.workflow-orchestration.tenant.run.eyebrow')"
    :title="run?.name || t('plugin.workflow-orchestration.tenant.run.untitled')"
  >
    <template #actions>
      <button
        v-if="canAccessRunDetailPage"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        @click="openAIPlanner(buildRunPlannerSeed())"
      >
        {{ t('plugin.workflow-orchestration.tenant.run.actions.askAI') }}
      </button>
      <button
        v-if="canAccessRunDetailPage && hasRunActionAccess('pause')"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="actionBusy || !canRunAction(run, 'pause')"
        @click="handleAction('pause')"
      >
        {{ t('plugin.workflow-orchestration.tenant.run.actions.pause') }}
      </button>
      <button
        v-if="canAccessRunDetailPage && hasRunActionAccess('resume')"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="actionBusy || !canRunAction(run, 'resume')"
        @click="handleAction('resume')"
      >
        {{ t('plugin.workflow-orchestration.tenant.run.actions.resume') }}
      </button>
      <button
        v-if="canAccessRunDetailPage && hasRunActionAccess('retry')"
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="actionBusy || !canRunAction(run, 'retry')"
        @click="handleAction('retry')"
      >
        {{
          actionBusy
            ? t('plugin.workflow-orchestration.tenant.common.messages.processing')
            : t('plugin.workflow-orchestration.tenant.run.actions.retry')
        }}
      </button>
      <button
        v-if="canAccessRunDetailPage && hasRunActionAccess('terminate')"
        class="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="actionBusy || !canRunAction(run, 'terminate')"
        @click="handleAction('terminate')"
      >
        {{ t('plugin.workflow-orchestration.tenant.run.actions.terminate') }}
      </button>
    </template>

    <EmptyState
      v-if="!canAccessRunDetailPage"
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
        <div class="mt-4 h-48 animate-pulse rounded-3xl bg-slate-100" />
      </div>
      <div class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="h-5 w-32 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 h-48 animate-pulse rounded-3xl bg-slate-100" />
      </div>
    </section>

    <template v-else-if="run">
      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex flex-wrap items-center gap-2">
            <StatusPill
              :label="labelForRunStatus(run.status)"
              :tone="toneForRunStatus(run.status)"
            />
            <StatusPill
              v-if="run.riskLevel"
              :label="labelForRisk(run.riskLevel)"
              :tone="toneForRisk(run.riskLevel)"
            />
          </div>

          <dl class="mt-5 grid gap-3 text-sm text-slate-600 sm:grid-cols-2 xl:grid-cols-3">
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.run.fields.workflowName') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ run.workflowName || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.run.fields.currentNodeName') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ run.currentNodeName || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.run.fields.snapshotVersion') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ run.snapshotVersion || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.run.fields.startedAt') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatDateTime(run.startedAt) }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.run.fields.updatedAt') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatRelativeTime(run.updatedAt) }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.run.fields.costSummary') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ run.costSummary || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
          </dl>

          <div class="mt-5 rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
            <h2 class="text-sm font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.run.sections.contractSummary') }}
            </h2>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {{ run.contractSummary || t('plugin.workflow-orchestration.tenant.run.empty.contractSummary') }}
            </p>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.run.sections.timeline') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflow-orchestration.tenant.run.sections.timelineHint') }}
              </p>
            </div>
          </div>

          <div
            v-if="run.nodeRuns && run.nodeRuns.length > 0"
            class="mt-5 space-y-3"
          >
            <div
              v-for="nodeRun in run.nodeRuns"
              :key="nodeRun.id"
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="space-y-1">
                  <p class="text-sm font-semibold text-slate-900">
                    {{ nodeRun.nodeName || t('plugin.workflow-orchestration.tenant.workflow.empty.nodeName') }}
                  </p>
                  <p class="text-sm text-slate-600">
                    {{ nodeRun.nodeType || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
                  </p>
                </div>
                <StatusPill
                  :label="labelForRunStatus(nodeRun.status)"
                  :tone="toneForRunStatus(nodeRun.status)"
                />
              </div>
              <div class="mt-3 grid gap-3 text-xs text-slate-500 sm:grid-cols-3">
                <span>{{ formatDateTime(nodeRun.startedAt) }}</span>
                <span>{{ formatDateTime(nodeRun.endedAt) }}</span>
                <span>
                  {{
                    nodeRun.durationMs != null
                      ? `${nodeRun.durationMs} ms`
                      : t('plugin.workflow-orchestration.tenant.common.placeholders.empty')
                  }}
                </span>
              </div>
              <p
                v-if="nodeRun.errorMessage"
                class="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700"
              >
                {{ nodeRun.errorMessage }}
              </p>
            </div>
          </div>
          <EmptyState
            v-else
            :description="t('plugin.workflow-orchestration.tenant.run.empty.timelineDescription')"
            :title="t('plugin.workflow-orchestration.tenant.run.empty.timelineTitle')"
          />
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.run.sections.inputOutput') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.run.sections.inputOutputHint') }}
            </p>
          </div>

          <div class="mt-5 grid gap-4 lg:grid-cols-2">
            <div class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
              <h3 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.run.sections.inputPayload') }}
              </h3>
              <pre
                v-if="prettyInput"
                class="mt-4 max-h-80 overflow-auto rounded-2xl bg-slate-900 p-4 text-xs leading-6 text-slate-100"
              >{{ prettyInput }}</pre>
              <EmptyState
                v-else
                :description="t('plugin.workflow-orchestration.tenant.run.empty.inputDescription')"
                :title="t('plugin.workflow-orchestration.tenant.run.empty.inputTitle')"
              />
            </div>

            <div class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
              <h3 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.run.sections.outputPayload') }}
              </h3>
              <pre
                v-if="prettyOutput"
                class="mt-4 max-h-80 overflow-auto rounded-2xl bg-slate-900 p-4 text-xs leading-6 text-slate-100"
              >{{ prettyOutput }}</pre>
              <EmptyState
                v-else
                :description="t('plugin.workflow-orchestration.tenant.run.empty.outputDescription')"
                :title="t('plugin.workflow-orchestration.tenant.run.empty.outputTitle')"
              />
            </div>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.run.sections.artifacts') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflow-orchestration.tenant.run.sections.artifactsHint') }}
              </p>
            </div>
            <button
              v-if="canOpenArtifacts"
              class="text-sm font-medium text-sky-700 transition hover:text-sky-800"
              @click="navigateTo('artifacts')"
            >
              {{ t('plugin.workflow-orchestration.tenant.common.actions.openArtifacts') }}
            </button>
          </div>

          <div
            v-if="run.artifacts && run.artifacts.length > 0"
            class="mt-5 space-y-3"
          >
            <button
              v-for="artifact in run.artifacts"
              :key="artifact.id"
              class="flex w-full items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left transition hover:border-sky-200 hover:bg-sky-50/60 disabled:cursor-not-allowed disabled:opacity-70"
              :disabled="!canOpenArtifactDetail"
              @click="navigateTo(`artifacts/${artifact.id}`)"
            >
              <div class="min-w-0 space-y-2">
                <p class="truncate text-sm font-semibold text-slate-900">
                  {{ artifact.title || t('plugin.workflow-orchestration.tenant.artifact.untitled') }}
                </p>
                <div class="flex flex-wrap items-center gap-2">
                  <StatusPill
                    :label="labelForArtifactType(artifact.type)"
                    tone="info"
                  />
                  <StatusPill
                    :label="labelForArtifactStatus(artifact.status)"
                    :tone="toneForArtifactStatus(artifact.status)"
                  />
                </div>
              </div>
              <span class="text-xs text-slate-500">
                {{ formatRelativeTime(artifact.updatedAt) }}
              </span>
            </button>
          </div>
          <EmptyState
            v-else
            :description="t('plugin.workflow-orchestration.tenant.run.empty.artifactDescription')"
            :title="t('plugin.workflow-orchestration.tenant.run.empty.artifactTitle')"
          />
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.run.sections.approvals') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflow-orchestration.tenant.run.sections.approvalsHint') }}
              </p>
            </div>
            <button
              v-if="run.hostApprovalPath"
              class="text-sm font-medium text-sky-700 transition hover:text-sky-800"
              @click="openExternal(run.hostApprovalPath)"
            >
              {{ t('plugin.workflow-orchestration.tenant.run.actions.openHostApproval') }}
            </button>
          </div>

          <div
            v-if="run.approvals && run.approvals.length > 0"
            class="mt-5 space-y-3"
          >
            <button
              v-for="approval in run.approvals"
              :key="approval.id"
              class="flex w-full items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left transition hover:border-sky-200 hover:bg-sky-50/60"
              @click="openExternal(approval.detailPath || run.hostApprovalPath || 'runs')"
            >
              <div class="space-y-1">
                <p class="text-sm font-semibold text-slate-900">
                  {{ approval.title }}
                </p>
                <p class="text-sm text-slate-600">
                  {{ approval.approverName || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
                </p>
              </div>
              <div class="text-right text-xs text-slate-500">
                <p>{{ approval.status || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}</p>
                <p>{{ formatDateTime(approval.dueAt) }}</p>
              </div>
            </button>
          </div>
          <EmptyState
            v-else
            :description="t('plugin.workflow-orchestration.tenant.run.empty.approvalDescription')"
            :title="t('plugin.workflow-orchestration.tenant.run.empty.approvalTitle')"
          />
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.run.sections.recovery') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.run.sections.recoveryHint') }}
            </p>
          </div>

          <div
            v-if="run.recoveryEvents && run.recoveryEvents.length > 0"
            class="mt-5 space-y-3"
          >
            <div
              v-for="event in run.recoveryEvents"
              :key="event.id"
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4"
            >
              <div class="flex flex-wrap items-center justify-between gap-3">
                <p class="text-sm font-semibold text-slate-900">
                  {{ event.title || event.eventType }}
                </p>
                <span class="text-xs text-slate-500">
                  {{ formatDateTime(event.createdAt) }}
                </span>
              </div>
              <p
                v-if="event.summary"
                class="mt-2 text-sm leading-6 text-slate-600"
              >
                {{ event.summary }}
              </p>
            </div>
          </div>
          <EmptyState
            v-else
            :description="t('plugin.workflow-orchestration.tenant.run.empty.recoveryDescription')"
            :title="t('plugin.workflow-orchestration.tenant.run.empty.recoveryTitle')"
          />
        </article>
      </section>
    </template>

    <EmptyState
      v-else
      :description="t('plugin.workflow-orchestration.tenant.run.empty.detailDescription')"
      :title="t('plugin.workflow-orchestration.tenant.run.empty.detailTitle')"
    />
    </template>
  </ConsoleShell>
</template>
