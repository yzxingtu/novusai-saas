<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';

import {
  getTenantBuilderCapabilitiesApi,
  getTenantHomeApi,
} from '../../../api/tenant';
import type {
  TenantBuilderCapability,
  TenantHomePayload,
  TenantHomeStatCard,
} from '../../../types/tenant';
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantHome',
});

const {
  formatNumber,
  formatPercent,
  formatRelativeTime,
  labelForArtifactStatus,
  labelForCapability,
  labelForRisk,
  labelForRunStatus,
  labelForWorkflowStatus,
  navigateTo,
  openExternal,
  t,
  toneForArtifactStatus,
  toneForRisk,
  toneForRunStatus,
  toneForWorkflowStatus,
} = useTenantOrchestration();

const loading = ref(true);
const errorMessage = ref('');
const home = ref<TenantHomePayload>({
  alerts: [],
  highlightedWorkflows: [],
  latestArtifacts: [],
  latestRuns: [],
  stats: [],
  todos: [],
});
const capabilities = ref<TenantBuilderCapability[]>([]);

const defaultStats = computed<TenantHomeStatCard[]>(() => [
  {
    code: 'pending_approvals',
    label: t('plugin.workflowOrchestration.tenant.home.metrics.pendingApprovals'),
    tone: 'warning',
    value: home.value.summary?.pendingApprovals ?? 0,
  },
  {
    code: 'failed_runs',
    label: t('plugin.workflowOrchestration.tenant.home.metrics.failedRuns'),
    tone: 'danger',
    value: home.value.summary?.failedRuns ?? 0,
  },
  {
    code: 'pending_artifacts',
    label: t('plugin.workflowOrchestration.tenant.home.metrics.pendingArtifacts'),
    tone: 'info',
    value: home.value.summary?.pendingArtifacts ?? 0,
  },
  {
    code: 'active_workflows',
    label: t('plugin.workflowOrchestration.tenant.home.metrics.activeWorkflows'),
    tone: 'success',
    value: home.value.summary?.activeWorkflows ?? 0,
  },
]);

const statCards = computed(() => {
  return home.value.stats && home.value.stats.length > 0
    ? home.value.stats
    : defaultStats.value;
});

const capabilityMap = computed(() => {
  return new Map(capabilities.value.map((item) => [item.code, item]));
});

const boundaryItems = computed(() => {
  return [
    {
      code: 'tenant_simple_builder',
      enabled: capabilityMap.value.get('tenant_simple_builder')?.enabled ?? false,
      hint:
        capabilityMap.value.get('tenant_simple_builder')?.reason ??
        t('plugin.workflowOrchestration.tenant.capability.hints.tenant_simple_builder'),
    },
    {
      code: 'tenant_template_editor',
      enabled:
        capabilityMap.value.get('tenant_template_editor')?.enabled ?? false,
      hint:
        capabilityMap.value.get('tenant_template_editor')?.reason ??
        t('plugin.workflowOrchestration.tenant.capability.hints.tenant_template_editor'),
    },
    {
      code: 'agentic_builder',
      enabled: capabilityMap.value.get('agentic_builder')?.enabled ?? false,
      hint:
        capabilityMap.value.get('agentic_builder')?.reason ??
        t('plugin.workflowOrchestration.tenant.capability.hints.agentic_builder'),
    },
  ];
});

const lockedBoundaryCodes = [
  'code_nodes',
  'connector_management',
  'platform_policy_changes',
];

async function loadPage(): Promise<void> {
  loading.value = true;
  errorMessage.value = '';

  try {
    const [homePayload, capabilityPayload] = await Promise.all([
      getTenantHomeApi(),
      getTenantBuilderCapabilitiesApi(),
    ]);
    home.value = homePayload;
    capabilities.value =
      homePayload.builderCapabilities && homePayload.builderCapabilities.length > 0
        ? homePayload.builderCapabilities
        : capabilityPayload;
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflowOrchestration.tenant.common.messages.loadFailed');
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadPage();
});
</script>

<template>
  <ConsoleShell
    :description="t('plugin.workflowOrchestration.tenant.home.description')"
    :eyebrow="t('plugin.workflowOrchestration.tenant.home.eyebrow')"
    :title="t('plugin.workflowOrchestration.tenant.home.title')"
  >
    <template #actions>
      <button
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        @click="navigateTo('runs')"
      >
        {{ t('plugin.workflowOrchestration.tenant.common.actions.openRuns') }}
      </button>
      <button
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        @click="navigateTo('workflows')"
      >
        {{ t('plugin.workflowOrchestration.tenant.common.actions.openWorkflows') }}
      </button>
    </template>

    <section
      v-if="errorMessage"
      class="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700"
    >
      {{ errorMessage }}
    </section>

    <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <article
        v-for="card in statCards"
        :key="card.code"
        class="rounded-3xl border border-white/70 bg-white/90 px-5 py-5 shadow-sm"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="space-y-2">
            <p class="text-sm font-medium text-slate-500">
              {{ card.label }}
            </p>
            <p class="text-3xl font-semibold tracking-tight text-slate-900">
              {{ formatNumber(card.value) }}
            </p>
            <p
              v-if="card.hint"
              class="text-xs leading-5 text-slate-500"
            >
              {{ card.hint }}
            </p>
          </div>
          <StatusPill
            :label="t(`plugin.workflowOrchestration.tenant.common.tones.${card.tone ?? 'info'}`)"
            :tone="card.tone ?? 'info'"
          />
        </div>
      </article>
    </section>

    <section v-if="loading" class="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
      <div class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="h-6 w-48 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 space-y-3">
          <div class="h-16 animate-pulse rounded-2xl bg-slate-100" />
          <div class="h-16 animate-pulse rounded-2xl bg-slate-100" />
          <div class="h-16 animate-pulse rounded-2xl bg-slate-100" />
        </div>
      </div>
      <div class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="h-6 w-36 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 space-y-3">
          <div class="h-24 animate-pulse rounded-2xl bg-slate-100" />
          <div class="h-24 animate-pulse rounded-2xl bg-slate-100" />
        </div>
      </div>
    </section>

    <section v-else class="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
      <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflowOrchestration.tenant.home.sections.todayTodo') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflowOrchestration.tenant.home.sections.todayTodoHint') }}
            </p>
          </div>
          <button
            class="text-sm font-medium text-sky-700 transition hover:text-sky-800"
            @click="navigateTo('runs')"
          >
            {{ t('plugin.workflowOrchestration.tenant.common.actions.viewAll') }}
          </button>
        </div>

        <div
          v-if="home.todos && home.todos.length > 0"
          class="mt-5 space-y-3"
        >
          <button
            v-for="todo in home.todos"
            :key="todo.id"
            class="flex w-full items-start gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-left transition hover:border-sky-200 hover:bg-sky-50/60"
            @click="openExternal(todo.targetPath || 'runs')"
          >
            <div class="mt-1 h-2.5 w-2.5 rounded-full bg-sky-500" />
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <p class="text-sm font-semibold text-slate-900">
                  {{ todo.title }}
                </p>
                <StatusPill
                  :label="t(`plugin.workflowOrchestration.tenant.common.todoCategory.${todo.category}`)"
                  tone="info"
                />
                <StatusPill
                  v-if="todo.severity"
                  :label="t(`plugin.workflowOrchestration.tenant.common.severity.${todo.severity}`)"
                  :tone="todo.severity === 'high' ? 'danger' : todo.severity === 'medium' ? 'warning' : 'info'"
                />
              </div>
              <p
                v-if="todo.summary"
                class="mt-2 text-sm leading-6 text-slate-600"
              >
                {{ todo.summary }}
              </p>
              <div class="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                <span v-if="todo.dueAt">
                  {{ formatRelativeTime(todo.dueAt) }}
                </span>
                <span>
                  {{ todo.actionLabel || t('plugin.workflowOrchestration.tenant.common.actions.handleNow') }}
                </span>
              </div>
            </div>
          </button>
        </div>
        <EmptyState
          v-else
          :description="t('plugin.workflowOrchestration.tenant.home.empty.todoDescription')"
          :title="t('plugin.workflowOrchestration.tenant.home.empty.todoTitle')"
        />
      </article>

      <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div>
          <h2 class="text-lg font-semibold text-slate-900">
            {{ t('plugin.workflowOrchestration.tenant.home.sections.boundary') }}
          </h2>
          <p class="mt-1 text-sm text-slate-500">
            {{ t('plugin.workflowOrchestration.tenant.home.sections.boundaryHint') }}
          </p>
        </div>

        <div class="mt-5 grid gap-3">
          <div
            v-for="item in boundaryItems"
            :key="item.code"
            class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="space-y-1">
                <p class="text-sm font-semibold text-slate-900">
                  {{ labelForCapability(item.code) }}
                </p>
                <p class="text-sm leading-6 text-slate-600">
                  {{ item.hint }}
                </p>
              </div>
              <StatusPill
                :label="t(`plugin.workflowOrchestration.tenant.capability.state.${item.enabled ? 'enabled' : 'disabled'}`)"
                :tone="item.enabled ? 'success' : 'neutral'"
              />
            </div>
          </div>
        </div>

        <div class="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4">
          <p class="text-sm font-semibold text-amber-900">
            {{ t('plugin.workflowOrchestration.tenant.home.sections.lockedTitle') }}
          </p>
          <ul class="mt-3 space-y-2 text-sm text-amber-800">
            <li
              v-for="code in lockedBoundaryCodes"
              :key="code"
            >
              {{ t(`plugin.workflowOrchestration.tenant.capability.locked.${code}`) }}
            </li>
          </ul>
        </div>
      </article>
    </section>

    <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
      <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflowOrchestration.tenant.home.sections.highlightedWorkflows') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflowOrchestration.tenant.home.sections.highlightedWorkflowsHint') }}
            </p>
          </div>
          <button
            class="text-sm font-medium text-sky-700 transition hover:text-sky-800"
            @click="navigateTo('workflows')"
          >
            {{ t('plugin.workflowOrchestration.tenant.common.actions.openWorkflows') }}
          </button>
        </div>

        <div
          v-if="home.highlightedWorkflows && home.highlightedWorkflows.length > 0"
          class="mt-5 space-y-3"
        >
          <button
            v-for="workflow in home.highlightedWorkflows"
            :key="workflow.id"
            class="flex w-full flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 text-left transition hover:border-sky-200 hover:bg-sky-50/60"
            @click="navigateTo(`workflows/${workflow.id}`)"
          >
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="space-y-2">
                <p class="text-sm font-semibold text-slate-900">
                  {{ workflow.name || t('plugin.workflowOrchestration.tenant.workflow.untitled') }}
                </p>
                <div class="flex flex-wrap items-center gap-2">
                  <StatusPill
                    :label="labelForWorkflowStatus(workflow.status)"
                    :tone="toneForWorkflowStatus(workflow.status)"
                  />
                  <StatusPill
                    v-if="workflow.riskLevel"
                    :label="labelForRisk(workflow.riskLevel)"
                    :tone="toneForRisk(workflow.riskLevel)"
                  />
                </div>
              </div>
              <span class="text-xs text-slate-500">
                {{ formatRelativeTime(workflow.updatedAt) }}
              </span>
            </div>
            <div class="grid gap-3 text-sm text-slate-600 sm:grid-cols-3">
              <div>
                <p class="text-xs uppercase tracking-wide text-slate-400">
                  {{ t('plugin.workflowOrchestration.tenant.workflow.fields.version') }}
                </p>
                <p class="mt-1 font-medium text-slate-900">
                  {{ workflow.currentVersion || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
                </p>
              </div>
              <div>
                <p class="text-xs uppercase tracking-wide text-slate-400">
                  {{ t('plugin.workflowOrchestration.tenant.workflow.fields.successRate7d') }}
                </p>
                <p class="mt-1 font-medium text-slate-900">
                  {{ formatPercent(workflow.successRate7d) }}
                </p>
              </div>
              <div>
                <p class="text-xs uppercase tracking-wide text-slate-400">
                  {{ t('plugin.workflowOrchestration.tenant.workflow.fields.pendingApprovals') }}
                </p>
                <p class="mt-1 font-medium text-slate-900">
                  {{ formatNumber(workflow.pendingApprovals ?? 0) }}
                </p>
              </div>
            </div>
          </button>
        </div>
        <EmptyState
          v-else
          :description="t('plugin.workflowOrchestration.tenant.home.empty.workflowDescription')"
          :title="t('plugin.workflowOrchestration.tenant.home.empty.workflowTitle')"
        >
          <button
            class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
            @click="navigateTo('workflows')"
          >
            {{ t('plugin.workflowOrchestration.tenant.common.actions.openWorkflows') }}
          </button>
        </EmptyState>
      </article>

      <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflowOrchestration.tenant.home.sections.opsStream') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflowOrchestration.tenant.home.sections.opsStreamHint') }}
            </p>
          </div>
          <button
            class="text-sm font-medium text-sky-700 transition hover:text-sky-800"
            @click="navigateTo('artifacts')"
          >
            {{ t('plugin.workflowOrchestration.tenant.common.actions.openArtifacts') }}
          </button>
        </div>

        <div class="mt-5 space-y-4">
          <div>
            <div class="mb-3 flex items-center justify-between gap-3">
              <h3 class="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                {{ t('plugin.workflowOrchestration.tenant.home.sections.latestRuns') }}
              </h3>
              <button
                class="text-xs font-medium text-sky-700 transition hover:text-sky-800"
                @click="navigateTo('runs')"
              >
                {{ t('plugin.workflowOrchestration.tenant.common.actions.viewAll') }}
              </button>
            </div>
            <div
              v-if="home.latestRuns && home.latestRuns.length > 0"
              class="space-y-3"
            >
              <button
                v-for="run in home.latestRuns.slice(0, 3)"
                :key="run.id"
                class="flex w-full items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left transition hover:border-sky-200 hover:bg-sky-50/60"
                @click="navigateTo(`runs/${run.id}`)"
              >
                <div class="min-w-0 space-y-1">
                  <p class="truncate text-sm font-semibold text-slate-900">
                    {{ run.name || t('plugin.workflowOrchestration.tenant.run.untitled') }}
                  </p>
                  <p class="truncate text-xs text-slate-500">
                    {{ run.workflowName || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
                  </p>
                </div>
                <div class="flex flex-col items-end gap-2">
                  <StatusPill
                    :label="labelForRunStatus(run.status)"
                    :tone="toneForRunStatus(run.status)"
                  />
                  <span class="text-xs text-slate-500">
                    {{ formatRelativeTime(run.updatedAt) }}
                  </span>
                </div>
              </button>
            </div>
            <EmptyState
              v-else
              :description="t('plugin.workflowOrchestration.tenant.home.empty.runDescription')"
              :title="t('plugin.workflowOrchestration.tenant.home.empty.runTitle')"
            />
          </div>

          <div>
            <div class="mb-3 flex items-center justify-between gap-3">
              <h3 class="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                {{ t('plugin.workflowOrchestration.tenant.home.sections.latestArtifacts') }}
              </h3>
              <button
                class="text-xs font-medium text-sky-700 transition hover:text-sky-800"
                @click="navigateTo('artifacts')"
              >
                {{ t('plugin.workflowOrchestration.tenant.common.actions.viewAll') }}
              </button>
            </div>
            <div
              v-if="home.latestArtifacts && home.latestArtifacts.length > 0"
              class="space-y-3"
            >
              <button
                v-for="artifact in home.latestArtifacts.slice(0, 3)"
                :key="artifact.id"
                class="flex w-full flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-sky-200 hover:bg-sky-50/60"
                @click="navigateTo(`artifacts/${artifact.id}`)"
              >
                <div class="flex items-center justify-between gap-3">
                  <p class="truncate text-sm font-semibold text-slate-900">
                    {{ artifact.title || t('plugin.workflowOrchestration.tenant.artifact.untitled') }}
                  </p>
                  <StatusPill
                    :label="labelForArtifactStatus(artifact.status)"
                    :tone="toneForArtifactStatus(artifact.status)"
                  />
                </div>
                <p
                  v-if="artifact.previewText"
                  class="line-clamp-2 text-sm leading-6 text-slate-600"
                >
                  {{ artifact.previewText }}
                </p>
                <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                  <span>{{ artifact.workflowName || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}</span>
                  <span>{{ formatRelativeTime(artifact.updatedAt) }}</span>
                </div>
              </button>
            </div>
            <EmptyState
              v-else
              :description="t('plugin.workflowOrchestration.tenant.home.empty.artifactDescription')"
              :title="t('plugin.workflowOrchestration.tenant.home.empty.artifactTitle')"
            />
          </div>
        </div>
      </article>
    </section>

    <section
      v-if="home.alerts && home.alerts.length > 0"
      class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm"
    >
      <div class="flex items-center justify-between gap-3">
        <div>
          <h2 class="text-lg font-semibold text-slate-900">
            {{ t('plugin.workflowOrchestration.tenant.home.sections.alerts') }}
          </h2>
          <p class="mt-1 text-sm text-slate-500">
            {{ t('plugin.workflowOrchestration.tenant.home.sections.alertsHint') }}
          </p>
        </div>
      </div>
      <div class="mt-5 grid gap-3 lg:grid-cols-2">
        <button
          v-for="alert in home.alerts"
          :key="alert.id"
          class="flex items-start gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-left transition hover:border-sky-200 hover:bg-sky-50/60"
          @click="openExternal(alert.targetPath || 'runs')"
        >
          <div
            class="mt-1 h-3 w-3 rounded-full"
            :class="
              alert.level === 'critical' || alert.level === 'high'
                ? 'bg-rose-500'
                : alert.level === 'medium'
                  ? 'bg-amber-500'
                  : 'bg-sky-500'
            "
          />
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <p class="text-sm font-semibold text-slate-900">
                {{ alert.title }}
              </p>
              <StatusPill
                :label="t(`plugin.workflowOrchestration.tenant.common.severity.${alert.level}`)"
                :tone="alert.level === 'critical' || alert.level === 'high' ? 'danger' : alert.level === 'medium' ? 'warning' : 'info'"
              />
            </div>
            <p
              v-if="alert.summary"
              class="mt-2 text-sm leading-6 text-slate-600"
            >
              {{ alert.summary }}
            </p>
          </div>
        </button>
      </div>
    </section>
  </ConsoleShell>
</template>
