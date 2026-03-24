<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';

import {
  listTenantRunsApi,
  pauseTenantRunApi,
  resumeTenantRunApi,
  retryTenantRunApi,
  terminateTenantRunApi,
} from '../../../api/tenant';
import type { TenantRunSummary } from '../../../types/tenant';
import {
  TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  buildPrompt,
  openWorkflowAIPanel,
  useWorkflowPageAI,
} from '../../../shared/ai';
import {
  TENANT_RUN_ACTION_ACCESS_CODES,
  TENANT_RUN_LIST_PAGE_ACCESS_CODES,
  WORKFLOW_ACCESS_CODES,
} from '../../../shared/access';
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantRunList',
});

const TENANT_RUN_LIST_PAGE_KEY = 'tenant.workflow_orchestration.runs';

const {
  canRunAction,
  formatNumber,
  formatRelativeTime,
  hasAccess,
  hasAnyAccess,
  labelForRisk,
  labelForRunStatus,
  navigateTo,
  t,
  toneForRisk,
  toneForRunStatus,
} = useTenantOrchestration();
const permissionDeniedMessage = t(
  'plugin.workflow-orchestration.tenant.common.messages.permissionDenied',
);
const canAccessRunListPage = hasAnyAccess(TENANT_RUN_LIST_PAGE_ACCESS_CODES);
const canOpenWorkflowCenter = hasAccess(
  WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_LIST,
);
const canOpenArtifacts = hasAccess(
  WORKFLOW_ACCESS_CODES.ARTIFACT_CENTER_LIST,
);
const canOpenRunDetail = hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_VIEW);

function hasRunActionAccess(
  action: keyof typeof TENANT_RUN_ACTION_ACCESS_CODES,
): boolean {
  return hasAccess(TENANT_RUN_ACTION_ACCESS_CODES[action]);
}

const loading = ref(true);
const errorMessage = ref('');
const actionLoadingId = ref<null | number>(null);
const runs = ref<TenantRunSummary[]>([]);
const keyword = ref('');
const selectedStatus = ref('');
const page = ref(1);
const size = ref(12);
const total = ref(0);

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(total.value / size.value));
});

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
    pageKey: TENANT_RUN_LIST_PAGE_KEY,
  });
}

const statusOptions = [
  'pending',
  'queued',
  'validating',
  'planning',
  'running',
  'waiting_human',
  'waiting_approval',
  'waiting_input',
  'paused',
  'recovering',
  'compensating',
  'succeeded',
  'completed',
  'partially_completed',
  'failed',
  'cancelled',
];

async function loadRuns(): Promise<void> {
  if (!canAccessRunListPage) {
    loading.value = false;
    errorMessage.value = permissionDeniedMessage;
    runs.value = [];
    total.value = 0;
    return;
  }

  loading.value = true;
  errorMessage.value = '';

  try {
    const result = await listTenantRunsApi({
      keyword: keyword.value || undefined,
      page: page.value,
      size: size.value,
      statuses: selectedStatus.value ? [selectedStatus.value] : undefined,
    });
    runs.value = result.items;
    total.value = result.total;
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.loadFailed');
  } finally {
    loading.value = false;
  }
}

function applyFilters(): void {
  page.value = 1;
  void loadRuns();
}

function resetFilters(): void {
  keyword.value = '';
  selectedStatus.value = '';
  page.value = 1;
  void loadRuns();
}

async function handleAction(
  action: 'pause' | 'resume' | 'retry' | 'terminate',
  run: TenantRunSummary,
): Promise<void> {
  if (!hasRunActionAccess(action)) {
    errorMessage.value = permissionDeniedMessage;
    return;
  }

  if (!run.id) {
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

  actionLoadingId.value = run.id;
  try {
    if (action === 'pause') {
      await pauseTenantRunApi(run.id);
    }
    if (action === 'resume') {
      await resumeTenantRunApi(run.id);
    }
    if (action === 'retry') {
      await retryTenantRunApi(run.id);
    }
    if (action === 'terminate') {
      await terminateTenantRunApi(run.id);
    }
    await loadRuns();
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
  } finally {
    actionLoadingId.value = null;
  }
}

onMounted(() => {
  void loadRuns();
});

useWorkflowPageAI({
  conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  pageKey: TENANT_RUN_LIST_PAGE_KEY,
  buildContext: () => ({
    entityDescription: t('plugin.workflow-orchestration.tenant.run.ai.pageDescription'),
    entityTitle: t('plugin.workflow-orchestration.tenant.run.listTitle'),
    entityType: 'workflow_orchestration_tenant_run_list',
    pageData: {
      active_status_filter: selectedStatus.value || null,
      keyword: keyword.value,
      total_items: total.value,
      visible_runs: runs.value.slice(0, 6).map((run) => ({
        id: run.id,
        name: run.name,
        status: run.status ?? null,
        workflow_name: run.workflowName ?? null,
      })),
    },
    pageTitle: t('plugin.workflow-orchestration.tenant.run.listTitle'),
  }),
  operations: [
    {
      name: 'open_tenant_workflow_center',
      label: t('plugin.workflow-orchestration.tenant.run.ai.operations.openWorkflows.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.run.ai.operations.openWorkflows.description',
      ),
      readonly: true,
      handler: async () => {
        if (!canOpenWorkflowCenter) {
          return {
            success: false,
            message: permissionDeniedMessage,
          };
        }
        navigateTo('workflows');
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.run.ai.operations.openWorkflows.success',
          ),
        };
      },
    },
    {
      name: 'open_tenant_artifact_center',
      label: t('plugin.workflow-orchestration.tenant.run.ai.operations.openArtifacts.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.run.ai.operations.openArtifacts.description',
      ),
      readonly: true,
      handler: async () => {
        if (!canOpenArtifacts) {
          return {
            success: false,
            message: permissionDeniedMessage,
          };
        }
        navigateTo('artifacts');
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.run.ai.operations.openArtifacts.success',
          ),
        };
      },
    },
    {
      name: 'open_tenant_run_ai_assistant',
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
        openAIPlanner(typeof params.idea === 'string' ? params.idea : undefined);
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.run.ai.operations.openAI.success',
          ),
        };
      },
    },
    {
      name: 'refresh_tenant_run_center',
      label: t('plugin.workflow-orchestration.tenant.run.ai.operations.refresh.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.run.ai.operations.refresh.description',
      ),
      readonly: true,
      handler: async () => {
        await loadRuns();
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
</script>

<template>
  <ConsoleShell
    :description="t('plugin.workflow-orchestration.tenant.run.listDescription')"
    :eyebrow="t('plugin.workflow-orchestration.tenant.run.eyebrow')"
    :title="t('plugin.workflow-orchestration.tenant.run.listTitle')"
  >
    <template #actions>
      <button
        v-if="canAccessRunListPage && canOpenWorkflowCenter"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        @click="navigateTo('workflows')"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.openWorkflows') }}
      </button>
      <button
        v-if="canAccessRunListPage"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        @click="openAIPlanner()"
      >
        {{ t('plugin.workflow-orchestration.tenant.run.actions.askAI') }}
      </button>
      <button
        v-if="canAccessRunListPage && canOpenArtifacts"
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        @click="navigateTo('artifacts')"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.openArtifacts') }}
      </button>
    </template>

    <EmptyState
      v-if="!canAccessRunListPage"
      :title="permissionDeniedMessage"
    />
    <template v-else>
    <section class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.7fr)_auto]">
        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflow-orchestration.tenant.run.filters.keyword') }}</span>
          <input
            v-model="keyword"
            class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
            :placeholder="t('plugin.workflow-orchestration.tenant.run.placeholders.keyword')"
            @keyup.enter="applyFilters"
          />
        </label>

        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflow-orchestration.tenant.run.filters.status') }}</span>
          <select
            v-model="selectedStatus"
            class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
          >
            <option value="">
              {{ t('plugin.workflow-orchestration.tenant.common.filters.allStatus') }}
            </option>
            <option
              v-for="status in statusOptions"
              :key="status"
              :value="status"
            >
              {{ labelForRunStatus(status) }}
            </option>
          </select>
        </label>

        <div class="flex flex-wrap items-end gap-3">
          <button
            class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
            @click="applyFilters"
          >
            {{ t('plugin.workflow-orchestration.tenant.common.actions.applyFilters') }}
          </button>
          <button
            class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
            @click="resetFilters"
          >
            {{ t('plugin.workflow-orchestration.tenant.common.actions.resetFilters') }}
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

    <section v-if="loading" class="grid gap-4 lg:grid-cols-2">
      <div
        v-for="index in 4"
        :key="index"
        class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm"
      >
        <div class="h-5 w-48 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 h-28 animate-pulse rounded-3xl bg-slate-100" />
      </div>
    </section>

    <section
      v-else-if="runs.length > 0"
      class="grid gap-4 lg:grid-cols-2"
    >
      <article
        v-for="run in runs"
        :key="run.id"
        class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="space-y-2">
            <h2 class="text-lg font-semibold text-slate-900">
              {{ run.name || t('plugin.workflow-orchestration.tenant.run.untitled') }}
            </h2>
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
          </div>
          <button
            v-if="canOpenRunDetail"
            class="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="navigateTo(`runs/${run.id}`)"
          >
            {{ t('plugin.workflow-orchestration.tenant.common.actions.openDetail') }}
          </button>
        </div>

        <dl class="mt-5 grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
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
              {{ t('plugin.workflow-orchestration.tenant.run.fields.triggerSource') }}
            </dt>
            <dd class="mt-1 font-medium text-slate-900">
              {{ run.triggerSource || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
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
              {{ t('plugin.workflow-orchestration.tenant.run.fields.artifactCount') }}
            </dt>
            <dd class="mt-1 font-medium text-slate-900">
              {{ formatNumber(run.artifactCount ?? 0) }}
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

        <div class="mt-5 flex flex-wrap items-center gap-3">
          <button
            v-if="hasRunActionAccess('pause')"
            class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="actionLoadingId === run.id || !canRunAction(run, 'pause')"
            @click="handleAction('pause', run)"
          >
            {{ t('plugin.workflow-orchestration.tenant.run.actions.pause') }}
          </button>
          <button
            v-if="hasRunActionAccess('resume')"
            class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="actionLoadingId === run.id || !canRunAction(run, 'resume')"
            @click="handleAction('resume', run)"
          >
            {{ t('plugin.workflow-orchestration.tenant.run.actions.resume') }}
          </button>
          <button
            v-if="hasRunActionAccess('retry')"
            class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="actionLoadingId === run.id || !canRunAction(run, 'retry')"
            @click="handleAction('retry', run)"
          >
            {{
              actionLoadingId === run.id
                ? t('plugin.workflow-orchestration.tenant.common.messages.processing')
                : t('plugin.workflow-orchestration.tenant.run.actions.retry')
            }}
          </button>
          <button
            v-if="hasRunActionAccess('terminate')"
            class="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="actionLoadingId === run.id || !canRunAction(run, 'terminate')"
            @click="handleAction('terminate', run)"
          >
            {{ t('plugin.workflow-orchestration.tenant.run.actions.terminate') }}
          </button>
        </div>
      </article>
    </section>

    <EmptyState
      v-else
      :description="t('plugin.workflow-orchestration.tenant.run.empty.description')"
      :title="t('plugin.workflow-orchestration.tenant.run.empty.title')"
    >
      <button
        v-if="canOpenWorkflowCenter"
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        @click="navigateTo('workflows')"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.openWorkflows') }}
      </button>
      <button
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        @click="openAIPlanner()"
      >
        {{ t('plugin.workflow-orchestration.tenant.run.actions.askAI') }}
      </button>
    </EmptyState>

    <section
      v-if="!loading && totalPages > 1"
      class="flex items-center justify-between rounded-3xl border border-white/70 bg-white/90 px-5 py-4 shadow-sm"
    >
      <p class="text-sm text-slate-500">
        {{
          t('plugin.workflow-orchestration.tenant.common.pagination.summary', {
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
            void loadRuns();
          "
        >
          {{ t('plugin.workflow-orchestration.tenant.common.actions.previousPage') }}
        </button>
        <button
          class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="page >= totalPages"
          @click="
            page += 1;
            void loadRuns();
          "
        >
          {{ t('plugin.workflow-orchestration.tenant.common.actions.nextPage') }}
        </button>
      </div>
    </section>
    </template>
  </ConsoleShell>
</template>
