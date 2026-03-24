<script lang="ts" setup>
import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import {
  createTenantWorkflowApi,
  getTenantBuilderCapabilitiesApi,
  getTenantWorkflowDetailApi,
  publishTenantWorkflowApi,
  updateTenantWorkflowApi,
} from '../../../api/tenant';
import type {
  TenantBuilderCapability,
  TenantWorkflowDetail,
  TenantWorkflowUpsertPayload,
} from '../../../types/tenant';
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantWorkflowEditor',
});

const route = useRoute();
const {
  formatDateTime,
  labelForCapability,
  labelForBuilderMode,
  navigateTo,
  t,
} = useTenantOrchestration();

const loading = ref(true);
const saving = ref(false);
const errorMessage = ref('');
const workflow = ref<TenantWorkflowDetail | null>(null);
const capabilities = ref<TenantBuilderCapability[]>([]);
const form = ref<TenantWorkflowUpsertPayload>({
  description: '',
  name: '',
});

const isCreateMode = computed(() => {
  const raw = Array.isArray(route.params.id)
    ? route.params.id[0]
    : route.params.id;
  return raw === 'new' || raw === undefined;
});

const workflowId = computed(() => {
  if (isCreateMode.value) {
    return 0;
  }
  const raw = Array.isArray(route.params.id)
    ? route.params.id[0]
    : route.params.id;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
});

const lockedBoundaryCodes = [
  'code_nodes',
  'connector_management',
  'platform_policy_changes',
];

const canvasNodes = computed(() => workflow.value?.nodes ?? []);

async function loadEditor(): Promise<void> {
  loading.value = true;
  errorMessage.value = '';

  try {
    const capabilityPayload = await getTenantBuilderCapabilitiesApi();
    capabilities.value = capabilityPayload;

    if (isCreateMode.value) {
      workflow.value = null;
      form.value = {
        description: '',
        name: '',
      };
      return;
    }

    if (!workflowId.value) {
      errorMessage.value = t('plugin.workflow-orchestration.tenant.common.messages.invalidRoute');
      return;
    }

    const detail = await getTenantWorkflowDetailApi(workflowId.value);
    workflow.value = detail;
    form.value = {
      description: detail.description ?? '',
      name: detail.name ?? '',
    };
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.loadFailed');
  } finally {
    loading.value = false;
  }
}

async function saveWorkflow(): Promise<void> {
  if (!form.value.name.trim()) {
    errorMessage.value = t('plugin.workflow-orchestration.tenant.workflow.validation.nameRequired');
    return;
  }

  saving.value = true;
  errorMessage.value = '';

  try {
    if (isCreateMode.value) {
      const created = await createTenantWorkflowApi({
        description: form.value.description?.trim(),
        name: form.value.name.trim(),
      });
      workflow.value = created;
      navigateTo(`workflows/${created.id}/editor`);
      return;
    }

    if (!workflowId.value) {
      return;
    }

    workflow.value = await updateTenantWorkflowApi(workflowId.value, {
      description: form.value.description?.trim(),
      name: form.value.name.trim(),
    });
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
  } finally {
    saving.value = false;
  }
}

async function publishWorkflow(): Promise<void> {
  if (!workflow.value?.id) {
    return;
  }

  saving.value = true;
  try {
    workflow.value = await publishTenantWorkflowApi(workflow.value.id);
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
  } finally {
    saving.value = false;
  }
}

watch(
  () => route.params.id,
  () => {
    void loadEditor();
  },
  {
    immediate: true,
  },
);
</script>

<template>
  <ConsoleShell
    :description="t('plugin.workflow-orchestration.tenant.editor.description')"
    :eyebrow="t('plugin.workflow-orchestration.tenant.editor.eyebrow')"
    :title="
      isCreateMode
        ? t('plugin.workflow-orchestration.tenant.editor.createTitle')
        : workflow?.name || t('plugin.workflow-orchestration.tenant.workflow.untitled')
    "
  >
    <template #actions>
      <button
        v-if="!isCreateMode && workflow?.id"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        @click="navigateTo(`workflows/${workflow.id}`)"
      >
        {{ t('plugin.workflow-orchestration.tenant.common.actions.openDetail') }}
      </button>
      <button
        v-if="!isCreateMode && workflow?.id"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        :disabled="saving"
        @click="publishWorkflow"
      >
        {{ t('plugin.workflow-orchestration.tenant.workflow.actions.publish') }}
      </button>
      <button
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="saving"
        @click="saveWorkflow"
      >
        {{
          saving
            ? t('plugin.workflow-orchestration.tenant.common.messages.processing')
            : t('plugin.workflow-orchestration.tenant.editor.actions.save')
        }}
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
        <div class="h-5 w-40 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 h-56 animate-pulse rounded-3xl bg-slate-100" />
      </div>
      <div class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
        <div class="h-5 w-48 animate-pulse rounded-full bg-slate-200" />
        <div class="mt-4 space-y-3">
          <div class="h-20 animate-pulse rounded-2xl bg-slate-100" />
          <div class="h-20 animate-pulse rounded-2xl bg-slate-100" />
        </div>
      </div>
    </section>

    <template v-else>
      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div class="flex items-start justify-between gap-4">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.editor.sections.basicInfo') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflow-orchestration.tenant.editor.sections.basicInfoHint') }}
              </p>
            </div>
            <StatusPill
              v-if="workflow?.builderMode"
              :label="labelForBuilderMode(workflow.builderMode)"
              tone="info"
            />
          </div>

          <div class="mt-5 grid gap-4">
            <label class="space-y-2 text-sm text-slate-600">
              <span>{{ t('plugin.workflow-orchestration.tenant.workflow.fields.name') }}</span>
              <input
                v-model="form.name"
                class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
                :placeholder="t('plugin.workflow-orchestration.tenant.workflow.placeholders.name')"
              />
            </label>

            <label class="space-y-2 text-sm text-slate-600">
              <span>{{ t('plugin.workflow-orchestration.tenant.workflow.fields.description') }}</span>
              <textarea
                v-model="form.description"
                class="min-h-32 w-full rounded-3xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
                :placeholder="t('plugin.workflow-orchestration.tenant.workflow.placeholders.description')"
              />
            </label>
          </div>

          <div class="mt-5 rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
            <h3 class="text-sm font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.editor.sections.versionInfo') }}
            </h3>
            <dl class="mt-4 grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
              <div>
                <dt class="text-xs uppercase tracking-wide text-slate-400">
                  {{ t('plugin.workflow-orchestration.tenant.workflow.fields.version') }}
                </dt>
                <dd class="mt-1 font-medium text-slate-900">
                  {{ workflow?.currentVersion || t('plugin.workflow-orchestration.tenant.common.placeholders.empty') }}
                </dd>
              </div>
              <div>
                <dt class="text-xs uppercase tracking-wide text-slate-400">
                  {{ t('plugin.workflow-orchestration.tenant.workflow.fields.updatedAt') }}
                </dt>
                <dd class="mt-1 font-medium text-slate-900">
                  {{ formatDateTime(workflow?.updatedAt) }}
                </dd>
              </div>
            </dl>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.editor.sections.capabilities') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.editor.sections.capabilitiesHint') }}
            </p>
          </div>

          <div class="mt-5 grid gap-3">
            <div
              v-for="capability in capabilities"
              :key="capability.code"
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="space-y-1">
                  <p class="text-sm font-semibold text-slate-900">
                    {{ capability.label || labelForCapability(capability.code) }}
                  </p>
                  <p class="text-sm leading-6 text-slate-600">
                    {{
                      capability.description ||
                        capability.reason ||
                        t('plugin.workflow-orchestration.tenant.editor.empty.capabilityDescription')
                    }}
                  </p>
                </div>
                <StatusPill
                  :label="t(`plugin.workflow-orchestration.tenant.capability.state.${capability.enabled ? 'enabled' : 'disabled'}`)"
                  :tone="capability.enabled ? 'success' : 'neutral'"
                />
              </div>
            </div>
          </div>

          <div class="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4">
            <p class="text-sm font-semibold text-amber-900">
              {{ t('plugin.workflow-orchestration.tenant.editor.sections.boundaryTitle') }}
            </p>
            <ul class="mt-3 space-y-2 text-sm text-amber-800">
              <li
                v-for="code in lockedBoundaryCodes"
                :key="code"
              >
                {{ t(`plugin.workflow-orchestration.tenant.capability.locked.${code}`) }}
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
                {{ t('plugin.workflow-orchestration.tenant.editor.sections.canvasPreview') }}
              </h2>
              <p class="mt-1 text-sm text-slate-500">
                {{ t('plugin.workflow-orchestration.tenant.editor.sections.canvasPreviewHint') }}
              </p>
            </div>
          </div>

          <div
            v-if="canvasNodes.length > 0"
            class="mt-5 grid gap-3"
          >
            <div
              v-for="node in canvasNodes"
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
                  :label="node.readonly ? t('plugin.workflow-orchestration.tenant.editor.flags.platformManaged') : t('plugin.workflow-orchestration.tenant.editor.flags.tenantEditable')"
                  :tone="node.readonly ? 'warning' : 'success'"
                />
              </div>
            </div>
          </div>
          <EmptyState
            v-else
            :description="t('plugin.workflow-orchestration.tenant.editor.empty.canvasDescription')"
            :title="t('plugin.workflow-orchestration.tenant.editor.empty.canvasTitle')"
          />
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.editor.sections.designRules') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.editor.sections.designRulesHint') }}
            </p>
          </div>

          <div class="mt-5 space-y-3">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <h3 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.editor.cards.operatorScope') }}
              </h3>
              <p class="mt-2 text-sm leading-6 text-slate-600">
                {{ t('plugin.workflow-orchestration.tenant.editor.cardBody.operatorScope') }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <h3 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.editor.cards.reviewLane') }}
              </h3>
              <p class="mt-2 text-sm leading-6 text-slate-600">
                {{ t('plugin.workflow-orchestration.tenant.editor.cardBody.reviewLane') }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <h3 class="text-sm font-semibold text-slate-900">
                {{ t('plugin.workflow-orchestration.tenant.editor.cards.integrationBoundary') }}
              </h3>
              <p class="mt-2 text-sm leading-6 text-slate-600">
                {{ t('plugin.workflow-orchestration.tenant.editor.cardBody.integrationBoundary') }}
              </p>
            </div>
          </div>
        </article>
      </section>

      <section
        v-if="workflow && workflow.relatedRuns && workflow.relatedRuns.length > 0"
        class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm"
      >
        <div class="flex items-center justify-between gap-3">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.editor.sections.recentRuns') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.editor.sections.recentRunsHint') }}
            </p>
          </div>
          <button
            class="text-sm font-medium text-sky-700 transition hover:text-sky-800"
            @click="navigateTo('runs')"
          >
            {{ t('plugin.workflow-orchestration.tenant.common.actions.openRuns') }}
          </button>
        </div>

        <div class="mt-5 grid gap-3 lg:grid-cols-3">
          <button
            v-for="run in workflow.relatedRuns.slice(0, 3)"
            :key="run.id"
            class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-left transition hover:border-sky-200 hover:bg-sky-50/60"
            @click="navigateTo(`runs/${run.id}`)"
          >
            <p class="text-sm font-semibold text-slate-900">
              {{ run.name || t('plugin.workflow-orchestration.tenant.run.untitled') }}
            </p>
            <p class="mt-1 text-xs text-slate-500">
              {{ formatDateTime(run.updatedAt) }}
            </p>
          </button>
        </div>
      </section>
    </template>
  </ConsoleShell>
</template>
