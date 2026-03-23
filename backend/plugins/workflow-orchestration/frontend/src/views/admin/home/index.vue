<script lang="ts" setup>
import type { AdminOverviewResponse } from '../../../types/admin';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Alert, Button, Card, Empty, Spin, Tag } from 'ant-design-vue';

import { getAdminOverviewApi } from '../../../api/admin';
import { formatCompactNumber, formatDateTime } from '../shared/format';

import { builderSurfaceCards, homeQuickLinks } from './data';

import { getReleaseStatusColor, getReleaseStatusText } from '../releases/data';
import { getRunStatusColor, getRunStatusText } from '../runtime/data';
import {
  getTemplateStatusColor,
  getTemplateStatusText,
} from '../templates/data';
import { ADMIN_I18N_PREFIX } from '../shared/constants';
import { $t } from '@novus/plugin-shared';

defineOptions({ name: 'WorkflowOrchestrationAdminHome' });

interface StatusBucketItem {
  color: string;
  count: number;
  key: string;
  label: string;
}

const router = useRouter();

const loading = ref(false);
const overview = ref<AdminOverviewResponse | null>(null);

async function loadOverview() {
  loading.value = true;
  try {
    overview.value = await getAdminOverviewApi();
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

const artifactStatusBuckets = computed(() =>
  Object.entries(runtimeSummary.value?.artifact_status_counts ?? {})
    .map(([key, count]) => ({
      key,
      count,
    }))
    .sort((left, right) => right.count - left.count),
);

function goTo(path: string) {
  router.push(path);
}

onMounted(() => {
  void loadOverview();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <section class="relative overflow-hidden rounded-2xl border bg-card shadow-sm">
      <div class="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-primary/5" />
      <div class="relative flex flex-col gap-4 p-5">
        <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div class="space-y-2">
            <div
              class="inline-flex items-center gap-2 rounded-full border bg-background/85 px-3 py-1 text-xs text-muted-foreground"
            >
              <IconifyIcon icon="lucide:workflow" class="h-3.5 w-3.5" />
              {{ $t(`${ADMIN_I18N_PREFIX}.home.badge`) }}
            </div>
            <div>
              <h1 class="text-xl font-semibold text-foreground md:text-2xl">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.title`) }}
              </h1>
              <p class="mt-1 max-w-3xl text-sm text-muted-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.subtitle`) }}
              </p>
            </div>
          </div>

          <Button :loading="loading" @click="loadOverview">
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" />
            </template>
            {{ $t(`${ADMIN_I18N_PREFIX}.common.refresh`) }}
          </Button>
        </div>

        <div class="grid grid-cols-2 gap-3 lg:grid-cols-6">
          <div
            v-for="card in summaryCards"
            :key="card.key"
            class="rounded-xl border bg-background/80 p-3"
          >
            <div class="flex items-center gap-2 text-xs text-muted-foreground">
              <IconifyIcon :icon="card.icon" class="h-3.5 w-3.5" />
              <span>{{ card.label }}</span>
            </div>
            <div class="mt-2 text-lg font-semibold text-foreground">
              {{ card.value }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <Alert
      :message="$t(`${ADMIN_I18N_PREFIX}.home.contractNotice.title`)"
      :description="$t(`${ADMIN_I18N_PREFIX}.home.contractNotice.description`)"
      show-icon
      type="info"
    />

    <div class="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(340px,0.7fr)]">
      <Card :body-style="{ padding: '18px' }">
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:panel-top-open" class="h-4 w-4 text-primary" />
            {{ $t(`${ADMIN_I18N_PREFIX}.home.quickLinks.title`) }}
          </div>
        </template>

        <div class="grid gap-3 md:grid-cols-3">
          <button
            v-for="link in homeQuickLinks"
            :key="link.key"
            class="rounded-2xl border bg-accent/10 p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-primary/5"
            type="button"
            @click="goTo(link.path)"
          >
            <div class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
              <IconifyIcon :icon="link.icon" class="h-5 w-5 text-primary" />
            </div>
            <div class="text-sm font-medium text-foreground">
              {{ $t(`${ADMIN_I18N_PREFIX}.${link.titleKey}`) }}
            </div>
            <div class="mt-1 text-xs leading-5 text-muted-foreground">
              {{ $t(`${ADMIN_I18N_PREFIX}.${link.descriptionKey}`) }}
            </div>
          </button>
        </div>
      </Card>

      <Card :body-style="{ padding: '18px' }">
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:layers-3" class="h-4 w-4 text-primary" />
            {{ $t(`${ADMIN_I18N_PREFIX}.home.builderSurfaces.title`) }}
          </div>
        </template>

        <div class="space-y-3">
          <div
            v-for="surface in builderSurfaceCards"
            :key="surface.code"
            class="rounded-xl border bg-accent/10 p-3"
          >
            <div class="flex items-start gap-3">
              <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                <IconifyIcon :icon="surface.icon" class="h-4 w-4 text-primary" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.${surface.titleKey}`) }}
                  </span>
                  <Tag color="default" class="!m-0">
                    {{ $t(`${ADMIN_I18N_PREFIX}.home.builderSurfaces.notExposed`) }}
                  </Tag>
                </div>
                <p class="mt-1 text-xs leading-5 text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.${surface.descriptionKey}`) }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>

    <Spin :spinning="loading">
      <div class="grid gap-4 xl:grid-cols-3">
        <Card :body-style="{ padding: '18px' }">
          <template #title>
            <div class="flex items-center gap-2">
              <IconifyIcon icon="lucide:copy" class="h-4 w-4 text-primary" />
              {{ $t(`${ADMIN_I18N_PREFIX}.home.sections.templates`) }}
            </div>
          </template>

          <div v-if="templateStatusBuckets.length === 0" class="py-8">
            <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
          </div>
          <div v-else class="space-y-4">
            <div class="flex flex-wrap gap-2">
              <Tag
                v-for="item in templateStatusBuckets"
                :key="item.key"
                :color="item.color"
                class="!m-0"
              >
                {{ item.label }} · {{ formatCompactNumber(item.count) }}
              </Tag>
            </div>
            <div class="grid gap-3 md:grid-cols-3">
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.home.templateFacts.totalVersions`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ formatCompactNumber(templateSummary?.total_versions) }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.home.templateFacts.totalRuns`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ formatCompactNumber(templateSummary?.total_runs) }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.home.templateFacts.totalArtifacts`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ formatCompactNumber(templateSummary?.total_artifacts) }}
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card :body-style="{ padding: '18px' }">
          <template #title>
            <div class="flex items-center gap-2">
              <IconifyIcon icon="lucide:rocket" class="h-4 w-4 text-primary" />
              {{ $t(`${ADMIN_I18N_PREFIX}.home.sections.releases`) }}
            </div>
          </template>

          <div v-if="releaseStatusBuckets.length === 0" class="py-8">
            <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
          </div>
          <div v-else class="space-y-4">
            <div class="flex flex-wrap gap-2">
              <Tag
                v-for="item in releaseStatusBuckets"
                :key="item.key"
                :color="item.color"
                class="!m-0"
              >
                {{ item.label }} · {{ formatCompactNumber(item.count) }}
              </Tag>
            </div>
            <div class="rounded-xl border bg-accent/10 px-4 py-3">
              <div class="text-xs text-muted-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.releaseFacts.latestPublishedAt`) }}
              </div>
              <div class="mt-2 text-sm font-medium text-foreground">
                {{ formatDateTime(releaseSummary?.latest_published_at) }}
              </div>
            </div>
          </div>
        </Card>

        <Card :body-style="{ padding: '18px' }">
          <template #title>
            <div class="flex items-center gap-2">
              <IconifyIcon icon="lucide:activity" class="h-4 w-4 text-primary" />
              {{ $t(`${ADMIN_I18N_PREFIX}.home.sections.runtime`) }}
            </div>
          </template>

          <div v-if="runtimeStatusBuckets.length === 0" class="py-8">
            <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
          </div>
          <div v-else class="space-y-4">
            <div class="space-y-2">
              <div class="text-xs text-muted-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.runtimeFacts.runStatuses`) }}
              </div>
              <div class="flex flex-wrap gap-2">
                <Tag
                  v-for="item in runtimeStatusBuckets"
                  :key="item.key"
                  :color="item.color"
                  class="!m-0"
                >
                  {{ item.label }} · {{ formatCompactNumber(item.count) }}
                </Tag>
              </div>
            </div>
            <div class="space-y-2">
              <div class="text-xs text-muted-foreground">
                {{ $t(`${ADMIN_I18N_PREFIX}.home.runtimeFacts.artifactStatuses`) }}
              </div>
              <div class="flex flex-wrap gap-2">
                <Tag
                  v-for="item in artifactStatusBuckets"
                  :key="item.key"
                  class="!m-0"
                >
                  {{ item.key }} · {{ formatCompactNumber(item.count) }}
                </Tag>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </Spin>
  </Page>
</template>
