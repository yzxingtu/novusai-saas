<script lang="ts" setup>
import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import {
  downloadTenantArtifactApi,
  getTenantArtifactDetailApi,
  submitTenantArtifactFeedbackApi,
} from '../../../api/tenant';
import type { TenantArtifactDetail } from '../../../types/tenant';
import ConsoleShell from '../shared/ConsoleShell.vue';
import EmptyState from '../shared/EmptyState.vue';
import StatusPill from '../shared/StatusPill.vue';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantArtifactDetail',
});

const route = useRoute();
const {
  formatBytes,
  formatDateTime,
  formatRelativeTime,
  labelForArtifactStatus,
  labelForArtifactType,
  navigateTo,
  saveBlob,
  shared,
  t,
  toneForArtifactStatus,
} = useTenantOrchestration();

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

const downloadState = computed(() => {
  if (!artifact.value) {
    return {
      enabled: false,
      reason: t('plugin.workflowOrchestration.tenant.common.messages.downloadUnavailable'),
    };
  }

  const backendAllowsDownload = Array.isArray(artifact.value.availableActions)
    ? artifact.value.availableActions.includes('download')
    : artifact.value.canDownload !== false;
  const downloadAvailable = backendAllowsDownload && artifact.value.downloadAvailable !== false;

  if (!downloadAvailable) {
    return {
      enabled: false,
      reason: t('plugin.workflowOrchestration.tenant.common.messages.downloadUnavailable'),
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
    reason: t('plugin.workflowOrchestration.tenant.artifact.empty.downloadDisabled'),
  };
});

async function loadArtifact(): Promise<void> {
  if (!artifactId.value) {
    errorMessage.value = t('plugin.workflowOrchestration.tenant.common.messages.invalidRoute');
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
        : t('plugin.workflowOrchestration.tenant.common.messages.loadFailed');
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
        : t('plugin.workflowOrchestration.tenant.common.messages.actionFailed');
  } finally {
    downloading.value = false;
  }
}

async function submitFeedback(): Promise<void> {
  if (!artifact.value?.id || artifact.value.canFeedback === false) {
    return;
  }
  if (!feedbackComment.value.trim()) {
    errorMessage.value = t('plugin.workflowOrchestration.tenant.artifact.validation.commentRequired');
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
        : t('plugin.workflowOrchestration.tenant.common.messages.actionFailed');
  } finally {
    submittingFeedback.value = false;
  }
}

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
    :description="artifact?.previewText || t('plugin.workflowOrchestration.tenant.artifact.detailDescription')"
    :eyebrow="t('plugin.workflowOrchestration.tenant.artifact.eyebrow')"
    :title="artifact?.title || t('plugin.workflowOrchestration.tenant.artifact.untitled')"
  >
    <template #actions>
      <button
        v-if="artifact?.workflowId"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        @click="navigateTo(`workflows/${artifact.workflowId}`)"
      >
        {{ t('plugin.workflowOrchestration.tenant.common.actions.viewWorkflow') }}
      </button>
      <button
        v-if="artifact?.runId"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
        @click="navigateTo(`runs/${artifact.runId}`)"
      >
        {{ t('plugin.workflowOrchestration.tenant.common.actions.viewRun') }}
      </button>
      <button
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="downloading || !downloadState.enabled"
        @click="downloadArtifact"
      >
        {{
          downloading
            ? t('plugin.workflowOrchestration.tenant.common.messages.processing')
            : t('plugin.workflowOrchestration.tenant.common.actions.download')
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
                {{ t('plugin.workflowOrchestration.tenant.artifact.fields.workflowName') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.workflowName || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.artifact.fields.runId') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.runId ?? t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.artifact.fields.sourceVersion') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.sourceVersion || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.artifact.fields.sourceNodeName') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.sourceNodeName || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.artifact.fields.sizeBytes') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatBytes(artifact.sizeBytes) }}
              </dd>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.artifact.fields.updatedAt') }}
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
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.adoption') }}
            </h2>
            <p class="mt-2 text-sm leading-6 text-slate-600">
              {{ artifact.adoptionSummary || t('plugin.workflowOrchestration.tenant.artifact.empty.adoptionDescription') }}
            </p>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.preview') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.previewHint') }}
            </p>
          </div>

          <pre
            v-if="previewText"
            class="mt-5 max-h-[26rem] overflow-auto whitespace-pre-wrap rounded-3xl bg-slate-900 p-5 text-xs leading-6 text-slate-100"
          >{{ previewText }}</pre>
          <EmptyState
            v-else
            :description="t('plugin.workflowOrchestration.tenant.artifact.empty.previewDescription')"
            :title="t('plugin.workflowOrchestration.tenant.artifact.empty.previewTitle')"
          />
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.structuredData') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.structuredDataHint') }}
            </p>
          </div>

          <pre
            v-if="prettyJson"
            class="mt-5 max-h-[26rem] overflow-auto rounded-3xl bg-slate-900 p-5 text-xs leading-6 text-slate-100"
          >{{ prettyJson }}</pre>
          <EmptyState
            v-else
            :description="t('plugin.workflowOrchestration.tenant.artifact.empty.jsonDescription')"
            :title="t('plugin.workflowOrchestration.tenant.artifact.empty.jsonTitle')"
          />
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.traceability') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.traceabilityHint') }}
            </p>
          </div>

          <dl class="mt-5 grid gap-3 text-sm text-slate-600">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.artifact.fields.createdAt') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ formatDateTime(artifact.createdAt) }}
              </dd>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.artifact.fields.mimeType') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.mimeType || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.artifact.fields.downloadFilename') }}
              </dt>
              <dd class="mt-1 font-medium text-slate-900">
                {{ artifact.downloadFilename || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </dd>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <dt class="text-xs uppercase tracking-wide text-slate-400">
                {{ t('plugin.workflowOrchestration.tenant.artifact.fields.feedbackCount') }}
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
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.feedback') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.feedbackHint') }}
            </p>
          </div>

          <div class="mt-5 grid gap-4">
            <label class="space-y-2 text-sm text-slate-600">
              <span>{{ t('plugin.workflowOrchestration.tenant.artifact.fields.rating') }}</span>
              <select
                v-model="feedbackRating"
                class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
                :disabled="submittingFeedback || artifact.canFeedback === false"
              >
                <option :value="null">
                  {{ t('plugin.workflowOrchestration.tenant.artifact.placeholders.rating') }}
                </option>
                <option
                  v-for="rating in ratingOptions"
                  :key="rating"
                  :value="rating"
                >
                  {{ t('plugin.workflowOrchestration.tenant.artifact.ratingOption', { rating }) }}
                </option>
              </select>
            </label>

            <label class="space-y-2 text-sm text-slate-600">
              <span>{{ t('plugin.workflowOrchestration.tenant.artifact.fields.feedbackComment') }}</span>
              <textarea
                v-model="feedbackComment"
                class="min-h-36 w-full rounded-3xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
                :disabled="submittingFeedback || artifact.canFeedback === false"
                :placeholder="t('plugin.workflowOrchestration.tenant.artifact.placeholders.feedbackComment')"
              />
            </label>
          </div>

          <p
            v-if="artifact.canFeedback === false"
            class="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
          >
            {{ t('plugin.workflowOrchestration.tenant.artifact.empty.feedbackDisabled') }}
          </p>

          <div class="mt-5">
            <button
              class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="submittingFeedback || artifact.canFeedback === false"
              @click="submitFeedback"
            >
              {{
                submittingFeedback
                  ? t('plugin.workflowOrchestration.tenant.common.messages.processing')
                  : t('plugin.workflowOrchestration.tenant.common.actions.submitFeedback')
              }}
            </button>
          </div>
        </article>

        <article class="rounded-3xl border border-white/70 bg-white/90 p-6 shadow-sm">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.feedbackHistory') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('plugin.workflowOrchestration.tenant.artifact.sections.feedbackHistoryHint') }}
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
                    {{ item.createdBy || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
                  </p>
                  <p class="text-xs text-slate-500">
                    {{ formatDateTime(item.createdAt) }}
                  </p>
                </div>
                <StatusPill
                  :label="
                    item.rating != null
                      ? t('plugin.workflowOrchestration.tenant.artifact.ratingBadge', { rating: item.rating })
                      : t('plugin.workflowOrchestration.tenant.artifact.noRating')
                  "
                  :tone="item.rating != null && item.rating >= 4 ? 'success' : item.rating != null && item.rating <= 2 ? 'warning' : 'neutral'"
                />
              </div>
              <p class="mt-3 text-sm leading-6 text-slate-600">
                {{ item.comment || t('plugin.workflowOrchestration.tenant.common.placeholders.empty') }}
              </p>
            </div>
          </div>
          <EmptyState
            v-else
            :description="t('plugin.workflowOrchestration.tenant.artifact.empty.feedbackDescription')"
            :title="t('plugin.workflowOrchestration.tenant.artifact.empty.feedbackTitle')"
          />
        </article>
      </section>
    </template>

    <EmptyState
      v-else
      :description="t('plugin.workflowOrchestration.tenant.artifact.empty.detailDescription')"
      :title="t('plugin.workflowOrchestration.tenant.artifact.empty.detailTitle')"
    />
  </ConsoleShell>
</template>
