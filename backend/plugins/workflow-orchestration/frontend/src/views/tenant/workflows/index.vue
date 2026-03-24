<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';

import {
  executeTenantWorkflowApi,
  listTenantWorkflowsApi,
} from '../../../api/tenant';
import type { TenantWorkflowSummary } from '../../../types/tenant';
import {
  TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  buildPrompt,
  openWorkflowAIPanel,
  useWorkflowPageAI,
} from '../../../shared/ai';
import {
  TENANT_WORKFLOW_CREATE_PAGE_ACCESS_CODES,
  TENANT_WORKFLOW_LIST_PAGE_ACCESS_CODES,
  WORKFLOW_ACCESS_CODES,
} from '../../../shared/access';
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantWorkflowList',
});

const TENANT_WORKFLOW_LIST_PAGE_KEY = 'tenant.workflow_orchestration.workflows';

const {
  formatNumber,
  formatPercent,
  formatRelativeTime,
  hasAccess,
  hasAnyAccess,
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
const permissionDeniedMessage = t(
  'plugin.workflow-orchestration.tenant.common.messages.permissionDenied',
);
const canAccessWorkflowListPage = hasAnyAccess(
  TENANT_WORKFLOW_LIST_PAGE_ACCESS_CODES,
);
const canOpenCreateGuide = hasAnyAccess(TENANT_WORKFLOW_CREATE_PAGE_ACCESS_CODES);
const canOpenRuns = hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_LIST);
const canOpenWorkflowDetail = hasAccess(
  WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_VIEW,
);
const canOpenEditor = hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_EDIT);
const canRunWorkflow = hasAccess(WORKFLOW_ACCESS_CODES.WORKFLOW_RUN_EXECUTE);

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
  if (!canAccessWorkflowListPage) {
    loading.value = false;
    errorMessage.value = permissionDeniedMessage;
    workflows.value = [];
    total.value = 0;
    return;
  }

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
        : t('plugin.workflow-orchestration.tenant.common.messages.loadFailed');
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
  if (!canRunWorkflow) {
    errorMessage.value = permissionDeniedMessage;
    return;
  }

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
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
  } finally {
    actionLoadingId.value = null;
  }
}

function openEditor(workflowId: number): void {
  if (!canOpenEditor) {
    errorMessage.value = permissionDeniedMessage;
    return;
  }
  navigateTo(`workflows/${workflowId}/editor`);
}

function openDetail(workflowId: number): void {
  navigateTo(`workflows/${workflowId}`);
}

function createWorkflow(): void {
  if (!canOpenCreateGuide) {
    errorMessage.value = permissionDeniedMessage;
    return;
  }
  navigateTo('workflows/new');
}

function openAIPlanner(seed?: string): void {
  openWorkflowAIPanel({
    conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
    message: buildPrompt([
      t('plugin.workflow-orchestration.tenant.workflow.ai.systemLead'),
      seed?.trim()
        ? t('plugin.workflow-orchestration.tenant.workflow.ai.userIdea', {
            idea: seed.trim(),
          })
        : t('plugin.workflow-orchestration.tenant.workflow.ai.emptyIdea'),
      t('plugin.workflow-orchestration.tenant.workflow.ai.outputContract'),
    ]),
    pageKey: TENANT_WORKFLOW_LIST_PAGE_KEY,
  });
}

onMounted(() => {
  void loadWorkflows();
});

useWorkflowPageAI({
  conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  pageKey: TENANT_WORKFLOW_LIST_PAGE_KEY,
  buildContext: () => ({
    entityDescription: t('plugin.workflow-orchestration.tenant.workflow.ai.pageDescription'),
    entityTitle: t('plugin.workflow-orchestration.tenant.workflow.listTitle'),
    entityType: 'workflow_orchestration_tenant_workflow_list',
    pageData: {
      active_builder_mode_filter: selectedBuilderMode.value || null,
      active_status_filter: selectedStatus.value || null,
      keyword: keyword.value,
      total_items: total.value,
      visible_workflow_names: workflows.value
        .slice(0, 6)
        .map((workflow) => workflow.name)
        .filter(Boolean),
    },
    pageTitle: t('plugin.workflow-orchestration.tenant.workflow.listTitle'),
  }),
  operations: [
    {
      name: 'open_workflow_create_guide',
      label: t('plugin.workflow-orchestration.tenant.workflow.ai.operations.openCreateGuide.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.workflow.ai.operations.openCreateGuide.description',
      ),
      readonly: true,
      handler: async () => {
        if (!canOpenCreateGuide) {
          return {
            success: false,
            message: permissionDeniedMessage,
          };
        }
        createWorkflow();
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.workflow.ai.operations.openCreateGuide.success',
          ),
        };
      },
    },
    {
      name: 'open_workflow_ai_planner',
      label: t('plugin.workflow-orchestration.tenant.workflow.ai.operations.openAI.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.workflow.ai.operations.openAI.description',
      ),
      readonly: true,
      params: {
        idea: {
          description: t(
            'plugin.workflow-orchestration.tenant.workflow.ai.operations.openAI.ideaDescription',
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
            'plugin.workflow-orchestration.tenant.workflow.ai.operations.openAI.success',
          ),
        };
      },
    },
    {
      name: 'refresh_workflow_list',
      label: t('plugin.workflow-orchestration.tenant.workflow.ai.operations.refresh.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.workflow.ai.operations.refresh.description',
      ),
      readonly: true,
      handler: async () => {
        await loadWorkflows();
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
</script>

<template>
  <ConsoleShell
    :description="t('plugin.workflow-orchestration.tenant.workflow.listDescription')"
    :eyebrow="t('plugin.workflow-orchestration.tenant.workflow.eyebrow')"
    :title="t('plugin.workflow-orchestration.tenant.workflow.listTitle')"
  >
    <template #actions>
      <button
        v-if="canAccessWorkflowListPage && canOpenRuns"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        @click="navigateTo('runs')"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.openRuns') }}
      </button>
      <button
        v-if="canAccessWorkflowListPage"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        @click="openAIPlanner()"
      >
        {{ t('plugin.workflow-orchestration.tenant.workflow.actions.askAI') }}
      </button>
      <button
        v-if="canAccessWorkflowListPage && canOpenCreateGuide"
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        @click="createWorkflow"
      >
        {{ t('plugin.workflow-orchestration.tenant.workflow.actions.openCreateGuide') }}
      </button>
    </template>

    <EmptyState
      v-if="!canAccessWorkflowListPage"
      :title="permissionDeniedMessage"
    />
    <template v-else>
    <section class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_repeat(3,minmax(0,0.5fr))]">
        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflow-orchestration.tenant.workflow.filters.keyword') }}</span>
          <input
            v-model="keyword"
            class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
            :placeholder="t('plugin.workflow-orchestration.tenant.workflow.placeholders.keyword')"
            @keyup.enter="applyFilters"
          />
        </label>

        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflow-orchestration.tenant.workflow.filters.status') }}</span>
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
              {{ labelForWorkflowStatus(status) }}
            </option>
          </select>
        </label>

        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflow-orchestration.tenant.workflow.filters.builderMode') }}</span>
          <select
            v-model="selectedBuilderMode"
            class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
          >
            <option value="">
              {{ t('plugin.workflow-orchestration.tenant.common.filters.allBuilderModes') }}
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
              {{ workflow.name || t('plugin.workflow-orchestration.tenant.workflow.untitled') }}
            </h2>
            <p
              v-if="workflow.description"
              class="line-clamp-2 text-sm leading-6 text-slate-600"
            >
              {{ workflow.description }}
            </p>
          </div>
          <button
            v-if="canOpenWorkflowDetail"
            class="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="openDetail(workflow.id)"
          >
            {{ t('plugin.workflow-orchestration.tenant.common.actions.openDetail') }}
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
              {{ t('plugin.workflow-orchestration.tenant.workflow.fields.version') }}
            </dt>
            <dd class="mt-1 font-medium text-slate-900">
              {{ workflow.currentVersion || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
            </dd>
          </div>
          <div class="rounded-2xl bg-slate-50 px-4 py-3">
            <dt class="text-xs uppercase tracking-wide text-slate-400">
              {{ t('plugin.workflow-orchestration.tenant.workflow.fields.lastRunStatus') }}
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
              {{ t('plugin.workflow-orchestration.tenant.workflow.fields.pendingApprovals') }}
            </dt>
            <dd class="mt-1 font-medium text-slate-900">
              {{ formatNumber(workflow.pendingApprovals ?? 0) }}
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

        <div class="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <p class="text-xs uppercase tracking-wide text-slate-400">
            {{ t('plugin.workflow-orchestration.tenant.workflow.fields.lastRunAt') }}
          </p>
          <p class="mt-1 font-medium text-slate-900">
            {{ formatRelativeTime(workflow.lastRunAt || workflow.updatedAt) }}
          </p>
        </div>

        <div class="mt-auto flex flex-wrap items-center gap-3">
          <button
            v-if="canOpenEditor && workflow.canEdit !== false"
            class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
            @click="openEditor(workflow.id)"
          >
            {{ t('plugin.workflow-orchestration.tenant.workflow.actions.openEditor') }}
          </button>
          <button
            v-if="canRunWorkflow"
            class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="workflow.canExecute === false || actionLoadingId === workflow.id"
            @click="executeWorkflow(workflow)"
          >
            {{
              actionLoadingId === workflow.id
                ? t('plugin.workflow-orchestration.tenant.common.messages.processing')
                : t('plugin.workflow-orchestration.tenant.workflow.actions.run')
              }}
          </button>
        </div>
        <p
          v-if="workflow.canExecute === false"
          class="text-xs leading-5 text-slate-500"
        >
          {{ t('plugin.workflow-orchestration.tenant.workflow.hints.publishBeforeRun') }}
        </p>
      </article>
    </section>

    <EmptyState
      v-else
      :description="t('plugin.workflow-orchestration.tenant.workflow.empty.description')"
      :title="t('plugin.workflow-orchestration.tenant.workflow.empty.title')"
    >
      <button
        v-if="canOpenCreateGuide"
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        @click="createWorkflow"
      >
        {{ t('plugin.workflow-orchestration.tenant.workflow.actions.openCreateGuide') }}
      </button>
      <button
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        @click="openAIPlanner()"
      >
        {{ t('plugin.workflow-orchestration.tenant.workflow.actions.askAI') }}
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
            void loadWorkflows();
          "
        >
          {{ t('plugin.workflow-orchestration.tenant.common.actions.previousPage') }}
        </button>
        <button
          class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="page >= totalPages"
          @click="
            page += 1;
            void loadWorkflows();
          "
        >
          {{ t('plugin.workflow-orchestration.tenant.common.actions.nextPage') }}
        </button>
      </div>
    </section>
    </template>
  </ConsoleShell>
</template>
