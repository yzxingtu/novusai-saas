<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';

import { listTenantArtifactsApi } from '../../../api/tenant';
import type { TenantArtifactSummary } from '../../../types/tenant';
import {
  TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  buildPrompt,
  openWorkflowAIPanel,
  useWorkflowPageAI,
} from '../../../shared/ai';
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantArtifactList',
});

const TENANT_ARTIFACT_LIST_PAGE_KEY = 'tenant.workflow_orchestration.artifacts';

const {
  formatBytes,
  formatRelativeTime,
  labelForArtifactStatus,
  labelForArtifactType,
  navigateTo,
  t,
  toneForArtifactStatus,
} = useTenantOrchestration();

const loading = ref(true);
const errorMessage = ref('');
const artifacts = ref<TenantArtifactSummary[]>([]);
const keyword = ref('');
const selectedStatus = ref('');
const selectedType = ref('');
const page = ref(1);
const size = ref(12);
const total = ref(0);

const statusOptions = [
  'draft',
  'ready',
  'adopted',
  'rejected',
  'archived',
  'expired',
  'failed',
];

const typeOptions = [
  'draft',
  'report',
  'recommendation',
  'approval_packet',
  'evidence_bundle',
];

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(total.value / size.value));
});

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
    pageKey: TENANT_ARTIFACT_LIST_PAGE_KEY,
  });
}

async function loadArtifacts(): Promise<void> {
  loading.value = true;
  errorMessage.value = '';

  try {
    const result = await listTenantArtifactsApi({
      keyword: keyword.value || undefined,
      page: page.value,
      size: size.value,
      statuses: selectedStatus.value ? [selectedStatus.value] : undefined,
      types: selectedType.value ? [selectedType.value] : undefined,
    });
    artifacts.value = result.items;
    size.value = result.size || size.value;
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
  void loadArtifacts();
}

function resetFilters(): void {
  keyword.value = '';
  selectedStatus.value = '';
  selectedType.value = '';
  page.value = 1;
  void loadArtifacts();
}

onMounted(() => {
  void loadArtifacts();
});

useWorkflowPageAI({
  conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  pageKey: TENANT_ARTIFACT_LIST_PAGE_KEY,
  buildContext: () => ({
    entityDescription: t(
      'plugin.workflow-orchestration.tenant.artifact.ai.pageDescription',
    ),
    entityTitle: t('plugin.workflow-orchestration.tenant.artifact.listTitle'),
    entityType: 'workflow_orchestration_tenant_artifact_list',
    pageData: {
      active_status_filter: selectedStatus.value || null,
      active_type_filter: selectedType.value || null,
      keyword: keyword.value,
      total_items: total.value,
      visible_artifacts: artifacts.value.slice(0, 6).map((artifact) => ({
        id: artifact.id,
        title: artifact.title,
        status: artifact.status ?? null,
        type: artifact.type ?? null,
        workflow_name: artifact.workflowName ?? null,
      })),
    },
    pageTitle: t('plugin.workflow-orchestration.tenant.artifact.listTitle'),
  }),
  operations: [
    {
      name: 'open_tenant_run_center',
      label: t('plugin.workflow-orchestration.tenant.artifact.ai.operations.openRuns.label'),
      description: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.openRuns.description',
      ),
      readonly: true,
      handler: async () => {
        navigateTo('runs');
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.artifact.ai.operations.openRuns.success',
          ),
        };
      },
    },
    {
      name: 'open_tenant_workflow_center_from_artifacts',
      label: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.openWorkflows.label',
      ),
      description: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.openWorkflows.description',
      ),
      readonly: true,
      handler: async () => {
        navigateTo('workflows');
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.artifact.ai.operations.openWorkflows.success',
          ),
        };
      },
    },
    {
      name: 'open_tenant_artifact_ai_assistant',
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
        openAIPlanner(typeof params.idea === 'string' ? params.idea : undefined);
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.artifact.ai.operations.openAI.success',
          ),
        };
      },
    },
    {
      name: 'refresh_tenant_artifact_center',
      label: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.refresh.label',
      ),
      description: t(
        'plugin.workflow-orchestration.tenant.artifact.ai.operations.refresh.description',
      ),
      readonly: true,
      handler: async () => {
        await loadArtifacts();
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
</script>

<template>
  <ConsoleShell
    :description="t('plugin.workflow-orchestration.tenant.artifact.listDescription')"
    :eyebrow="t('plugin.workflow-orchestration.tenant.artifact.eyebrow')"
    :title="t('plugin.workflow-orchestration.tenant.artifact.listTitle')"
  >
    <template #actions>
      <button
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        @click="navigateTo('runs')"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.openRuns') }}
      </button>
      <button
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        @click="openAIPlanner()"
      >
        {{ t('plugin.workflow-orchestration.tenant.artifact.actions.askAI') }}
      </button>
      <button
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        @click="navigateTo('workflows')"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.openWorkflows') }}
      </button>
    </template>

    <section class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_repeat(3,minmax(0,0.5fr))]">
        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflow-orchestration.tenant.artifact.filters.keyword') }}</span>
          <input
            v-model="keyword"
            class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
            :placeholder="t('plugin.workflow-orchestration.tenant.artifact.placeholders.keyword')"
            @keyup.enter="applyFilters"
          />
        </label>

        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflow-orchestration.tenant.artifact.filters.status') }}</span>
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
              {{ labelForArtifactStatus(status) }}
            </option>
          </select>
        </label>

        <label class="space-y-2 text-sm text-slate-600">
          <span>{{ t('plugin.workflow-orchestration.tenant.artifact.filters.type') }}</span>
          <select
            v-model="selectedType"
            class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
          >
            <option value="">
              {{ t('plugin.workflow-orchestration.tenant.common.filters.allArtifactTypes') }}
            </option>
            <option
              v-for="type in typeOptions"
              :key="type"
              :value="type"
            >
              {{ labelForArtifactType(type) }}
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

    <section v-if="loading" class="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
      <div
        v-for="index in 6"
        :key="index"
        class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm"
      >
        <div class="h-5 w-40 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 h-24 animate-pulse rounded-3xl bg-slate-100" />
        <div class="mt-4 h-10 animate-pulse rounded-2xl bg-slate-100" />
      </div>
    </section>

    <section
      v-else-if="artifacts.length > 0"
      class="grid gap-4 lg:grid-cols-2 xl:grid-cols-3"
    >
      <article
        v-for="artifact in artifacts"
        :key="artifact.id"
        class="flex flex-col gap-4 rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="space-y-2">
            <h2 class="text-lg font-semibold text-slate-900">
              {{ artifact.title || t('plugin.workflow-orchestration.tenant.artifact.untitled') }}
            </h2>
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
          <button
            class="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="navigateTo(`artifacts/${artifact.id}`)"
          >
            {{ t('plugin.workflow-orchestration.tenant.common.actions.openDetail') }}
          </button>
        </div>

        <p
          v-if="artifact.previewText"
          class="line-clamp-3 text-sm leading-6 text-slate-600"
        >
          {{ artifact.previewText }}
        </p>
        <p
          v-else
          class="text-sm leading-6 text-slate-500"
        >
          {{ t('plugin.workflow-orchestration.tenant.artifact.empty.previewDescription') }}
        </p>

        <dl class="grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
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
              {{ t('plugin.workflow-orchestration.tenant.artifact.fields.sourceVersion') }}
            </dt>
            <dd class="mt-1 font-medium text-slate-900">
              {{ artifact.sourceVersion || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
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

        <div class="mt-auto flex flex-wrap items-center gap-3">
          <button
            v-if="artifact.workflowId"
            class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
            @click="navigateTo(`workflows/${artifact.workflowId}`)"
          >
            {{ t('plugin.workflow-orchestration.tenant.common.actions.viewWorkflow') }}
          </button>
          <button
            v-if="artifact.runId"
            class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
            @click="navigateTo(`runs/${artifact.runId}`)"
          >
            {{ t('plugin.workflow-orchestration.tenant.common.actions.viewRun') }}
          </button>
        </div>
      </article>
    </section>

    <EmptyState
      v-else
      :description="t('plugin.workflow-orchestration.tenant.artifact.empty.description')"
      :title="t('plugin.workflow-orchestration.tenant.artifact.empty.title')"
    >
      <button
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        @click="navigateTo('workflows')"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.openWorkflows') }}
      </button>
      <button
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        @click="navigateTo('runs')"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.openRuns') }}
      </button>
      <button
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        @click="openAIPlanner()"
      >
        {{ t('plugin.workflow-orchestration.tenant.artifact.actions.askAI') }}
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
            void loadArtifacts();
          "
        >
          {{ t('plugin.workflow-orchestration.tenant.common.actions.previousPage') }}
        </button>
        <button
          class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="page >= totalPages"
          @click="
            page += 1;
            void loadArtifacts();
          "
        >
          {{ t('plugin.workflow-orchestration.tenant.common.actions.nextPage') }}
        </button>
      </div>
    </section>
  </ConsoleShell>
</template>
