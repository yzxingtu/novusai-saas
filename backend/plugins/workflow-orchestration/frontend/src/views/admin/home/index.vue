<script lang="ts" setup>
import type { AdminOverviewResponse } from '../../../types/admin';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Empty, Input, Spin, Tag } from 'ant-design-vue';

import { getAdminOverviewApi } from '../../../api/admin';
import {
  ADMIN_WORKFLOW_AI_CONVERSATION_SCOPE,
  buildPrompt,
  openWorkflowAIPanel,
  useWorkflowPageAI,
} from '../../../shared/ai';
import {
  ADMIN_HOME_PAGE_ACCESS_CODES,
  WORKFLOW_ACCESS_CODES,
  hasAllPluginAccess,
  hasAnyPluginAccess,
  hasPluginAccess,
} from '../../../shared/access';
import { formatCompactNumber, formatDateTime } from '../shared/format';
import { ADMIN_I18N_PREFIX, buildAdminPath } from '../shared/constants';

import { getReleaseStatusColor, getReleaseStatusText } from '../releases/data';
import { getRunStatusColor, getRunStatusText } from '../runtime/data';
import {
  getTemplateStatusColor,
  getTemplateStatusText,
} from '../templates/data';
import { $t } from '@novus/plugin-shared';

defineOptions({ name: 'WorkflowOrchestrationAdminHome' });

const ADMIN_HOME_PAGE_KEY = 'admin.workflow_orchestration.home';

interface StatusBucketItem {
  color: string;
  count: number;
  key: string;
  label: string;
}

const router = useRouter();
const loading = ref(false);
const errorMessage = ref('');
const overview = ref<AdminOverviewResponse | null>(null);
const intentDraft = ref('');
const canAccessAdminHomePage = hasAnyPluginAccess(ADMIN_HOME_PAGE_ACCESS_CODES);
const canLoadOverview = canAccessAdminHomePage;
const canOpenTemplates = hasPluginAccess(
  WORKFLOW_ACCESS_CODES.ADMIN_PLATFORM_TEMPLATE_LIST,
);
const canCreateTemplate = hasAllPluginAccess([
  WORKFLOW_ACCESS_CODES.ADMIN_PLATFORM_TEMPLATE_LIST,
  WORKFLOW_ACCESS_CODES.ADMIN_PLATFORM_TEMPLATE_CREATE,
]);
const canOpenReleases = hasPluginAccess(
  WORKFLOW_ACCESS_CODES.ADMIN_RELEASE_OPS_LIST,
);
const canOpenRuntime = hasPluginAccess(
  WORKFLOW_ACCESS_CODES.ADMIN_RUNTIME_OPS_LIST,
);

const starterPromptKeys = [
  'contentReview',
  'opsApproval',
  'runtimeRepair',
] as const;

async function loadOverview() {
  if (!canLoadOverview) {
    overview.value = null;
    errorMessage.value = '';
    loading.value = false;
    return;
  }

  loading.value = true;
  errorMessage.value = '';
  try {
    overview.value = await getAdminOverviewApi();
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : $t(`${ADMIN_I18N_PREFIX}.common.emptyState`);
  } finally {
    loading.value = false;
  }
}

function buildStatusBuckets(
  source: Record<string, number> | undefined,
  resolveLabel: (value: string) => string,
  resolveColor: (value: string) => string,
): StatusBucketItem[] {
  return Object.entries(source ?? {})
    .map(([key, count]) => ({
      key,
      count,
      label: resolveLabel(key),
      color: resolveColor(key),
    }))
    .sort((left, right) => right.count - left.count);
}

const templateSummary = computed(() => overview.value?.template_summary);
const releaseSummary = computed(() => overview.value?.release_summary);
const runtimeSummary = computed(() => overview.value?.runtime_summary);
const settingsSummary = computed(() => overview.value?.settings_summary);

const summaryCards = computed(() => [
  {
    key: 'templates',
    icon: 'lucide:copy',
    label: $t(`${ADMIN_I18N_PREFIX}.home.metrics.templates`),
    value: formatCompactNumber(templateSummary.value?.total_templates),
  },
  {
    key: 'versions',
    icon: 'lucide:history',
    label: $t(`${ADMIN_I18N_PREFIX}.home.metrics.versions`),
    value: formatCompactNumber(templateSummary.value?.total_versions),
  },
  {
    key: 'releases',
    icon: 'lucide:rocket',
    label: $t(`${ADMIN_I18N_PREFIX}.home.metrics.releases`),
    value: formatCompactNumber(releaseSummary.value?.total_releases),
  },
  {
    key: 'runningRuns',
    icon: 'lucide:activity',
    label: $t(`${ADMIN_I18N_PREFIX}.home.metrics.runningRuns`),
    value: formatCompactNumber(runtimeSummary.value?.run_status_counts?.running),
  },
  {
    key: 'failedRuns',
    icon: 'lucide:shield-alert',
    label: $t(`${ADMIN_I18N_PREFIX}.home.metrics.failedRuns`),
    value: formatCompactNumber(runtimeSummary.value?.run_status_counts?.failed),
  },
  {
    key: 'environments',
    icon: 'lucide:layers-2',
    label: $t(`${ADMIN_I18N_PREFIX}.home.metrics.environments`),
    value: formatCompactNumber(settingsSummary.value?.environment_count),
  },
]);

const templateStatusBuckets = computed(() =>
  buildStatusBuckets(
    templateSummary.value?.status_counts,
    getTemplateStatusText,
    getTemplateStatusColor,
  ),
);

const releaseStatusBuckets = computed(() =>
  buildStatusBuckets(
    releaseSummary.value?.status_counts,
    getReleaseStatusText,
    getReleaseStatusColor,
  ),
);

const runtimeStatusBuckets = computed(() =>
  buildStatusBuckets(
    runtimeSummary.value?.run_status_counts,
    getRunStatusText,
    getRunStatusColor,
  ),
);

const resourceCards = computed(() => [
  {
    allowed: canOpenTemplates,
    key: 'templates',
    ctaLabel: $t(`${ADMIN_I18N_PREFIX}.home.resources.templates.action`),
    description: $t(`${ADMIN_I18N_PREFIX}.home.resources.templates.description`),
    facts: [
      {
        label: $t(`${ADMIN_I18N_PREFIX}.home.templateFacts.totalVersions`),
        value: formatCompactNumber(templateSummary.value?.total_versions),
      },
      {
        label: $t(`${ADMIN_I18N_PREFIX}.home.templateFacts.totalRuns`),
        value: formatCompactNumber(templateSummary.value?.total_runs),
      },
      {
        label: $t(`${ADMIN_I18N_PREFIX}.home.templateFacts.totalArtifacts`),
        value: formatCompactNumber(templateSummary.value?.total_artifacts),
      },
    ],
    icon: 'lucide:copy-plus',
    path: buildAdminPath('templates'),
    statusBuckets: templateStatusBuckets.value,
    title: $t(`${ADMIN_I18N_PREFIX}.home.resources.templates.title`),
  },
  {
    allowed: canOpenReleases,
    key: 'releases',
    ctaLabel: $t(`${ADMIN_I18N_PREFIX}.home.resources.releases.action`),
    description: $t(`${ADMIN_I18N_PREFIX}.home.resources.releases.description`),
    facts: [
      {
        label: $t(`${ADMIN_I18N_PREFIX}.home.releaseFacts.latestPublishedAt`),
        value: formatDateTime(releaseSummary.value?.latest_published_at),
      },
      {
        label: $t(`${ADMIN_I18N_PREFIX}.home.metrics.releases`),
        value: formatCompactNumber(releaseSummary.value?.total_releases),
      },
    ],
    icon: 'lucide:rocket',
    path: buildAdminPath('releases'),
    statusBuckets: releaseStatusBuckets.value,
    title: $t(`${ADMIN_I18N_PREFIX}.home.resources.releases.title`),
  },
  {
    allowed: canOpenRuntime,
    key: 'runtime',
    ctaLabel: $t(`${ADMIN_I18N_PREFIX}.home.resources.runtime.action`),
    description: $t(`${ADMIN_I18N_PREFIX}.home.resources.runtime.description`),
    facts: [
      {
        label: $t(`${ADMIN_I18N_PREFIX}.home.runtimeFacts.runStatuses`),
        value: formatCompactNumber(runtimeStatusBuckets.value.length),
      },
      {
        label: $t(`${ADMIN_I18N_PREFIX}.home.runtimeFacts.artifactStatuses`),
        value: formatCompactNumber(
          Object.keys(runtimeSummary.value?.artifact_status_counts ?? {}).length,
        ),
      },
    ],
    icon: 'lucide:activity',
    path: buildAdminPath('runtime'),
    statusBuckets: runtimeStatusBuckets.value,
    title: $t(`${ADMIN_I18N_PREFIX}.home.resources.runtime.title`),
  },
].filter((section) => section.allowed));

async function openTemplateCreate() {
  if (!canCreateTemplate) {
    errorMessage.value = $t(`${ADMIN_I18N_PREFIX}.common.permissionDenied`);
    return;
  }
  await router.push({
    path: buildAdminPath('templates'),
    query: { create: '1' },
  });
}

function openPath(path: string) {
  void router.push(path);
}

function buildPlannerPrompt(seed?: string): string {
  const normalizedSeed = seed?.trim() || intentDraft.value.trim();
  return buildPrompt([
    $t(`${ADMIN_I18N_PREFIX}.home.ai.systemLead`),
    normalizedSeed
      ? $t(`${ADMIN_I18N_PREFIX}.home.ai.userIdea`, {
          idea: normalizedSeed,
        })
      : $t(`${ADMIN_I18N_PREFIX}.home.ai.emptyIdea`),
    $t(`${ADMIN_I18N_PREFIX}.home.ai.outputContract`),
  ]);
}

function openAIPlanner(seed?: string) {
  openWorkflowAIPanel({
    conversationScope: ADMIN_WORKFLOW_AI_CONVERSATION_SCOPE,
    message: buildPlannerPrompt(seed),
    pageKey: ADMIN_HOME_PAGE_KEY,
  });
}

useWorkflowPageAI({
  conversationScope: ADMIN_WORKFLOW_AI_CONVERSATION_SCOPE,
  pageKey: ADMIN_HOME_PAGE_KEY,
  buildContext: () => ({
    entityDescription: $t(`${ADMIN_I18N_PREFIX}.home.ai.pageDescription`),
    entityTitle: $t(`${ADMIN_I18N_PREFIX}.home.title`),
    entityType: 'workflow_orchestration_admin_home',
    pageData: {
      failed_runs: runtimeSummary.value?.run_status_counts?.failed ?? 0,
      intent_draft: intentDraft.value,
      release_total: releaseSummary.value?.total_releases ?? 0,
      template_total: templateSummary.value?.total_templates ?? 0,
    },
    pageTitle: $t(`${ADMIN_I18N_PREFIX}.home.title`),
  }),
  operations: [
    {
      name: 'open_admin_template_create',
      label: $t(`${ADMIN_I18N_PREFIX}.home.ai.operations.openTemplateCreate.label`),
      description: $t(
        `${ADMIN_I18N_PREFIX}.home.ai.operations.openTemplateCreate.description`,
      ),
      readonly: true,
      handler: async () => {
        if (!canCreateTemplate) {
          return {
            success: false,
            message: $t(`${ADMIN_I18N_PREFIX}.common.permissionDenied`),
          };
        }
        await openTemplateCreate();
        return {
          success: true,
          message: $t(
            `${ADMIN_I18N_PREFIX}.home.ai.operations.openTemplateCreate.success`,
          ),
        };
      },
    },
    {
      name: 'open_admin_home_ai_planner',
      label: $t(`${ADMIN_I18N_PREFIX}.home.ai.operations.openAI.label`),
      description: $t(`${ADMIN_I18N_PREFIX}.home.ai.operations.openAI.description`),
      readonly: true,
      params: {
        idea: {
          description: $t(
            `${ADMIN_I18N_PREFIX}.home.ai.operations.openAI.ideaDescription`,
          ),
          required: false,
          type: 'string',
        },
      },
      handler: async (params: Record<string, unknown>) => {
        openAIPlanner(typeof params.idea === 'string' ? params.idea : undefined);
        return {
          success: true,
          message: $t(`${ADMIN_I18N_PREFIX}.home.ai.operations.openAI.success`),
        };
      },
    },
    {
      name: 'open_admin_runtime_center',
      label: $t(`${ADMIN_I18N_PREFIX}.home.ai.operations.openRuntime.label`),
      description: $t(
        `${ADMIN_I18N_PREFIX}.home.ai.operations.openRuntime.description`,
      ),
      readonly: true,
      handler: async () => {
        if (!canOpenRuntime) {
          return {
            success: false,
            message: $t(`${ADMIN_I18N_PREFIX}.common.permissionDenied`),
          };
        }
        openPath(buildAdminPath('runtime'));
        return {
          success: true,
          message: $t(`${ADMIN_I18N_PREFIX}.home.ai.operations.openRuntime.success`),
        };
      },
    },
    ...(canLoadOverview
      ? [
          {
            name: 'refresh_admin_workbench',
            label: $t(`${ADMIN_I18N_PREFIX}.home.ai.operations.refresh.label`),
            description: $t(
              `${ADMIN_I18N_PREFIX}.home.ai.operations.refresh.description`,
            ),
            readonly: true,
            handler: async () => {
              await loadOverview();
              return {
                success: true,
                message: $t(
                  `${ADMIN_I18N_PREFIX}.home.ai.operations.refresh.success`,
                ),
              };
            },
          },
        ]
      : []),
  ],
});

onMounted(() => {
  void loadOverview();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <template v-if="canAccessAdminHomePage">
    <section class="relative overflow-hidden rounded-[28px] border bg-card shadow-sm">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.16),transparent_48%),radial-gradient(circle_at_bottom_right,rgba(15,23,42,0.08),transparent_52%)]" />
      <div class="relative grid gap-4 p-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <div class="space-y-5">
          <div class="space-y-3">
            <div
              class="inline-flex items-center gap-2 rounded-full border bg-background/85 px-3 py-1 text-xs text-muted-foreground"
            >
              <IconifyIcon icon="lucide:workflow" class="h-3.5 w-3.5" />
              {{ $t(`${ADMIN_I18N_PREFIX}.home.badge`) }}
            </div>
            <div>
              <h1 class="text-2xl font-semibold text-foreground md:text-3xl">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.title`) }}
              </h1>
              <p class="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.subtitle`) }}
              </p>
            </div>
          </div>

          <div class="rounded-[26px] border bg-background/85 p-4">
            <div class="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
              <IconifyIcon icon="lucide:sparkles" class="h-4 w-4 text-primary" />
              {{ $t(`${ADMIN_I18N_PREFIX}.home.ai.cardTitle`) }}
            </div>
            <Input.TextArea
              v-model:value="intentDraft"
              :auto-size="{ minRows: 4, maxRows: 7 }"
              :placeholder="$t(`${ADMIN_I18N_PREFIX}.home.ai.placeholder`)"
            />
            <div class="mt-4 flex flex-wrap gap-3">
              <Button type="primary" @click="openAIPlanner()">
                <template #icon>
                  <IconifyIcon icon="lucide:message-square-plus" />
                </template>
                {{ $t(`${ADMIN_I18N_PREFIX}.home.actions.askAI`) }}
              </Button>
              <Button v-if="canCreateTemplate" @click="openTemplateCreate">
                <template #icon>
                  <IconifyIcon icon="lucide:copy-plus" />
                </template>
                {{ $t(`${ADMIN_I18N_PREFIX}.home.actions.createTemplate`) }}
              </Button>
              <Button v-if="canLoadOverview" @click="loadOverview">
                <template #icon>
                  <IconifyIcon icon="lucide:refresh-cw" />
                </template>
                {{ $t(`${ADMIN_I18N_PREFIX}.common.refresh`) }}
              </Button>
            </div>
          </div>

          <div class="grid gap-3 md:grid-cols-3">
            <button
              v-for="promptKey in starterPromptKeys"
              :key="promptKey"
              class="rounded-3xl border bg-background/85 p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-primary/5"
              type="button"
              @click="openAIPlanner($t(`${ADMIN_I18N_PREFIX}.home.ai.starters.${promptKey}.prompt`))"
            >
              <div class="text-sm font-medium text-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.ai.starters.${promptKey}.title`) }}
              </div>
              <div class="mt-2 text-xs leading-5 text-muted-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.ai.starters.${promptKey}.description`) }}
              </div>
            </button>
          </div>
        </div>

        <Card :body-style="{ padding: '20px' }">
          <template #title>
            <div class="flex items-center gap-2">
              <IconifyIcon icon="lucide:list-checks" class="h-4 w-4 text-primary" />
              {{ $t(`${ADMIN_I18N_PREFIX}.home.steps.title`) }}
            </div>
          </template>

          <div class="space-y-3">
            <div class="rounded-2xl border bg-accent/10 p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
                01
              </div>
              <div class="mt-2 text-sm font-medium text-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.steps.create.title`) }}
              </div>
              <div class="mt-1 text-xs leading-5 text-muted-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.steps.create.description`) }}
              </div>
            </div>
            <div class="rounded-2xl border bg-accent/10 p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
                02
              </div>
              <div class="mt-2 text-sm font-medium text-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.steps.publish.title`) }}
              </div>
              <div class="mt-1 text-xs leading-5 text-muted-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.steps.publish.description`) }}
              </div>
            </div>
            <div class="rounded-2xl border bg-accent/10 p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
                03
              </div>
              <div class="mt-2 text-sm font-medium text-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.steps.runtime.title`) }}
              </div>
              <div class="mt-1 text-xs leading-5 text-muted-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.steps.runtime.description`) }}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </section>

    <section
      v-if="errorMessage"
      class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
    >
      {{ errorMessage }}
    </section>

    <div class="grid grid-cols-2 gap-3 lg:grid-cols-6">
      <div
        v-for="card in summaryCards"
        :key="card.key"
        class="rounded-2xl border bg-card p-4 shadow-sm"
      >
        <div class="flex items-center gap-2 text-xs text-muted-foreground">
          <IconifyIcon :icon="card.icon" class="h-3.5 w-3.5" />
          <span>{{ card.label }}</span>
        </div>
        <div class="mt-3 text-xl font-semibold text-foreground">
          {{ card.value }}
        </div>
      </div>
    </div>

    <Spin :spinning="loading">
      <div class="grid gap-4 xl:grid-cols-3">
        <Card
          v-for="section in resourceCards"
          :key="section.key"
          :body-style="{ padding: '18px' }"
        >
          <template #title>
            <div class="flex items-center gap-2">
              <IconifyIcon :icon="section.icon" class="h-4 w-4 text-primary" />
              {{ section.title }}
            </div>
          </template>

          <p class="text-sm leading-6 text-muted-foreground">
            {{ section.description }}
          </p>

          <div v-if="section.statusBuckets.length === 0" class="py-8">
            <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
          </div>
          <div v-else class="mt-4 space-y-4">
            <div class="flex flex-wrap gap-2">
              <Tag
                v-for="item in section.statusBuckets"
                :key="item.key"
                :color="item.color"
                class="!m-0"
              >
                {{ item.label }} · {{ formatCompactNumber(item.count) }}
              </Tag>
            </div>
            <div class="grid gap-3">
              <div
                v-for="fact in section.facts"
                :key="fact.label"
                class="rounded-2xl border bg-accent/10 px-4 py-3"
              >
                <div class="text-xs text-muted-foreground">
                  {{ fact.label }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ fact.value }}
                </div>
              </div>
            </div>
          </div>

          <div class="mt-5">
            <Button block @click="openPath(section.path)">
              {{ section.ctaLabel }}
            </Button>
          </div>
        </Card>
      </div>
    </Spin>
    </template>

    <Card v-else :body-style="{ padding: '32px' }">
      <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.permissionDenied`)" />
    </Card>
  </Page>
</template>
