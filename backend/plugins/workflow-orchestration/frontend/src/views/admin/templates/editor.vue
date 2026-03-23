<script lang="ts" setup>
import type { WorkflowTemplateDetail } from '../../../types/admin';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Alert, Button, Card, Empty, Modal, Spin, Tag, message } from 'ant-design-vue';

import {
  getAdminTemplateDetailApi,
  publishAdminTemplateApi,
} from '../../../api/admin';
import { formatCompactNumber, formatDateTime } from '../shared/format';

import {
  buildTemplatePublishPayload,
  editorCapabilityCategories,
  getBuilderSurfaceText,
  getCapabilityLabel,
  getReleaseScopeText,
  getTemplateGraphCounts,
  getTemplateStatusColor,
  getTemplateStatusText,
} from './data';

import { ADMIN_I18N_PREFIX, buildAdminPath } from '../shared/constants';
import { $t } from '@novus/plugin-shared';

defineOptions({ name: 'WorkflowOrchestrationAdminTemplateEditor' });

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

const templateId = computed(() => resolveNumericParam(route.params.id));
const graphCounts = computed(() => getTemplateGraphCounts(template.value));
const graphNodes = computed(() => template.value?.nodes ?? []);
const graphEdges = computed(() => template.value?.edges ?? []);

const capabilityCategoryCards = computed(() =>
  editorCapabilityCategories.map((category) => {
    const items = (template.value?.builder_capabilities ?? []).filter(
      (item) => item.category === category.code,
    );

    return {
      ...category,
      availableCount: items.filter((item) => item.available !== false).length,
      items,
    };
  }),
);

const governanceBlocks = computed(() => [
  {
    key: 'locked',
    icon: 'lucide:lock',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.segments.locked`),
  },
  {
    key: 'editable',
    icon: 'lucide:square-pen',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.segments.editable`),
  },
  {
    key: 'parameterized',
    icon: 'lucide:sliders-horizontal',
    label: $t(`${ADMIN_I18N_PREFIX}.templates.detail.segments.parameterized`),
  },
]);

async function loadPage() {
  if (!templateId.value) {
    template.value = null;
    return;
  }

  loading.value = true;
  try {
    template.value = await getAdminTemplateDetailApi(templateId.value);
  } finally {
    loading.value = false;
  }
}

function goBack() {
  if (!templateId.value) {
    router.push(buildAdminPath('templates'));
    return;
  }

  router.push(buildAdminPath(`templates/${templateId.value}`));
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
      :message="$t(`${ADMIN_I18N_PREFIX}.editor.banner.message`)"
      :description="$t(`${ADMIN_I18N_PREFIX}.editor.banner.description`)"
      show-icon
      type="info"
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
                  <IconifyIcon icon="lucide:spline" class="h-3.5 w-3.5" />
                  {{ $t(`${ADMIN_I18N_PREFIX}.editor.badge`) }}
                </div>
                <div>
                  <h1 class="text-xl font-semibold text-foreground md:text-2xl">
                    {{ $t(`${ADMIN_I18N_PREFIX}.editor.title`) }}
                  </h1>
                  <p class="mt-1 text-sm text-muted-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.editor.subtitle`) }}
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
                  {{ $t(`${ADMIN_I18N_PREFIX}.common.backToDetail`) }}
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
              <div class="rounded-xl border bg-background/85 p-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.editor.cards.version`) }}
                </div>
                <div class="mt-2 font-mono text-lg font-semibold text-foreground">
                  {{ template.latest_version?.version_label || template.latest_version_label || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                </div>
              </div>
              <div class="rounded-xl border bg-background/85 p-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.editor.cards.nodes`) }}
                </div>
                <div class="mt-2 text-lg font-semibold text-foreground">
                  {{ formatCompactNumber(graphCounts.nodeCount) }}
                </div>
              </div>
              <div class="rounded-xl border bg-background/85 p-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.editor.cards.edges`) }}
                </div>
                <div class="mt-2 text-lg font-semibold text-foreground">
                  {{ formatCompactNumber(graphCounts.edgeCount) }}
                </div>
              </div>
              <div class="rounded-xl border bg-background/85 p-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.editor.cards.updatedAt`) }}
                </div>
                <div class="mt-2 text-sm font-medium text-foreground">
                  {{ formatDateTime(template.updated_at) }}
                </div>
              </div>
            </div>
          </div>
        </section>

        <div class="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
          <Card :body-style="{ padding: '18px' }">
            <template #title>
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:palette" class="h-4 w-4 text-primary" />
                {{ $t(`${ADMIN_I18N_PREFIX}.editor.palette.title`) }}
              </div>
            </template>

            <div class="space-y-3">
              <div
                v-for="category in capabilityCategoryCards"
                :key="category.code"
                class="rounded-2xl border bg-accent/10 p-4"
              >
                <div class="flex items-start gap-3">
                  <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                    <IconifyIcon :icon="category.icon" class="h-4 w-4 text-primary" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="text-sm font-semibold text-foreground">
                      {{ $t(`${ADMIN_I18N_PREFIX}.${category.titleKey}`) }}
                    </div>
                    <div class="mt-1 text-xs leading-5 text-muted-foreground">
                      {{ $t(`${ADMIN_I18N_PREFIX}.${category.descriptionKey}`) }}
                    </div>
                    <div class="mt-3 flex flex-wrap gap-2">
                      <Tag v-if="category.items.length > 0" class="!m-0">
                        {{
                          $t(`${ADMIN_I18N_PREFIX}.editor.palette.availableCount`, {
                            count: category.availableCount,
                          })
                        }}
                      </Tag>
                      <Tag v-if="category.items.length > 0" class="!m-0">
                        {{
                          $t(`${ADMIN_I18N_PREFIX}.editor.palette.totalCount`, {
                            count: category.items.length,
                          })
                        }}
                      </Tag>
                      <Tag v-else class="!m-0">
                        {{ $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`) }}
                      </Tag>
                    </div>
                  </div>
                </div>

                <div v-if="category.items.length > 0" class="mt-3 space-y-2">
                  <div
                    v-for="item in category.items.slice(0, 4)"
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
                <Alert
                  v-else
                  class="mt-3"
                  :message="$t(`${ADMIN_I18N_PREFIX}.editor.palette.notIntegrated`)"
                  show-icon
                  type="info"
                />
              </div>
            </div>
          </Card>

          <Card :body-style="{ padding: '18px' }">
            <template #title>
              <div class="flex items-center gap-2">
                <IconifyIcon icon="lucide:workflow" class="h-4 w-4 text-primary" />
                {{ $t(`${ADMIN_I18N_PREFIX}.editor.canvas.title`) }}
              </div>
            </template>

            <div v-if="graphNodes.length === 0" class="space-y-3 py-6">
              <Alert
                :message="$t(`${ADMIN_I18N_PREFIX}.editor.canvas.emptyTitle`)"
                :description="$t(`${ADMIN_I18N_PREFIX}.editor.canvas.emptyDescription`)"
                show-icon
                type="warning"
              />
              <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
            </div>
            <div v-else class="space-y-4">
              <div
                class="rounded-3xl border bg-gradient-to-br from-primary/10 via-background to-accent/20 p-4"
              >
                <div class="mb-4 flex flex-wrap items-center gap-2">
                  <Tag class="!m-0">
                    {{
                      $t(`${ADMIN_I18N_PREFIX}.editor.canvas.nodeCount`, {
                        count: graphNodes.length,
                      })
                    }}
                  </Tag>
                  <Tag class="!m-0">
                    {{
                      $t(`${ADMIN_I18N_PREFIX}.editor.canvas.edgeCount`, {
                        count: graphEdges.length,
                      })
                    }}
                  </Tag>
                </div>

                <div class="grid gap-3 md:grid-cols-2">
                  <div
                    v-for="node in graphNodes"
                    :key="node.id"
                    class="rounded-2xl border bg-background/85 p-4 shadow-sm"
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0 flex-1">
                        <div class="truncate text-sm font-semibold text-foreground">
                          {{ node.title || node.node_key }}
                        </div>
                        <div class="mt-1 text-xs text-muted-foreground">
                          {{ node.node_type }}
                        </div>
                      </div>
                      <Tag class="!m-0">
                        {{ node.node_key }}
                      </Tag>
                    </div>

                    <div class="mt-3 flex flex-wrap gap-2">
                      <Tag class="!m-0">
                        {{ node.node_type }}
                      </Tag>
                      <Tag v-if="node.timeout_minutes !== null && node.timeout_minutes !== undefined" class="!m-0">
                        {{ `${node.timeout_minutes}m` }}
                      </Tag>
                      <Tag v-if="node.retry_limit !== null && node.retry_limit !== undefined" class="!m-0">
                        {{ `retry:${node.retry_limit}` }}
                      </Tag>
                    </div>
                  </div>
                </div>
              </div>

              <div class="rounded-2xl border bg-accent/10 p-4">
                <div class="text-sm font-semibold text-foreground">
                  {{ $t(`${ADMIN_I18N_PREFIX}.editor.canvas.connections`) }}
                </div>
                <div class="mt-3 space-y-2">
                  <div
                    v-for="edge in graphEdges"
                    :key="edge.id || edge.edge_key"
                    class="flex items-center gap-2 rounded-xl border bg-background/85 px-3 py-3 text-sm text-foreground"
                  >
                    <span class="font-medium">{{ edge.from_node_key }}</span>
                    <IconifyIcon icon="lucide:move-right" class="h-3.5 w-3.5 text-muted-foreground" />
                    <span class="font-medium">{{ edge.to_node_key }}</span>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <div class="space-y-4">
            <Card :body-style="{ padding: '18px' }">
              <template #title>
                <div class="flex items-center gap-2">
                  <IconifyIcon icon="lucide:shield-check" class="h-4 w-4 text-primary" />
                  {{ $t(`${ADMIN_I18N_PREFIX}.editor.governance.title`) }}
                </div>
              </template>

              <Alert
                :message="$t(`${ADMIN_I18N_PREFIX}.editor.governance.notIntegrated`)"
                show-icon
                type="info"
              />

              <div class="mt-3 space-y-3">
                <div
                  v-for="block in governanceBlocks"
                  :key="block.key"
                  class="rounded-xl border bg-accent/10 px-4 py-3"
                >
                  <div class="flex items-center gap-2 text-xs text-muted-foreground">
                    <IconifyIcon :icon="block.icon" class="h-3.5 w-3.5" />
                    <span>{{ block.label }}</span>
                  </div>
                  <div class="mt-2 text-sm font-medium text-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`) }}
                  </div>
                </div>
              </div>
            </Card>

            <Card :body-style="{ padding: '18px' }">
              <template #title>
                <div class="flex items-center gap-2">
                  <IconifyIcon icon="lucide:list-checks" class="h-4 w-4 text-primary" />
                  {{ $t(`${ADMIN_I18N_PREFIX}.editor.readiness.title`) }}
                </div>
              </template>

              <div class="space-y-3">
                <div class="rounded-xl border bg-accent/10 px-4 py-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.editor.readiness.owner`) }}
                  </div>
                  <div class="mt-2 text-sm font-medium text-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`) }}
                  </div>
                </div>
                <div class="rounded-xl border bg-accent/10 px-4 py-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.editor.readiness.latestRelease`) }}
                  </div>
                  <div class="mt-2 text-sm font-medium text-foreground">
                    {{ template.latest_release?.code || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                  </div>
                </div>
                <div class="rounded-xl border bg-accent/10 px-4 py-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.editor.readiness.lastPublishedAt`) }}
                  </div>
                  <div class="mt-2 text-sm font-medium text-foreground">
                    {{ formatDateTime(template.published_at) }}
                  </div>
                </div>
                <div class="rounded-xl border bg-accent/10 px-4 py-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.editor.readiness.scope`) }}
                  </div>
                  <div class="mt-2 text-sm font-medium text-foreground">
                    {{ getReleaseScopeText(template.release_scope) }}
                  </div>
                </div>
                <div class="rounded-xl border bg-accent/10 px-4 py-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.editor.readiness.schemaNote`) }}
                  </div>
                  <div class="mt-2 text-sm leading-6 text-foreground">
                    {{ $t(`${ADMIN_I18N_PREFIX}.editor.readiness.schemaNoteValue`) }}
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </template>

      <template v-else-if="!templateId">
        <Card :body-style="{ padding: '24px' }">
          <Empty :description="$t(`${ADMIN_I18N_PREFIX}.templates.detail.invalidTemplate`)" />
        </Card>
      </template>
    </Spin>
  </Page>
</template>
