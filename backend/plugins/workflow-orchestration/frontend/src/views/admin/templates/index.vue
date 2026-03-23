<script lang="ts" setup>
import type {
  AdminTemplateListQuery,
  WorkflowTemplateSummary,
} from '../../../types/admin';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  Modal,
  Pagination,
  Select,
  Table,
  Tag,
  Tooltip,
  message,
} from 'ant-design-vue';

import { listAdminTemplatesApi, publishAdminTemplateApi } from '../../../api/admin';
import { formatCompactNumber, formatDateTime } from '../shared/format';
import { usePaginatedCollection } from '../shared/use-paginated-collection';

import {
  buildTemplatePublishPayload,
  getBuilderSurfaceOptions,
  getBuilderSurfaceText,
  getReleaseScopeOptions,
  getReleaseScopeText,
  getTemplateCategoryText,
  getTemplateStatusColor,
  getTemplateStatusOptions,
  getTemplateStatusText,
} from './data';

import { ADMIN_I18N_PREFIX, buildAdminPath } from '../shared/constants';
import { $t } from '@novus/plugin-shared';

defineOptions({ name: 'WorkflowOrchestrationAdminTemplates' });

const router = useRouter();
const publishingId = ref<null | number>(null);
const searchKeyword = ref('');

const collection = usePaginatedCollection<
  WorkflowTemplateSummary,
  Omit<AdminTemplateListQuery, 'page' | 'pageSize'>
>({
  initialPageSize: 10,
  initialQuery: {
    builderSurface: '',
    keyword: '',
    releaseScope: '',
    sort: '-updated_at',
    status: '',
  },
  loader: ({ page, pageSize, query }) =>
    listAdminTemplatesApi({
      ...query,
      page,
      pageSize,
    }),
});

const tableColumns = computed(() => [
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.table.name`),
    dataIndex: 'name',
    key: 'name',
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.status`),
    dataIndex: 'status',
    key: 'status',
    width: 130,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.table.category`),
    dataIndex: 'category',
    key: 'category',
    width: 180,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.table.builderSurface`),
    dataIndex: 'builder_surface',
    key: 'builder_surface',
    width: 180,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.table.releaseScope`),
    dataIndex: 'release_scope',
    key: 'release_scope',
    width: 180,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.templates.table.latestVersion`),
    dataIndex: 'latest_version_label',
    key: 'latest_version_label',
    width: 140,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.updatedAt`),
    dataIndex: 'updated_at',
    key: 'updated_at',
    width: 180,
  },
  {
    title: $t(`${ADMIN_I18N_PREFIX}.common.action`),
    key: 'action',
    width: 220,
    fixed: 'right',
  },
]);

const templateStatusOptions = computed(() => getTemplateStatusOptions());
const builderSurfaceOptions = computed(() => getBuilderSurfaceOptions());
const releaseScopeOptions = computed(() => getReleaseScopeOptions());

const summaryCards = computed(() => {
  const items = collection.items.value;

  return [
    {
      key: 'total',
      icon: 'lucide:copy',
      label: $t(`${ADMIN_I18N_PREFIX}.templates.stats.totalTemplates`),
      value: formatCompactNumber(collection.total.value),
    },
    {
      key: 'published',
      icon: 'lucide:badge-check',
      label: $t(`${ADMIN_I18N_PREFIX}.templates.stats.published`),
      value: formatCompactNumber(
        items.filter((item) => item.status === 'published').length,
      ),
    },
    {
      key: 'draft',
      icon: 'lucide:file-edit',
      label: $t(`${ADMIN_I18N_PREFIX}.templates.stats.draft`),
      value: formatCompactNumber(
        items.filter((item) => item.status === 'draft').length,
      ),
    },
    {
      key: 'risk',
      icon: 'lucide:shield-alert',
      label: $t(`${ADMIN_I18N_PREFIX}.templates.stats.riskSignal`),
      value: $t(`${ADMIN_I18N_PREFIX}.common.notIntegrated`),
    },
  ];
});

async function applyFilters() {
  await collection.patchQuery({ keyword: searchKeyword.value });
}

async function handlePaginationChange(page: number, pageSize: number) {
  if (pageSize !== collection.pageSize.value) {
    await collection.setPageSize(pageSize);
    return;
  }

  await collection.setPage(page);
}

function openDetail(templateId: number) {
  router.push(buildAdminPath(`templates/${templateId}`));
}

function openEditor(templateId: number) {
  router.push(buildAdminPath(`templates/${templateId}/editor`));
}

function confirmPublish(row: WorkflowTemplateSummary) {
  Modal.confirm({
    title: $t(`${ADMIN_I18N_PREFIX}.templates.publish.confirmTitle`),
    content: $t(`${ADMIN_I18N_PREFIX}.templates.publish.confirmContent`, {
      name: row.name,
    }),
    onOk: async () => {
      publishingId.value = row.id;
      try {
        await publishAdminTemplateApi(row.id, buildTemplatePublishPayload(row));
        message.success($t(`${ADMIN_I18N_PREFIX}.templates.publish.success`));
        await collection.load();
      } finally {
        publishingId.value = null;
      }
    },
  });
}

onMounted(() => {
  searchKeyword.value = collection.query.value.keyword ?? '';
  void collection.load();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <section class="relative overflow-hidden rounded-2xl border bg-card shadow-sm">
      <div class="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-primary/5" />
      <div class="relative flex flex-col gap-4 p-5">
        <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div
              class="mb-2 inline-flex items-center gap-2 rounded-full border bg-background/85 px-3 py-1 text-xs text-muted-foreground"
            >
              <IconifyIcon icon="lucide:copy-plus" class="h-3.5 w-3.5" />
              {{ $t(`${ADMIN_I18N_PREFIX}.templates.badge`) }}
            </div>
            <h1 class="text-xl font-semibold text-foreground md:text-2xl">
              {{ $t(`${ADMIN_I18N_PREFIX}.templates.title`) }}
            </h1>
            <p class="mt-1 text-sm text-muted-foreground">
              {{ $t(`${ADMIN_I18N_PREFIX}.templates.subtitle`) }}
            </p>
          </div>

          <Button :loading="collection.loading.value" @click="collection.load">
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" />
            </template>
            {{ $t(`${ADMIN_I18N_PREFIX}.common.refresh`) }}
          </Button>
        </div>

        <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div
            v-for="card in summaryCards"
            :key="card.key"
            class="rounded-xl border bg-background/85 p-3"
          >
            <div class="flex items-center gap-2 text-xs text-muted-foreground">
              <IconifyIcon :icon="card.icon" class="h-3.5 w-3.5" />
              {{ card.label }}
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
      :description="$t(`${ADMIN_I18N_PREFIX}.templates.contractNotice.description`)"
      show-icon
      type="info"
    />

    <Card :body-style="{ padding: '18px' }">
      <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div class="grid gap-3 md:grid-cols-2 xl:flex xl:flex-wrap">
          <Input
            v-model:value="searchKeyword"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.templates.filters.searchPlaceholder`)"
            allow-clear
            class="min-w-[240px]"
            @press-enter="applyFilters"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:search" class="h-4 w-4 text-muted-foreground" />
            </template>
          </Input>

          <Select
            :value="collection.query.value.status"
            :options="templateStatusOptions"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.templates.filters.allStatuses`)"
            allow-clear
            class="min-w-[180px]"
            @change="(value) => collection.patchQuery({ status: typeof value === 'string' ? value : '' })"
          />

          <Select
            :value="collection.query.value.builderSurface"
            :options="builderSurfaceOptions"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.templates.filters.allSurfaces`)"
            allow-clear
            class="min-w-[220px]"
            @change="(value) => collection.patchQuery({ builderSurface: typeof value === 'string' ? value : '' })"
          />

          <Select
            :value="collection.query.value.releaseScope"
            :options="releaseScopeOptions"
            :placeholder="$t(`${ADMIN_I18N_PREFIX}.templates.filters.allScopes`)"
            allow-clear
            class="min-w-[220px]"
            @change="(value) => collection.patchQuery({ releaseScope: typeof value === 'string' ? value : '' })"
          />
        </div>

        <Button type="primary" @click="applyFilters">
          <template #icon>
            <IconifyIcon icon="lucide:filter" />
          </template>
          {{ $t(`${ADMIN_I18N_PREFIX}.templates.filters.apply`) }}
        </Button>
      </div>
    </Card>

    <Card :body-style="{ padding: '0' }">
      <Table
        :columns="tableColumns"
        :data-source="collection.items.value"
        :loading="collection.loading.value"
        :pagination="false"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <button
              class="flex max-w-[320px] items-start gap-3 text-left"
              type="button"
              @click="openDetail(record.id)"
            >
              <div class="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                <IconifyIcon icon="lucide:git-branch-plus" class="h-4 w-4 text-primary" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm font-medium text-foreground">
                  {{ record.name }}
                </div>
                <div class="mt-1 truncate text-xs text-muted-foreground">
                  {{ record.code || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
                </div>
                <div class="mt-1 truncate text-xs text-muted-foreground">
                  {{ record.description || $t(`${ADMIN_I18N_PREFIX}.common.noDescription`) }}
                </div>
              </div>
            </button>
          </template>

          <template v-else-if="column.key === 'status'">
            <Tag :color="getTemplateStatusColor(record.status)">
              {{ getTemplateStatusText(record.status) }}
            </Tag>
          </template>

          <template v-else-if="column.key === 'category'">
            <span class="text-sm text-foreground">
              {{ getTemplateCategoryText(record.category) }}
            </span>
          </template>

          <template v-else-if="column.key === 'builder_surface'">
            <span class="text-sm text-foreground">
              {{ getBuilderSurfaceText(record.builder_surface) }}
            </span>
          </template>

          <template v-else-if="column.key === 'release_scope'">
            <span class="text-sm text-foreground">
              {{ getReleaseScopeText(record.release_scope) }}
            </span>
          </template>

          <template v-else-if="column.key === 'latest_version_label'">
            <span class="font-mono text-sm text-foreground">
              {{ record.latest_version_label || $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`) }}
            </span>
          </template>

          <template v-else-if="column.key === 'updated_at'">
            <Tooltip :title="formatDateTime(record.updated_at)">
              <span class="text-sm text-muted-foreground">
                {{ formatDateTime(record.updated_at) }}
              </span>
            </Tooltip>
          </template>

          <template v-else-if="column.key === 'action'">
            <div class="flex items-center gap-2">
              <Button type="link" size="small" @click="openDetail(record.id)">
                {{ $t(`${ADMIN_I18N_PREFIX}.common.detail`) }}
              </Button>
              <Button type="link" size="small" @click="openEditor(record.id)">
                {{ $t(`${ADMIN_I18N_PREFIX}.common.editor`) }}
              </Button>
              <Button
                type="link"
                size="small"
                :disabled="record.latest_version_id === null || record.latest_version_id === undefined"
                :loading="publishingId === record.id"
                @click="confirmPublish(record)"
              >
                {{ $t(`${ADMIN_I18N_PREFIX}.common.publish`) }}
              </Button>
            </div>
          </template>
        </template>

        <template #emptyText>
          <div class="py-10">
            <Empty :description="$t(`${ADMIN_I18N_PREFIX}.common.emptyState`)" />
          </div>
        </template>
      </Table>

      <div class="flex justify-end border-t px-4 py-4">
        <Pagination
          :current="collection.page.value"
          :page-size="collection.pageSize.value"
          :total="collection.total.value"
          show-size-changer
          @change="handlePaginationChange"
        />
      </div>
    </Card>
  </Page>
</template>
