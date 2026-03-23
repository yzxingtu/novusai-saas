<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';

import {
  executeTenantWorkflowApi,
  listTenantWorkflowsApi,
} from '../../../api/tenant';
import type { TenantWorkflowSummary } from '../../../types/tenant';
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantWorkflowList',
});

const {
  formatNumber,
  formatPercent,
  formatRelativeTime,
  labelForBuilderMode,
  labelForRisk,
  labelForRunStatus,
  labelForWorkflowStatus,
  navigateTo,
  t,
  toneForRisk,
  toneForRunStatus,
  toneForWorkflowStatus,
} = useTenantOrchestration();

const loading = ref(true);
const actionLoadingId = ref<null | number>(null);
const errorMessage = ref('');
const workflows = ref<TenantWorkflowSummary[]>([]);
const keyword = ref('');
const selectedStatus = ref('');
const selectedBuilderMode = ref('');
const page = ref(1);
const size = ref(9);
const total = ref(0);

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(total.value / size.value));
});

const statusOptions = [
  'draft',
  'published',
  'paused',
  'disabled',
  'archived',
  'error',
];

const builderModeOptions = [
  'tenant_simple_builder',
  'tenant_template_editor',
  'copied_from_template',
];

async function loadWorkflows(): Promise<void> {
  loading.value = true;
  errorMessage.value = '';

  try {
    const result = await listTenantWorkflowsApi({
      builderModes: selectedBuilderMode.value
        ? [selectedBuilderMode.value]
        : undefined,
      keyword: keyword.value || undefined,
      page: page.value,
      size: size.value,
      statuses: selectedStatus.value ? [selectedStatus.value] : undefined,
    });
    workflows.value = result.items;
    total.value = result.total;
    size.value = result.size || size.value;
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflowOrchestration.tenant.common.messages.loadFailed');
  } finally {
    loading.value = false;
  }
}

function applyFilters(): void {
  page.value = 1;
  void loadWorkflows();
}

function resetFilters(): void {
  keyword.value = '';
  selectedStatus.value = '';
  selectedBuilderMode.value = '';
  page.value = 1;
  void loadWorkflows();
}

async function executeWorkflow(workflow: TenantWorkflowSummary): Promise<void> {
  if (!workflow.id) {
    return;
  }

  actionLoadingId.value = workflow.id;
  try {
    const run = await executeTenantWorkflowApi(workflow.id);
    if (run.id) {
      navigateTo(`runs/${run.id}`);
    } else {
      await loadWorkflows();
    }
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflowOrchestration.tenant.common.messages.actionFailed');
  } finally {
    actionLoadingId.value = null;
  }
}

function openEditor(workflowId: number): void {
  navigateTo(`workflows/${workflowId}/editor`);
}

function openDetail(workflowId: number): void {
  navigateTo(`workflows/${workflowId}`);
}

function createWorkflow(): void {
  navigateTo('workflows/new/editor');
}

onMounted(() => {
  void loadWorkflows();
});
</script>

<template>
  <ConsoleShell
    :description="t('plugin.workflowOrchestration.tenant.workflow.listDescription')"
    :eyebrow="t('plugin.workflowOrchestration.tenant.workflow.eyebrow')"
    :title="t('plugin.workflowOrchestration.tenant.workflow.listTitle')"
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
        @click="createWorkflow"
      >
        {{ t('plugin.workflowOrchestration.tenant.workflow.actions.create') }}
      </button>
    </template>

    <section class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_repeat(3,minmax(0,0.5fr))]">
        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflowOrchestration.tenant.workflow.filters.keyword') }}</span>
          <input
            v-model="keyword"
            class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
            :placeholder="t('plugin.workflowOrchestration.tenant.workflow.placeholders.keyword')"
            @keyup.enter="applyFilters"
          />
        </label>

        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflowOrchestration.tenant.workflow.filters.status') }}</span>
          <select
            v-model="selectedStatus"
            class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
          >
            <option value="">
              {{ t('plugin.workflowOrchestration.tenant.common.filters.allStatus') }}
            </option>
            <option
              v-for="status in statusOptions"
              :key="status"
              :value="status"
            >
              {{ labelForWorkflowStatus(status) }}
            </option>
          </select>
        </label>

        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflowOrchestration.tenant.workflow.filters.builderMode') }}</span>
          <select
            v-model="selectedBuilderMode"
            class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
          >
            <option value="">
              {{ t('plugin.workflowOrchestration.tenant.common.filters.allBuilderModes') }}
            </option>
            <option
              v-for="mode in builderModeOptions"
              :key="mode"
              :value="mode"
            >
              {{ labelForBuilderMode(mode) }}
            </option>
          </select>
        </label>

        <div class="flex flex-wrap items-end gap-3">
          <button
            class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
            @click="applyFilters"
          >
            {{ t('plugin.workflowOrchestration.tenant.common.actions.applyFilters') }}
          </button>
          <button
            class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
            @click="resetFilters"
          >
            {{ t('plugin.workflowOrchestration.tenant.common.actions.resetFilters') }}
          </button>
        </div>
      </div>

      <p
        v-if="errorMessage"
        class="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
      >
        {{ errorMessage }}
      </p>
    </section>

    <section v-if="loading" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <div
        v-for="index in 6"
        :key="index"
        class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm"
      >
        <div class="h-5 w-40 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 h-20 animate-pulse rounded-2xl bg-slate-100" />
        <div class="mt-4 h-10 animate-pulse rounded-2xl bg-slate-100" />
      </div>
    </section>

    <section
      v-else-if="workflows.length > 0"
      class="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      <article
        v-for="workflow in workflows"
        :key="workflow.id"
        class="flex flex-col gap-4 rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="space-y-2">
            <h2 class="text-lg font-semibold text-slate-900">
              {{ workflow.name || t('plugin.workflowOrchestration.tenant.workflow.untitled') }}
            </h2>
            <p
              v-if="workflow.description"
              class="line-clamp-2 text-sm leading-6 text-slate-600"
            >
              {{ workflow.description }}
            </p>
          </div>
          <button
            class="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="openDetail(workflow.id)"
          >
            {{ t('plugin.workflowOrchestration.tenant.common.actions.openDetail') }}
          </button>
        </div>

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

        <dl class="grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
          <div class="rounded-2xl bg-slate-50 px-4 py-3">
            <dt class="text-xs uppercase tracking-wide text-slate-400">
              {{ t('plugin.workflowOrchestration.tenant.workflow.fields.version') }}
            </dt>
            <dd class="mt-1 font-medium text-slate-900">
              {{ workflow.currentVersion || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
            </dd>
          </div>
          <div class="rounded-2xl bg-slate-50 px-4 py-3">
            <dt class="text-xs uppercase tracking-wide text-slate-400">
              {{ t('plugin.workflowOrchestration.tenant.workflow.fields.lastRunStatus') }}
            </dt>
            <dd class="mt-1">
              <StatusPill
                :label="labelForRunStatus(workflow.latestRunStatus)"
                :tone="toneForRunStatus(workflow.latestRunStatus)"
              />
            </dd>
          </div>
          <div class="rounded-2xl bg-slate-50 px-4 py-3">
            <dt class="text-xs uppercase tracking-wide text-slate-400">
              {{ t('plugin.workflowOrchestration.tenant.workflow.fields.pendingApprovals') }}
            </dt>
            <dd class="mt-1 font-medium text-slate-900">
              {{ formatNumber(workflow.pendingApprovals ?? 0) }}
            </dd>
          </div>
          <div class="rounded-2xl bg-slate-50 px-4 py-3">
            <dt class="text-xs uppercase tracking-wide text-slate-400">
              {{ t('plugin.workflowOrchestration.tenant.workflow.fields.successRate7d') }}
            </dt>
            <dd class="mt-1 font-medium text-slate-900">
              {{ formatPercent(workflow.successRate7d) }}
            </dd>
          </div>
        </dl>

        <div class="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <p class="text-xs uppercase tracking-wide text-slate-400">
            {{ t('plugin.workflowOrchestration.tenant.workflow.fields.lastRunAt') }}
          </p>
          <p class="mt-1 font-medium text-slate-900">
            {{ formatRelativeTime(workflow.lastRunAt || workflow.updatedAt) }}
          </p>
        </div>

        <div class="mt-auto flex flex-wrap items-center gap-3">
          <button
            class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
            @click="openEditor(workflow.id)"
          >
            {{ t('plugin.workflowOrchestration.tenant.workflow.actions.openEditor') }}
          </button>
          <button
            class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="workflow.canExecute === false || actionLoadingId === workflow.id"
            @click="executeWorkflow(workflow)"
          >
            {{
              actionLoadingId === workflow.id
                ? t('plugin.workflowOrchestration.tenant.common.messages.processing')
                : t('plugin.workflowOrchestration.tenant.workflow.actions.run')
            }}
          </button>
        </div>
      </article>
    </section>

    <EmptyState
      v-else
      :description="t('plugin.workflowOrchestration.tenant.workflow.empty.description')"
      :title="t('plugin.workflowOrchestration.tenant.workflow.empty.title')"
    >
      <button
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        @click="createWorkflow"
      >
        {{ t('plugin.workflowOrchestration.tenant.workflow.actions.create') }}
      </button>
    </EmptyState>

    <section
      v-if="!loading && totalPages > 1"
      class="flex items-center justify-between rounded-3xl border border-white/70 bg-white/90 px-5 py-4 shadow-sm"
    >
      <p class="text-sm text-slate-500">
        {{
          t('plugin.workflowOrchestration.tenant.common.pagination.summary', {
            page,
            total,
            totalPages,
          })
        }}
      </p>
      <div class="flex items-center gap-3">
        <button
          class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="page <= 1"
          @click="
            page -= 1;
            void loadWorkflows();
          "
        >
          {{ t('plugin.workflowOrchestration.tenant.common.actions.previousPage') }}
        </button>
        <button
          class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="page >= totalPages"
          @click="
            page += 1;
            void loadWorkflows();
          "
        >
          {{ t('plugin.workflowOrchestration.tenant.common.actions.nextPage') }}
        </button>
      </div>
    </section>
  </ConsoleShell>
</template>
