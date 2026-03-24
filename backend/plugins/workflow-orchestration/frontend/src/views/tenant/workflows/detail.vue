<script lang="ts" setup>
import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import {
  executeTenantWorkflowApi,
  getTenantWorkflowDetailApi,
  listTenantWorkflowVersionsApi,
  publishTenantWorkflowApi,
} from '../../../api/tenant';
import {
  TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  buildPrompt,
  openWorkflowAIPanel,
  useWorkflowPageAI,
} from '../../../shared/ai';
import {
  TENANT_WORKFLOW_DETAIL_PAGE_ACCESS_CODES,
  WORKFLOW_ACCESS_CODES,
} from '../../../shared/access';
import type { TenantWorkflowDetail } from '../../../types/tenant';
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantWorkflowDetail',
});

const TENANT_WORKFLOW_DETAIL_PAGE_KEY =
  'tenant.workflow_orchestration.workflows.detail';

const route = useRoute();
const {
  formatDateTime,
  formatNumber,
  formatPercent,
  formatRelativeTime,
  hasAccess,
  hasAnyAccess,
  labelForArtifactStatus,
  labelForArtifactType,
  labelForBuilderMode,
  labelForRisk,
  labelForRunStatus,
  labelForWorkflowStatus,
  navigateTo,
  t,
  toneForArtifactStatus,
  toneForRisk,
  toneForRunStatus,
  toneForWorkflowStatus,
} = useTenantOrchestration();
const permissionDeniedMessage = t(
  'plugin.workflow-orchestration.tenant.common.messages.permissionDenied',
);
const canAccessWorkflowDetailPage = hasAnyAccess(
  TENANT_WORKFLOW_DETAIL_PAGE_ACCESS_CODES,
);
const canOpenEditor = hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_EDIT);
const canPublishWorkflow = hasAccess(
  WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_PUBLISH,
);
const canRunWorkflow = hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_EXECUTE);
const canOpenRuns = hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_LIST);
const canOpenRunDetail = hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_VIEW);
const canOpenArtifacts = hasAccess(
  WORKFLOW_ACCESS_CODES.ARTIFACT_CENTER_LIST,
);
const canOpenArtifactDetail = hasAccess(
  WORKFLOW_ACCESS_CODES.ARTIFACT_CENTER_VIEW,
);

const loading = ref(true);
const actionBusy = ref(false);
const errorMessage = ref('');
const workflow = ref<TenantWorkflowDetail | null>(null);

const workflowId = computed(() => {
  const raw = Array.isArray(route.params.id)
    ? route.params.id[0]
    : route.params.id;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
});

const topologyPreview = computed(() => {
  return workflow.value?.nodes?.slice(0, 6) ?? [];
});

function buildWorkflowPlannerSeed(): string | undefined {
  const parts = [
    workflow.value?.name?.trim(),
    workflow.value?.description?.trim(),
    workflow.value?.currentVersion
      ? `${t('plugin.workflow-orchestration.tenant.workflow.fields.version')}: ${workflow.value.currentVersion}`
      : '',
    workflow.value?.publishedVersion
      ? `${t('plugin.workflow-orchestration.tenant.workflow.fields.publishedVersion')}: ${workflow.value.publishedVersion}`
      : '',
    workflow.value?.status?.trim(),
  ].filter((part): part is string => Boolean(part && part.trim()));

  return parts.length > 0 ? parts.join('\n') : undefined;
}

function openEditor(): void {
  if (!canOpenEditor) {
    errorMessage.value = permissionDeniedMessage;
    return;
  }
  if (!workflowId.value) {
    return;
  }
  navigateTo(`workflows/${workflowId.value}/editor`);
}

async function loadWorkflow(): Promise<void> {
  if (!canAccessWorkflowDetailPage) {
    workflow.value = null;
    errorMessage.value = permissionDeniedMessage;
    loading.value = false;
    return;
  }

  if (!workflowId.value) {
    errorMessage.value = t('plugin.workflow-orchestration.tenant.common.messages.invalidRoute');
    loading.value = false;
    return;
  }

  loading.value = true;
  errorMessage.value = '';

  try {
    const detail = await getTenantWorkflowDetailApi(workflowId.value);
    if (!detail.versions || detail.versions.length === 0) {
      detail.versions = await listTenantWorkflowVersionsApi(workflowId.value);
    }
    workflow.value = detail;
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.loadFailed');
  } finally {
    loading.value = false;
  }
}

function buildPlannerPrompt(seed?: string): string {
  return buildPrompt([
    t('plugin.workflow-orchestration.tenant.workflow.ai.systemLead'),
    seed?.trim()
      ? t('plugin.workflow-orchestration.tenant.workflow.ai.userIdea', {
          idea: seed.trim(),
        })
      : t('plugin.workflow-orchestration.tenant.workflow.ai.emptyIdea'),
    t('plugin.workflow-orchestration.tenant.workflow.ai.outputContract'),
  ]);
}

function openAIPlanner(seed?: string): void {
  openWorkflowAIPanel({
    conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
    message: buildPlannerPrompt(seed),
    pageKey: TENANT_WORKFLOW_DETAIL_PAGE_KEY,
  });
}

async function runWorkflow(): Promise<{ message: string; success: boolean }> {
  if (!canRunWorkflow) {
    errorMessage.value = permissionDeniedMessage;
    return {
      success: false,
      message: permissionDeniedMessage,
    };
  }

  if (!workflow.value?.id) {
    return {
      success: false,
      message: t('plugin.workflow-orchestration.tenant.common.messages.invalidRoute'),
    };
  }

  actionBusy.value = true;
  try {
    const run = await executeTenantWorkflowApi(workflow.value.id);
    if (run.id) {
      navigateTo(`runs/${run.id}`);
      return {
        success: true,
        message: t('plugin.workflow-orchestration.tenant.workflow.actions.run'),
      };
    }
    await loadWorkflow();
    return {
      success: true,
      message: t('plugin.workflow-orchestration.tenant.workflow.actions.run'),
    };
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
    return {
      success: false,
      message: errorMessage.value,
    };
  } finally {
    actionBusy.value = false;
  }
}

async function publishWorkflow(): Promise<{ message: string; success: boolean }> {
  if (!canPublishWorkflow) {
    errorMessage.value = permissionDeniedMessage;
    return {
      success: false,
      message: permissionDeniedMessage,
    };
  }

  if (!workflow.value?.id) {
    return {
      success: false,
      message: t('plugin.workflow-orchestration.tenant.common.messages.invalidRoute'),
    };
  }

  actionBusy.value = true;
  try {
    workflow.value = await publishTenantWorkflowApi(workflow.value.id);
    return {
      success: true,
      message: t('plugin.workflow-orchestration.tenant.workflow.actions.publish'),
    };
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
    return {
      success: false,
      message: errorMessage.value,
    };
  } finally {
    actionBusy.value = false;
  }
}

useWorkflowPageAI({
  conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  pageKey: TENANT_WORKFLOW_DETAIL_PAGE_KEY,
  buildContext: () => ({
    entityDescription: t(
      'plugin.workflow-orchestration.tenant.workflow.detailDescription',
    ),
    entityTitle:
      workflow.value?.name
      || t('plugin.workflow-orchestration.tenant.workflow.untitled'),
    entityType: 'workflow_orchestration_tenant_workflow_detail',
    pageData: {
      can_execute: workflow.value?.canExecute ?? null,
      can_publish: workflow.value?.canPublish ?? null,
      current_version: workflow.value?.currentVersion ?? null,
      pending_approvals: workflow.value?.pendingApprovals ?? 0,
      published_version: workflow.value?.publishedVersion ?? null,
      related_artifact_count: workflow.value?.relatedArtifacts?.length ?? 0,
      related_run_count: workflow.value?.relatedRuns?.length ?? 0,
      status: workflow.value?.status ?? null,
      workflow_id: workflowId.value,
    },
    pageTitle:
      workflow.value?.name
      || t('plugin.workflow-orchestration.tenant.workflow.untitled'),
  }),
  operations: [
    {
      name: 'open_tenant_workflow_editor',
      label: t('plugin.workflow-orchestration.tenant.workflow.actions.openEditor'),
      description: t(
        'plugin.workflow-orchestration.tenant.workflow.detailDescription',
      ),
      readonly: true,
      handler: async () => {
        if (!canOpenEditor) {
          return {
            success: false,
            message: permissionDeniedMessage,
          };
        }
        openEditor();
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.workflow.actions.openEditor',
          ),
        };
      },
    },
    {
      name: 'publish_tenant_workflow',
      label: t('plugin.workflow-orchestration.tenant.workflow.actions.publish'),
      description: t(
        'plugin.workflow-orchestration.tenant.workflow.hints.publishBeforeRun',
      ),
      readonly: false,
      handler: publishWorkflow,
    },
    {
      name: 'run_tenant_workflow',
      label: t('plugin.workflow-orchestration.tenant.workflow.actions.run'),
      description: t(
        'plugin.workflow-orchestration.tenant.workflow.sections.relatedRunsHint',
      ),
      readonly: false,
      handler: runWorkflow,
    },
    {
      name: 'refresh_tenant_workflow_detail',
      label: t(
        'plugin.workflow-orchestration.tenant.workflow.ai.operations.refresh.label',
      ),
      description: t(
        'plugin.workflow-orchestration.tenant.workflow.ai.operations.refresh.description',
      ),
      readonly: true,
      handler: async () => {
        await loadWorkflow();
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.workflow.ai.operations.refresh.success',
          ),
        };
      },
    },
  ],
});

watch(
  () => route.params.id,
  () => {
    void loadWorkflow();
  },
  {
    immediate: true,
  },
);
</script>

<template>
  <ConsoleShell
    :description="workflow?.description || t('plugin.workflow-orchestration.tenant.workflow.detailDescription')"
    :eyebrow="t('plugin.workflow-orchestration.tenant.workflow.eyebrow')"
    :title="workflow?.name || t('plugin.workflow-orchestration.tenant.workflow.untitled')"
  >
    <template #actions>
      <button
        v-if="canAccessWorkflowDetailPage"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        @click="openAIPlanner(buildWorkflowPlannerSeed())"
      >
        {{ t('plugin.workflow-orchestration.tenant.workflow.actions.askAI') }}
      </button>
      <button
        v-if="canAccessWorkflowDetailPage && canOpenEditor"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        :disabled="workflow?.canEdit === false"
        @click="openEditor"
      >
        {{ t('plugin.workflow-orchestration.tenant.workflow.actions.openEditor') }}
      </button>
      <button
        v-if="canAccessWorkflowDetailPage && canPublishWorkflow"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="actionBusy || workflow?.canPublish === false"
        @click="publishWorkflow"
      >
        {{ t('plugin.workflow-orchestration.tenant.workflow.actions.publish') }}
      </button>
      <button
        v-if="canAccessWorkflowDetailPage && canRunWorkflow"
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="actionBusy || workflow?.canExecute === false"
        @click="runWorkflow"
      >
        {{
          actionBusy
            ? t('plugin.workflow-orchestration.tenant.common.messages.processing')
            : t('plugin.workflow-orchestration.tenant.workflow.actions.run')
        }}
      </button>
    </template>

    <EmptyState
      v-if="!canAccessWorkflowDetailPage"
      :title="permissionDeniedMessage"
    />
    <template v-else>
    <section
      v-if="errorMessage"
      class="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700"
    >
      {{ errorMessage }}
    </section>

    <section v-if="loading" class="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
      <div class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="h-5 w-52 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 h-44 animate-pulse rounded-3xl bg-slate-100" />
      </div>
      <div class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="h-5 w-36 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 space-y-3">
          <div class="h-16 animate-pulse rounded-2xl bg-slate-100" />
          <div class="h-16 animate-pulse rounded-2xl bg-slate-100" />
        </div>
      </div>
    </section>

    <template v-else-if="workflow">
      <section class="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex flex-wrap items-center gap-2">
            <StatusPill
              :label="labelForWorkflowStatus(workflow.status)"
              :tone="toneForWorkflowStatus(workflow.status)"
            />
            <StatusPill
              :label="labelForBuilderMode(workflow.builderMode)"
              tone="info"
            />
            <StatusPill
              v-if="workflow.riskLevel"
              :label="labelForRisk(workflow.riskLevel)"
              :tone="toneForRisk(workflow.riskLevel)"
            />
          </div>

          <dl class="mt-5 grid gap-3 text-sm text-slate-600 sm:grid-cols-2 xl:grid-cols-3">
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.workflow.fields.version') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ workflow.currentVersion || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.workflow.fields.publishedVersion') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ workflow.publishedVersion || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.workflow.fields.updatedAt') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatDateTime(workflow.updatedAt) }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.workflow.fields.pendingApprovals') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatNumber(workflow.pendingApprovals ?? 0) }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.workflow.fields.runCount7d') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatNumber(workflow.runCount7d ?? 0) }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflow-orchestration.tenant.workflow.fields.successRate7d') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatPercent(workflow.successRate7d) }}
              </dd>
            </div>
          </dl>

          <div class="mt-5 grid gap-4 lg:grid-cols-2">
            <div class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
              <h2 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.contextHealth') }}
              </h2>
              <p class="mt-2 text-sm leading-6 text-slate-600">
                {{
                  workflow.contextHealthSummary ||
                    t('plugin.workflow-orchestration.tenant.workflow.empty.contextHealth')
                }}
              </p>
            </div>
            <div class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
              <h2 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.policy') }}
              </h2>
              <p class="mt-2 text-sm leading-6 text-slate-600">
                {{
                  workflow.policySummary ||
                    t('plugin.workflow-orchestration.tenant.workflow.empty.policy')
                }}
              </p>
            </div>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.workflow.sections.structure') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.workflow.sections.structureHint') }}
            </p>
          </div>

          <div class="mt-5 space-y-3">
            <div
              v-for="node in topologyPreview"
              :key="node.id"
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="space-y-1">
                  <p class="text-sm font-semibold text-slate-900">
                    {{ node.name || t('plugin.workflow-orchestration.tenant.workflow.empty.nodeName') }}
                  </p>
                  <p class="text-sm text-slate-600">
                    {{ node.type }}
                  </p>
                </div>
                <StatusPill
                  v-if="node.status"
                  :label="labelForRunStatus(node.status)"
                  :tone="toneForRunStatus(node.status)"
                />
              </div>
            </div>
          </div>

          <div class="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4">
            <p class="text-sm font-semibold text-amber-900">
              {{ t('plugin.workflow-orchestration.tenant.workflow.sections.boundaryTitle') }}
            </p>
            <p class="mt-2 text-sm leading-6 text-amber-800">
              {{ t('plugin.workflow-orchestration.tenant.workflow.sections.boundaryHint') }}
            </p>
          </div>
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.contract') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.contractHint') }}
              </p>
            </div>
          </div>

          <div class="mt-5 grid gap-4 lg:grid-cols-2">
            <div class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
              <h3 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.inputs') }}
              </h3>
              <div
                v-if="workflow.inputVariables && workflow.inputVariables.length > 0"
                class="mt-4 space-y-3"
              >
                <div
                  v-for="input in workflow.inputVariables"
                  :key="input.name"
                  class="rounded-2xl bg-white px-4 py-3"
                >
                  <div class="flex items-center gap-2">
                    <p class="text-sm font-semibold text-slate-900">
                      {{ input.label || input.name }}
                    </p>
                    <StatusPill
                      :label="input.required ? t('plugin.workflow-orchestration.tenant.common.flags.required') : t('plugin.workflow-orchestration.tenant.common.flags.optional')"
                      :tone="input.required ? 'warning' : 'neutral'"
                    />
                  </div>
                  <p class="mt-2 text-sm text-slate-600">
                    {{ input.description || input.type || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
                  </p>
                </div>
              </div>
              <EmptyState
                v-else
                :description="t('plugin.workflow-orchestration.tenant.workflow.empty.inputDescription')"
                :title="t('plugin.workflow-orchestration.tenant.workflow.empty.inputTitle')"
              />
            </div>

            <div class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
              <h3 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.outputs') }}
              </h3>
              <div
                v-if="workflow.outputContracts && workflow.outputContracts.length > 0"
                class="mt-4 space-y-3"
              >
                <div
                  v-for="output in workflow.outputContracts"
                  :key="output.key"
                  class="rounded-2xl bg-white px-4 py-3"
                >
                  <p class="text-sm font-semibold text-slate-900">
                    {{ output.label || output.key }}
                  </p>
                  <p class="mt-2 text-sm text-slate-600">
                    {{ output.description || output.type || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
                  </p>
                </div>
              </div>
              <EmptyState
                v-else
                :description="t('plugin.workflow-orchestration.tenant.workflow.empty.outputDescription')"
                :title="t('plugin.workflow-orchestration.tenant.workflow.empty.outputTitle')"
              />
            </div>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.versions') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.versionsHint') }}
              </p>
            </div>
          </div>

          <div
            v-if="workflow.versions && workflow.versions.length > 0"
            class="mt-5 space-y-3"
          >
            <div
              v-for="version in workflow.versions"
              :key="version.id || version.version"
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4"
            >
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div class="space-y-1">
                  <div class="flex items-center gap-2">
                    <p class="text-sm font-semibold text-slate-900">
                      {{ version.version || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
                    </p>
                    <StatusPill
                      v-if="version.isCurrent"
                      :label="t('plugin.workflow-orchestration.tenant.workflow.flags.currentVersion')"
                      tone="success"
                    />
                  </div>
                  <p class="text-xs text-slate-500">
                    {{ version.createdBy || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
                    ·
                    {{ formatDateTime(version.createdAt) }}
                  </p>
                </div>
                <StatusPill
                  v-if="version.status"
                  :label="version.status"
                  tone="neutral"
                />
              </div>
              <p
                v-if="version.changeLog"
                class="mt-3 text-sm leading-6 text-slate-600"
              >
                {{ version.changeLog }}
              </p>
            </div>
          </div>
          <EmptyState
            v-else
            :description="t('plugin.workflow-orchestration.tenant.workflow.empty.versionDescription')"
            :title="t('plugin.workflow-orchestration.tenant.workflow.empty.versionTitle')"
          />
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.relatedRuns') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.relatedRunsHint') }}
              </p>
            </div>
            <button
              v-if="canOpenRuns"
              class="text-sm font-medium text-sky-700 transition hover:text-sky-800"
              @click="navigateTo('runs')"
            >
              {{ t('plugin.workflow-orchestration.tenant.common.actions.openRuns') }}
            </button>
          </div>

          <div
            v-if="workflow.relatedRuns && workflow.relatedRuns.length > 0"
            class="mt-5 space-y-3"
          >
            <button
              v-for="run in workflow.relatedRuns"
              :key="run.id"
              class="flex w-full items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left transition hover:border-sky-200 hover:bg-sky-50/60 disabled:cursor-not-allowed disabled:opacity-70"
              :disabled="!canOpenRunDetail"
              @click="navigateTo(`runs/${run.id}`)"
            >
              <div class="min-w-0 space-y-1">
                <p class="truncate text-sm font-semibold text-slate-900">
                  {{ run.name || t('plugin.workflow-orchestration.tenant.run.untitled') }}
                </p>
                <p class="truncate text-xs text-slate-500">
                  {{ formatRelativeTime(run.updatedAt) }}
                </p>
              </div>
              <StatusPill
                :label="labelForRunStatus(run.status)"
                :tone="toneForRunStatus(run.status)"
              />
            </button>
          </div>
          <EmptyState
            v-else
            :description="t('plugin.workflow-orchestration.tenant.workflow.empty.relatedRunDescription')"
            :title="t('plugin.workflow-orchestration.tenant.workflow.empty.relatedRunTitle')"
          />
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.relatedArtifacts') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflow-orchestration.tenant.workflow.sections.relatedArtifactsHint') }}
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
            v-if="workflow.relatedArtifacts && workflow.relatedArtifacts.length > 0"
            class="mt-5 space-y-3"
          >
            <button
              v-for="artifact in workflow.relatedArtifacts"
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
            :description="t('plugin.workflow-orchestration.tenant.workflow.empty.relatedArtifactDescription')"
            :title="t('plugin.workflow-orchestration.tenant.workflow.empty.relatedArtifactTitle')"
          />
        </article>
      </section>
    </template>

    <EmptyState
      v-else
      :description="t('plugin.workflow-orchestration.tenant.workflow.empty.detailDescription')"
      :title="t('plugin.workflow-orchestration.tenant.workflow.empty.detailTitle')"
    />
    </template>
  </ConsoleShell>
</template>
