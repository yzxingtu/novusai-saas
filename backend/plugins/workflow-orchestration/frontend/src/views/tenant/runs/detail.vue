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
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantRunDetail',
});

const route = useRoute();
const {
  canRunAction,
  formatDateTime,
  formatRelativeTime,
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

async function loadRun(): Promise<void> {
  if (!runId.value) {
    errorMessage.value = t('plugin.workflowOrchestration.tenant.common.messages.invalidRoute');
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
        : t('plugin.workflowOrchestration.tenant.common.messages.loadFailed');
  } finally {
    loading.value = false;
  }
}

async function handleAction(
  action: 'pause' | 'resume' | 'retry' | 'terminate',
): Promise<void> {
  if (!run.value?.id) {
    return;
  }

  if (
    action === 'terminate' &&
    !window.confirm(
      t('plugin.workflowOrchestration.tenant.run.confirm.terminate'),
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
        : t('plugin.workflowOrchestration.tenant.common.messages.actionFailed');
  } finally {
    actionBusy.value = false;
  }
}

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
    :description="t('plugin.workflowOrchestration.tenant.run.detailDescription')"
    :eyebrow="t('plugin.workflowOrchestration.tenant.run.eyebrow')"
    :title="run?.name || t('plugin.workflowOrchestration.tenant.run.untitled')"
  >
    <template #actions>
      <button
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="actionBusy || !canRunAction(run, 'pause')"
        @click="handleAction('pause')"
      >
        {{ t('plugin.workflowOrchestration.tenant.run.actions.pause') }}
      </button>
      <button
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="actionBusy || !canRunAction(run, 'resume')"
        @click="handleAction('resume')"
      >
        {{ t('plugin.workflowOrchestration.tenant.run.actions.resume') }}
      </button>
      <button
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="actionBusy || !canRunAction(run, 'retry')"
        @click="handleAction('retry')"
      >
        {{
          actionBusy
            ? t('plugin.workflowOrchestration.tenant.common.messages.processing')
            : t('plugin.workflowOrchestration.tenant.run.actions.retry')
        }}
      </button>
      <button
        class="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="actionBusy || !canRunAction(run, 'terminate')"
        @click="handleAction('terminate')"
      >
        {{ t('plugin.workflowOrchestration.tenant.run.actions.terminate') }}
      </button>
    </template>

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
                {{ t('plugin.workflowOrchestration.tenant.run.fields.workflowName') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ run.workflowName || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.run.fields.currentNodeName') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ run.currentNodeName || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.run.fields.snapshotVersion') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ run.snapshotVersion || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.run.fields.startedAt') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatDateTime(run.startedAt) }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.run.fields.updatedAt') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatRelativeTime(run.updatedAt) }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.run.fields.costSummary') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ run.costSummary || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
          </dl>

          <div class="mt-5 rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
            <h2 class="text-sm font-semibold text-slate-900">
              {{ t('plugin.workflowOrchestration.tenant.run.sections.contractSummary') }}
            </h2>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {{ run.contractSummary || t('plugin.workflowOrchestration.tenant.run.empty.contractSummary') }}
            </p>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflowOrchestration.tenant.run.sections.timeline') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflowOrchestration.tenant.run.sections.timelineHint') }}
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
                    {{ nodeRun.nodeName || t('plugin.workflowOrchestration.tenant.workflow.empty.nodeName') }}
                  </p>
                  <p class="text-sm text-slate-600">
                    {{ nodeRun.nodeType || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
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
                      : t('plugin.workflowOrchestration.tenant.common.placeholders.empty')
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
            :description="t('plugin.workflowOrchestration.tenant.run.empty.timelineDescription')"
            :title="t('plugin.workflowOrchestration.tenant.run.empty.timelineTitle')"
          />
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflowOrchestration.tenant.run.sections.inputOutput') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflowOrchestration.tenant.run.sections.inputOutputHint') }}
            </p>
          </div>

          <div class="mt-5 grid gap-4 lg:grid-cols-2">
            <div class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
              <h3 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflowOrchestration.tenant.run.sections.inputPayload') }}
              </h3>
              <pre
                v-if="prettyInput"
                class="mt-4 max-h-80 overflow-auto rounded-2xl bg-slate-900 p-4 text-xs leading-6 text-slate-100"
              >{{ prettyInput }}</pre>
              <EmptyState
                v-else
                :description="t('plugin.workflowOrchestration.tenant.run.empty.inputDescription')"
                :title="t('plugin.workflowOrchestration.tenant.run.empty.inputTitle')"
              />
            </div>

            <div class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
              <h3 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflowOrchestration.tenant.run.sections.outputPayload') }}
              </h3>
              <pre
                v-if="prettyOutput"
                class="mt-4 max-h-80 overflow-auto rounded-2xl bg-slate-900 p-4 text-xs leading-6 text-slate-100"
              >{{ prettyOutput }}</pre>
              <EmptyState
                v-else
                :description="t('plugin.workflowOrchestration.tenant.run.empty.outputDescription')"
                :title="t('plugin.workflowOrchestration.tenant.run.empty.outputTitle')"
              />
            </div>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflowOrchestration.tenant.run.sections.artifacts') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflowOrchestration.tenant.run.sections.artifactsHint') }}
              </p>
            </div>
            <button
              class="text-sm font-medium text-sky-700 transition hover:text-sky-800"
              @click="navigateTo('artifacts')"
            >
              {{ t('plugin.workflowOrchestration.tenant.common.actions.openArtifacts') }}
            </button>
          </div>

          <div
            v-if="run.artifacts && run.artifacts.length > 0"
            class="mt-5 space-y-3"
          >
            <button
              v-for="artifact in run.artifacts"
              :key="artifact.id"
              class="flex w-full items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left transition hover:border-sky-200 hover:bg-sky-50/60"
              @click="navigateTo(`artifacts/${artifact.id}`)"
            >
              <div class="min-w-0 space-y-2">
                <p class="truncate text-sm font-semibold text-slate-900">
                  {{ artifact.title || t('plugin.workflowOrchestration.tenant.artifact.untitled') }}
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
            :description="t('plugin.workflowOrchestration.tenant.run.empty.artifactDescription')"
            :title="t('plugin.workflowOrchestration.tenant.run.empty.artifactTitle')"
          />
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflowOrchestration.tenant.run.sections.approvals') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflowOrchestration.tenant.run.sections.approvalsHint') }}
              </p>
            </div>
            <button
              v-if="run.hostApprovalPath"
              class="text-sm font-medium text-sky-700 transition hover:text-sky-800"
              @click="openExternal(run.hostApprovalPath)"
            >
              {{ t('plugin.workflowOrchestration.tenant.run.actions.openHostApproval') }}
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
                  {{ approval.approverName || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
                </p>
              </div>
              <div class="text-right text-xs text-slate-500">
                <p>{{ approval.status || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}</p>
                <p>{{ formatDateTime(approval.dueAt) }}</p>
              </div>
            </button>
          </div>
          <EmptyState
            v-else
            :description="t('plugin.workflowOrchestration.tenant.run.empty.approvalDescription')"
            :title="t('plugin.workflowOrchestration.tenant.run.empty.approvalTitle')"
          />
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflowOrchestration.tenant.run.sections.recovery') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflowOrchestration.tenant.run.sections.recoveryHint') }}
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
            :description="t('plugin.workflowOrchestration.tenant.run.empty.recoveryDescription')"
            :title="t('plugin.workflowOrchestration.tenant.run.empty.recoveryTitle')"
          />
        </article>
      </section>
    </template>

    <EmptyState
      v-else
      :description="t('plugin.workflowOrchestration.tenant.run.empty.detailDescription')"
      :title="t('plugin.workflowOrchestration.tenant.run.empty.detailTitle')"
    />
  </ConsoleShell>
</template>
