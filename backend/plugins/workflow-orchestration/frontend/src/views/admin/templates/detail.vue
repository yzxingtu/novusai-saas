<script lang="ts" setup>
import type {
  WorkflowBuilderCapability,
  WorkflowTemplateDetail,
  WorkflowTemplateVersion,
} from '../../../types/admin';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Card,
  Empty,
  Modal,
  Spin,
  Table,
  Tag,
  Tooltip,
  message,
} from 'ant-design-vue';

import {
  getAdminTemplateDetailApi,
  listAdminTemplateVersionsApi,
  publishAdminTemplateApi,
} from '../../../api/admin';
import { formatCompactNumber, formatDateTime } from '../shared/format';

import {
  buildTemplatePublishPayload,
  getBuilderSurfaceText,
  getCapabilityCategoryText,
  getCapabilityLabel,
  getReleaseScopeText,
  getTemplateCategoryText,
  getTemplateGraphCounts,
  getTemplateStatusColor,
  getTemplateStatusText,
} from './data';

import { ADMIN_I18N_PREFIX, buildAdminPath } from '../shared/constants';
import { $t } from '@novus/plugin-shared';

defineOptions({ name: 'WorkflowOrchestrationAdminTemplateDetail' });

interface CapabilityGroup {
  category: string;
  categoryLabel: string;
  items: WorkflowBuilderCapability[];
}

function resolveNumericParam(raw: unknown): number | null {
  const value = Array.isArray(raw) ? raw[0] : raw;
  const normalized = Number(value);
  return Number.isFinite(normalized) && normalized > 0 ? normalized : null;
}

const route = useRoute();
const router = useRouter();

const loading = ref(false);
const publishing = ref(false);
const template = ref<null | WorkflowTemplateDetail>(null);
const versions = ref<WorkflowTemplateVersion[]>([]);

const templateId = computed(() => resolveNumericParam(route.params.id));
const graphCounts = computed(() => getTemplateGraphCounts(template.value));
const nodeRows = computed(() =>
  (template.value?.nodes ?? []).map((node) => ({
    ...node,
    label: node.title || node.node_key,
  })),
);
const edgeRows = computed(() => template.value?.edges ?? []);

const capabilityGroups = computed<CapabilityGroup[]>(() => {
  const source = template.value?.builder_capabilities ?? [];
  if (source.length === 0) {
    return [];
  }

  const groups = new Map<string, WorkflowBuilderCapability[]>();
  for (const item of source) {
    const category = item.category || 'uncategorized';
    const current = groups.get(category) ?? [];
    current.push(item);
    groups.set(category, current);
  }

  return [...groups.entries()].map(([category, items]) => ({
    category,
    categoryLabel: getCapabilityCategoryText(category),
    items,
  }));
});

const overviewCards = computed(() => [
  {
    key: 'versions',
    icon: 'lucide:history',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.cards.versions`),
    value: formatCompactNumber(template.value?.version_count ?? versions.value.length),
  },
  {
    key: 'nodes',
    icon: 'lucide:git-branch',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.cards.nodes`),
    value: formatCompactNumber(graphCounts.value.nodeCount),
  },
  {
    key: 'edges',
    icon: 'lucide:move-right',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.cards.edges`),
    value: formatCompactNumber(graphCounts.value.edgeCount),
  },
  {
    key: 'releases',
    icon: 'lucide:rocket',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.cards.releases`),
    value: $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`),
  },
]);

const metadataItems = computed(() => [
  {
    key: 'status',
    label: $t(`${ADMIN_I18N_PREFIX}.common.status`),
    value: getTemplateStatusText(template.value?.status),
    color: getTemplateStatusColor(template.value?.status),
    isTag: true,
  },
  {
    key: 'category',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.table.category`),
    value: getTemplateCategoryText(template.value?.category),
  },
  {
    key: 'builderSurface',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.table.builderSurface`),
    value: getBuilderSurfaceText(template.value?.builder_surface),
  },
  {
    key: 'releaseScope',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.table.releaseScope`),
    value: getReleaseScopeText(template.value?.release_scope),
  },
  {
    key: 'latestVersion',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.table.latestVersion`),
    value:
      template.value?.latest_version?.version_label
      || template.value?.latest_version_label
      || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`),
  },
  {
    key: 'publishedVersion',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.meta.publishedVersion`),
    value:
      template.value?.published_version?.version_label
      || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`),
  },
  {
    key: 'updatedAt',
    label: $t(`${ADMIN_I18N_PREFIX}.common.updatedAt`),
    value: formatDateTime(template.value?.updated_at),
  },
  {
    key: 'publishedAt',
    label: $t(`${ADMIN_I18N_PREFIX}.common.publishedAt`),
    value: formatDateTime(template.value?.published_at),
  },
  {
    key: 'workflowType',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.meta.workflowType`),
    value: $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`),
  },
  {
    key: 'risk',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.meta.risk`),
    value: $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`),
  },
  {
    key: 'owner',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.meta.owner`),
    value: $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`),
  },
]);

const versionColumns = computed(() => [
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.version`),
    dataIndex: 'version_label',
    key: 'version_label',
    width: 160,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.status`),
    dataIndex: 'status',
    key: 'status',
    width: 140,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.detail.versionTable.nodeCount`),
    dataIndex: 'node_count',
    key: 'node_count',
    width: 140,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.detail.versionTable.edgeCount`),
    dataIndex: 'edge_count',
    key: 'edge_count',
    width: 140,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.detail.versionTable.createdBy`),
    dataIndex: 'created_by',
    key: 'created_by',
    width: 160,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.createdAt`),
    dataIndex: 'created_at',
    key: 'created_at',
    width: 180,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.detail.versionTable.publishedAt`),
    dataIndex: 'published_at',
    key: 'published_at',
    width: 180,
  },
]);

const nodeColumns = computed(() => [
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.detail.snapshotTable.node`),
    dataIndex: 'label',
    key: 'label',
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.detail.snapshotTable.type`),
    dataIndex: 'node_type',
    key: 'node_type',
    width: 160,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.detail.snapshotTable.retryLimit`),
    dataIndex: 'retry_limit',
    key: 'retry_limit',
    width: 140,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.detail.snapshotTable.timeoutMinutes`),
    dataIndex: 'timeout_minutes',
    key: 'timeout_minutes',
    width: 160,
  },
]);

async function loadPage() {
  if (!templateId.value) {
    template.value = null;
    versions.value = [];
    return;
  }

  loading.value = true;
  try {
    const [detailResponse, versionResponse] = await Promise.all([
      getAdminTemplateDetailApi(templateId.value),
      listAdminTemplateVersionsApi(templateId.value, {
        page: 1,
        pageSize: 20,
        sort: '-created_at',
      }),
    ]);

    versions.value = versionResponse.items;
    template.value = detailResponse;
  } finally {
    loading.value = false;
  }
}

function goBack() {
  router.push(buildAdminPath('templates'));
}

function openEditor() {
  if (!templateId.value) {
    return;
  }
  router.push(buildAdminPath(`templates/${templateId.value}/editor`));
}

function confirmPublish() {
  if (!templateId.value || !template.value) {
    return;
  }

  Modal.confirm({
    title: $t(`${ADMIN_I18N_PREFIX}.templates.publish.confirmTitle`),
    content: $t(`${ADMIN_I18N_PREFIX}.templates.publish.confirmContent`, {
      name: template.value.name,
    }),
    onOk: async () => {
      publishing.value = true;
      try {
        await publishAdminTemplateApi(
          templateId.value,
          buildTemplatePublishPayload(template.value),
        );
        message.success($t(`${ADMIN_I18N_PREFIX}.templates.publish.success`));
        await loadPage();
      } finally {
        publishing.value = false;
      }
    },
  });
}

watch(
  () => route.params.id,
  () => {
    void loadPage();
  },
);

onMounted(() => {
  void loadPage();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <Alert
      v-if="!templateId"
      :message="$t(`${ADMIN_I18N_PREFIX}.templates.detail.invalidTemplate`)"
      show-icon
      type="warning"
    />

    <Spin :spinning="loading">
      <template v-if="template && templateId">
        <section class="relative overflow-hidden rounded-2xl border bg-card shadow-sm">
          <div class="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-primary/5" />
          <div class="relative flex flex-col gap-4 p-5">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div class="space-y-2">
                <div
                  class="inline-flex items-center gap-2 rounded-full border bg-background/85 px-3 py-1 text-xs text-muted-foreground"
                >
                  <IconifyIcon icon="lucide:git-branch-plus" class="h-3.5 w-3.5" />
                  {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.badge`) }}
                </div>
                <div>
                  <h1 class="text-xl font-semibold text-foreground md:text-2xl">
                    {{ template.name }}
                  </h1>
                  <p class="mt-1 max-w-4xl text-sm text-muted-foreground">
                    {{
                      template.description
                        || $t(`${ADMIN_I18N_PREFIX}.common.noDescription`)
                    }}
                  </p>
                </div>
                <div class="flex flex-wrap gap-2">
                  <Tag :color="getTemplateStatusColor(template.status)" class="!m-0">
                    {{ getTemplateStatusText(template.status) }}
                  </Tag>
                  <Tag class="!m-0">
                    {{ getBuilderSurfaceText(template.builder_surface) }}
                  </Tag>
                  <Tag class="!m-0">
                    {{ getReleaseScopeText(template.release_scope) }}
                  </Tag>
                </div>
              </div>

              <div class="flex flex-wrap gap-2">
                <Button @click="goBack">
                  <template #icon>
                    <IconifyIcon icon="lucide:arrow-left" />
                  </template>
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.backToList`) }}
                </Button>
                <Button @click="openEditor">
                  <template #icon>
                    <IconifyIcon icon="lucide:spline" />
                  </template>
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.editor`) }}
                </Button>
                <Button
                  type="primary"
                  :disabled="template.latest_version_id === null || template.latest_version_id === undefined"
                  :loading="publishing"
                  @click="confirmPublish"
                >
                  <template #icon>
                    <IconifyIcon icon="lucide:rocket" />
                  </template>
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.publish`) }}
                </Button>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <div
                v-for="card in overviewCards"
                :key="card.key"
                class="rounded-xl border bg-background/85 p-3"
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
          :message="$t(`${ADMIN_I18N_PREFIX}.templates.contractNotice.title`)"
          :description="$t(`${ADMIN_I18N_PREFIX}.templates.detail.contractNotice.description`)"
          show-icon
          type="info"
        />

        <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Card :body-style="{ padding: '18px' }">
            <template #title>
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:info" class="h-4 w-4 text-primary" />
                {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.meta.title`) }}
              </div>
            </template>

            <div class="grid gap-3 md:grid-cols-2">
              <div
                v-for="item in metadataItems"
                :key="item.key"
                class="rounded-xl border bg-accent/10 px-4 py-3"
              >
                <div class="text-xs text-muted-foreground">
                  {{ item.label }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  <Tag
                    v-if="item.isTag"
                    :color="item.color || 'default'"
                    class="!m-0"
                  >
                    {{ item.value }}
                  </Tag>
                  <template v-else>
                    {{ item.value }}
                  </template>
                </div>
              </div>
            </div>
          </Card>

          <Card :body-style="{ padding: '18px' }">
            <template #title>
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:rocket" class="h-4 w-4 text-primary" />
                {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.latestRelease.title`) }}
              </div>
            </template>

            <div v-if="template.latest_release" class="space-y-3">
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.code`) }}
                </div>
                <div class="mt-2 font-mono text-sm text-foreground">
                  {{ template.latest_release.code || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.version`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{
                    template.latest_release.workflow_version_id
                      ? `#${template.latest_release.workflow_version_id}`
                      : $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`)
                  }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.environment`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ template.latest_release.environment_code || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.channel`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ template.latest_release.channel || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.releaseScope`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ getReleaseScopeText(template.latest_release.release_scope) }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.publisher`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ template.latest_release.published_by ?? $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.publishedAt`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ formatDateTime(template.latest_release.published_at) }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.latestRelease.notes`) }}
                </div>
                <div class="mt-2 text-sm leading-6 text-foreground">
                  {{
                    template.latest_release.notes
                      || $t(`${ADMIN_I18N_PREFIX}.common.noDescription`)
                  }}
                </div>
              </div>
            </div>
            <div v-else class="py-10">
              <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
            </div>
          </Card>
        </div>

        <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Card :body-style="{ padding: '18px' }">
            <template #title>
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:network" class="h-4 w-4 text-primary" />
                {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.snapshot.title`) }}
              </div>
            </template>

            <div v-if="nodeRows.length === 0" class="space-y-3">
              <Alert
                :message="$t(`${ADMIN_I18N_PREFIX}.templates.detail.snapshot.emptyHint`)"
                show-icon
                type="info"
              />
              <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
            </div>
            <div v-else class="space-y-4">
              <div class="grid gap-3 md:grid-cols-2">
                <div class="rounded-xl border bg-accent/10 px-4 py-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.snapshot.nodeCount`) }}
                  </div>
                  <div class="mt-2 text-lg font-semibold text-foreground">
                    {{ graphCounts.nodeCount }}
                  </div>
                </div>
                <div class="rounded-xl border bg-accent/10 px-4 py-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.snapshot.edgeCount`) }}
                  </div>
                  <div class="mt-2 text-lg font-semibold text-foreground">
                    {{ graphCounts.edgeCount }}
                  </div>
                </div>
              </div>

              <Table
                :columns="nodeColumns"
                :data-source="nodeRows"
                :pagination="false"
                row-key="id"
                size="small"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'label'">
                    <div class="space-y-1">
                      <div class="text-sm font-medium text-foreground">
                        {{ record.label }}
                      </div>
                      <div class="flex flex-wrap gap-1.5">
                        <Tag class="!m-0">
                          {{ record.node_key }}
                        </Tag>
                      </div>
                    </div>
                  </template>

                  <template v-else-if="column.key === 'node_type'">
                    <span class="text-sm text-foreground">
                      {{ record.node_type }}
                    </span>
                  </template>

                  <template v-else-if="column.key === 'retry_limit'">
                    <span class="text-sm text-foreground">
                      {{ record.retry_limit ?? $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                    </span>
                  </template>

                  <template v-else-if="column.key === 'timeout_minutes'">
                    <span class="text-sm text-foreground">
                      {{ record.timeout_minutes ?? $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                    </span>
                  </template>
                </template>

                <template #emptyText>
                  <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
                </template>
              </Table>

              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.snapshot.edgePreview`) }}
                </div>
                <div class="mt-3 space-y-2">
                  <div
                    v-for="edge in edgeRows.slice(0, 8)"
                    :key="edge.id || edge.edge_key"
                    class="flex items-center gap-2 rounded-lg border bg-background/80 px-3 py-2 text-sm text-foreground"
                  >
                    <span class="font-medium">{{ edge.from_node_key }}</span>
                    <IconifyIcon icon="lucide:move-right" class="h-3.5 w-3.5 text-muted-foreground" />
                    <span class="font-medium">{{ edge.to_node_key }}</span>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <Card :body-style="{ padding: '18px' }">
            <template #title>
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:layers-3" class="h-4 w-4 text-primary" />
                {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.segments.title`) }}
              </div>
            </template>

            <Alert
              :message="$t(`${ADMIN_I18N_PREFIX}.templates.detail.segments.notIntegrated`)"
              show-icon
              type="info"
            />

            <div class="mt-3 space-y-3">
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.segments.locked`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`) }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.segments.editable`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`) }}
                </div>
              </div>
              <div class="rounded-xl border bg-accent/10 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.segments.parameterized`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`) }}
                </div>
              </div>
            </div>
          </Card>
        </div>

        <Card :body-style="{ padding: '18px' }">
          <template #title>
            <div class="flex items-center gap-2">
              <IconifyIcon icon="lucide:blocks" class="h-4 w-4 text-primary" />
              {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.capabilities.title`) }}
            </div>
          </template>

          <div v-if="capabilityGroups.length === 0" class="space-y-3">
            <Alert
              :message="$t(`${ADMIN_I18N_PREFIX}.templates.detail.capabilities.emptyTitle`)"
              :description="$t(`${ADMIN_I18N_PREFIX}.templates.detail.capabilities.emptyDescription`)"
              show-icon
              type="info"
            />
          </div>
          <div v-else class="grid gap-4 xl:grid-cols-2">
            <div
              v-for="group in capabilityGroups"
              :key="group.category"
              class="rounded-2xl border bg-accent/10 p-4"
            >
              <div class="mb-3 flex items-center justify-between gap-2">
                <div>
                  <div class="text-sm font-semibold text-foreground">
                    {{ group.categoryLabel }}
                  </div>
                  <div class="mt-1 text-xs text-muted-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.capabilities.count`, { count: group.items.length }) }}
                  </div>
                </div>
              </div>

              <div class="space-y-2">
                <div
                  v-for="item in group.items"
                  :key="item.code"
                  class="rounded-xl border bg-background/85 px-3 py-3"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0 flex-1">
                      <div class="text-sm font-medium text-foreground">
                        {{ getCapabilityLabel(item) }}
                      </div>
                      <div class="mt-1 text-xs leading-5 text-muted-foreground">
                        {{
                          item.description
                            || item.reason
                            || $t(`${ADMIN_I18N_PREFIX}.common.noDescription`)
                        }}
                      </div>
                    </div>
                    <Tag :color="item.available === false ? 'default' : 'success'" class="!m-0">
                      {{
                        item.available === false
                          ? $t(`${ADMIN_I18N_PREFIX}.templates.detail.capabilities.unavailable`)
                          : $t(`${ADMIN_I18N_PREFIX}.templates.detail.capabilities.available`)
                      }}
                    </Tag>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card :body-style="{ padding: '0' }">
          <template #title>
            <div class="flex items-center gap-2 px-4 py-4">
              <IconifyIcon icon="lucide:history" class="h-4 w-4 text-primary" />
              {{ $t(`${ADMIN_I18N_PREFIX}.templates.detail.versions.title`) }}
            </div>
          </template>

          <Table
            :columns="versionColumns"
            :data-source="versions"
            :pagination="false"
            row-key="id"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'version_label'">
                <span class="font-mono text-sm text-foreground">
                  {{ record.version_label || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                </span>
              </template>

              <template v-else-if="column.key === 'status'">
                <Tag :color="getTemplateStatusColor(record.status)">
                  {{ getTemplateStatusText(record.status) }}
                </Tag>
              </template>

              <template v-else-if="column.key === 'node_count'">
                <span class="text-sm text-foreground">
                  {{ record.node_count ?? $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                </span>
              </template>

              <template v-else-if="column.key === 'edge_count'">
                <span class="text-sm text-foreground">
                  {{ record.edge_count ?? $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                </span>
              </template>

              <template v-else-if="column.key === 'created_by'">
                <span class="text-sm text-foreground">
                  {{ record.created_by ?? $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                </span>
              </template>

              <template v-else-if="column.key === 'created_at'">
                <Tooltip :title="formatDateTime(record.created_at)">
                  <span class="text-sm text-muted-foreground">
                    {{ formatDateTime(record.created_at) }}
                  </span>
                </Tooltip>
              </template>

              <template v-else-if="column.key === 'published_at'">
                <Tooltip :title="formatDateTime(record.published_at)">
                  <span class="text-sm text-muted-foreground">
                    {{ formatDateTime(record.published_at) }}
                  </span>
                </Tooltip>
              </template>
            </template>

            <template #emptyText>
              <div class="py-10">
                <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
              </div>
            </template>
          </Table>
        </Card>
      </template>

      <template v-else-if="!templateId">
        <Card :body-style="{ padding: '24px' }">
          <Empty :description="$t(`${ADMIN_I18N_PREFIX}.templates.detail.invalidTemplate`)" />
        </Card>
      </template>
    </Spin>
  </Page>
</template>
